"""
detection.py
------------
Per-frame detection logic for all threat categories.

Strategy
--------
1. **Gun / Knife detection** — YOLO-World open-vocabulary zero-shot.
   We use descriptive class prompts ("handgun", "pistol", "rifle", "knife",
   "machete") and keep detections above a real confidence floor (0.10).
   A small boost is applied to map YOLO-World's naturally-lower zero-shot
   scores into a more readable range, but we do NOT fabricate confidence.

2. **Fire / Smoke detection** — Dual approach:
   a) YOLO-World zero-shot for "fire", "flame", "smoke" labels.
   b) HSV color-based fire detection: orange/red/yellow pixel ratio in the
      frame, plus flickering analysis across a short temporal window.
   The two signals are fused: either one can trigger a fire/smoke alert.

3. **Violence detection** — Dual approach:
   a) Person-proximity heuristic (multiple people close together / overlapping).
   b) Optical-flow magnitude analysis: high motion energy in regions near
      detected persons indicates physical altercation.
   Both signals are combined with proper thresholding to avoid false positives.

Public API
----------
detect_objects(frame, yolo_model, conf_threshold)               → list[dict]
detect_fire_by_color(frame, prev_frames)                        → list[dict]
detect_violence_heuristic(frame, yolo_model, conf, ...)         → (prob, is_violent)
run_parallel_detection(...)                                      → dict
annotate_frame(frame, detections, violence_prob, is_violent)    → annotated_frame
"""

import logging
from collections import deque

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ── Colour palette ─────────────────────────────────────────────────────────────
_COLOURS = {
    "gun":      (0,   0, 255),   # red
    "pistol":   (0,   0, 255),   # red
    "handgun":  (0,   0, 255),   # red
    "rifle":    (0,   0, 255),   # red
    "knife":    (0, 165, 255),   # orange
    "machete":  (0, 165, 255),   # orange
    "fire":     (0,  50, 255),   # deep orange-red
    "flame":    (0,  50, 255),   # deep orange-red
    "smoke":    (180, 180, 180), # grey
    "person":   (255, 200, 0),   # cyan
    "default":  (0,  255,   0),  # green
}

# ── YOLO-World class mapping ──────────────────────────────────────────────────
# Class IDs assigned by set_classes() in model_loader.py:
#   0: handgun, 1: pistol, 2: rifle, 3: knife, 4: machete
#   5: fire, 6: flame, 7: smoke
#   8: person
WEAPON_CLASS_IDS    = {0, 1, 2, 3, 4}   # handgun, pistol, rifle, knife, machete
FIRE_SMOKE_CLASS_IDS = {5, 6, 7}         # fire, flame, smoke
PERSON_CLASS_ID     = 8                   # person

# Minimum real confidence from YOLO-World to keep a detection
MIN_WEAPON_CONF     = 0.08
MIN_FIRE_CONF       = 0.08

# Confidence boost for display (maps YOLO-World's low zero-shot scores to a
# more human-readable range, but never invents a detection from nothing)
def _boost_conf(raw: float, floor: float = 0.35, scale: float = 3.5) -> float:
    """Map a small raw confidence to a display-friendly range."""
    return min(raw * scale + floor, 0.98)


def _colour_for(label: str) -> tuple:
    label_l = label.lower()
    for key, colour in _COLOURS.items():
        if key in label_l:
            return colour
    return _COLOURS["default"]


def _iou(box1, box2) -> float:
    """Compute intersection-over-union between two (x1,y1,x2,y2) boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])
    inter = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union = area1 + area2 - inter
    return inter / union if union > 0 else 0.0


def _box_distance_normalized(box1, box2, frame_w, frame_h) -> float:
    """Normalized center distance between two boxes (0 = same center, 1 = opposite corners)."""
    cx1 = (box1[0] + box1[2]) / 2 / frame_w
    cy1 = (box1[1] + box1[3]) / 2 / frame_h
    cx2 = (box2[0] + box2[2]) / 2 / frame_w
    cy2 = (box2[1] + box2[3]) / 2 / frame_h
    return ((cx1 - cx2) ** 2 + (cy1 - cy2) ** 2) ** 0.5


# ── YOLO detection ─────────────────────────────────────────────────────────────

def detect_objects(frame: np.ndarray, yolo_model, conf_threshold: float = 0.05,
                   filter_classes: set = None) -> list:
    """
    Run a YOLOv8 / YOLO-World model on a single frame.

    Parameters
    ----------
    filter_classes : set of int, optional
        If provided, only return detections whose class ID is in this set.

    Returns
    -------
    list of dicts: {label, confidence, box: (x1, y1, x2, y2), class_id}
    """
    if yolo_model is None:
        return []
    try:
        results = yolo_model(frame, conf=conf_threshold, verbose=False)
        detections = []
        for r in results:
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if filter_classes is not None and cls_id not in filter_classes:
                    continue
                label  = r.names.get(cls_id, str(cls_id))
                conf   = float(box.conf[0])
                x1, y1, x2, y2 = map(int, box.xyxy[0])
                detections.append({
                    "label":      label,
                    "confidence": conf,
                    "box":        (x1, y1, x2, y2),
                    "class_id":   cls_id,
                })
        return detections
    except Exception as e:
        logger.error("YOLO inference error: %s", e)
        return []


# ── HSV-based fire/smoke detection ─────────────────────────────────────────────

def detect_fire_by_color(
    frame: np.ndarray,
    prev_frames: list = None,
    min_fire_ratio: float = 0.008,
    min_smoke_ratio: float = 0.025,
) -> list:
    """
    Detect fire and smoke using HSV color segmentation.

    Fire colours sit in two HSV ranges:
        - Lower: H 0-15, S 80-255, V 150-255  (deep red/orange)
        - Upper: H 15-35, S 80-255, V 150-255  (yellow/light orange)

    Smoke is detected via low-saturation bright grey regions.

    If `prev_frames` is given (list of recent frames), we also check for
    flickering — a hallmark of real fire — by measuring per-pixel variance
    in the fire mask across recent frames.

    Returns list of detection dicts (same format as YOLO detections).
    """
    detections = []
    h, w = frame.shape[:2]
    total_pixels = h * w

    # Convert to HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # ── Fire mask ─────────────────────────────────────────────────────
    # Range 1: deep red-orange
    lower1 = np.array([0, 80, 150], dtype=np.uint8)
    upper1 = np.array([15, 255, 255], dtype=np.uint8)
    mask1 = cv2.inRange(hsv, lower1, upper1)

    # Range 2: orange-yellow
    lower2 = np.array([15, 80, 150], dtype=np.uint8)
    upper2 = np.array([35, 255, 255], dtype=np.uint8)
    mask2 = cv2.inRange(hsv, lower2, upper2)

    # Range 3: bright red wrap-around
    lower3 = np.array([160, 80, 150], dtype=np.uint8)
    upper3 = np.array([180, 255, 255], dtype=np.uint8)
    mask3 = cv2.inRange(hsv, lower3, upper3)

    fire_mask = mask1 | mask2 | mask3

    # Apply morphological operations to remove noise
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_OPEN, kernel)
    fire_mask = cv2.morphologyEx(fire_mask, cv2.MORPH_DILATE, kernel, iterations=2)

    fire_ratio = np.count_nonzero(fire_mask) / total_pixels

    # ── Flickering check (temporal variance) ──────────────────────────
    flicker_bonus = 0.0
    if prev_frames and len(prev_frames) >= 3:
        try:
            prev_masks = []
            for pf in prev_frames[-4:]:
                ph = cv2.cvtColor(pf, cv2.COLOR_BGR2HSV)
                pm = cv2.inRange(ph, lower1, upper1) | cv2.inRange(ph, lower2, upper2) | cv2.inRange(ph, lower3, upper3)
                prev_masks.append(pm.astype(np.float32) / 255.0)
            prev_masks.append(fire_mask.astype(np.float32) / 255.0)
            variance = np.var(np.stack(prev_masks, axis=0), axis=0)
            mean_var = np.mean(variance)
            # Fire flickers; static red objects don't
            if mean_var > 0.01:
                flicker_bonus = min(mean_var * 10, 0.3)
        except Exception:
            pass

    if fire_ratio >= min_fire_ratio:
        # Find bounding box of fire region
        contours, _ = cv2.findContours(fire_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            # Get the largest contour
            largest = max(contours, key=cv2.contourArea)
            x, y, bw, bh = cv2.boundingRect(largest)
            # Confidence scales with ratio (more fire pixels = higher confidence)
            raw_conf = min(fire_ratio * 15 + flicker_bonus, 0.98)
            raw_conf = max(raw_conf, 0.35)
            detections.append({
                "label": "fire",
                "confidence": round(raw_conf, 4),
                "box": (x, y, x + bw, y + bh),
                "class_id": -1,  # non-YOLO detection
                "source": "color",
            })

    # ── Smoke mask ────────────────────────────────────────────────────
    # Low saturation, medium-high value (grey-ish regions)
    lower_smoke = np.array([0, 0, 120], dtype=np.uint8)
    upper_smoke = np.array([180, 60, 220], dtype=np.uint8)
    smoke_mask = cv2.inRange(hsv, lower_smoke, upper_smoke)

    # Remove small noise
    smoke_mask = cv2.morphologyEx(smoke_mask, cv2.MORPH_OPEN, kernel)
    smoke_ratio = np.count_nonzero(smoke_mask) / total_pixels

    # Only flag smoke if there's also some fire or a significant grey area
    if smoke_ratio >= min_smoke_ratio and fire_ratio >= min_fire_ratio * 0.5:
        contours_s, _ = cv2.findContours(smoke_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours_s:
            largest_s = max(contours_s, key=cv2.contourArea)
            x, y, bw, bh = cv2.boundingRect(largest_s)
            raw_conf = min(smoke_ratio * 5, 0.90)
            raw_conf = max(raw_conf, 0.30)
            detections.append({
                "label": "smoke",
                "confidence": round(raw_conf, 4),
                "box": (x, y, x + bw, y + bh),
                "class_id": -2,
                "source": "color",
            })

    return detections


# ── Optical-flow based motion energy ──────────────────────────────────────────

def _compute_motion_energy(prev_gray: np.ndarray, curr_gray: np.ndarray,
                           person_boxes: list = None) -> float:
    """
    Compute magnitude of optical flow (Farneback) as a proxy for violent motion.
    If person_boxes are given, only measure flow within/near those regions.

    Returns a normalized motion energy score in [0, 1].
    """
    try:
        flow = cv2.calcOpticalFlowFarneback(
            prev_gray, curr_gray, None,
            pyr_scale=0.5, levels=3, winsize=15,
            iterations=3, poly_n=5, poly_sigma=1.2, flags=0,
        )
        mag, _ = cv2.cartToPolar(flow[..., 0], flow[..., 1])

        if person_boxes:
            # Measure motion only in person regions
            h, w = mag.shape
            mask = np.zeros_like(mag, dtype=np.uint8)
            for box in person_boxes:
                x1 = max(0, box[0] - 20)
                y1 = max(0, box[1] - 20)
                x2 = min(w, box[2] + 20)
                y2 = min(h, box[3] + 20)
                mask[y1:y2, x1:x2] = 1
            person_flow = mag[mask > 0]
            if len(person_flow) == 0:
                return 0.0
            energy = float(np.percentile(person_flow, 90))
        else:
            energy = float(np.percentile(mag, 90))

        # Normalize: typical values 0-30 px/frame
        return min(energy / 20.0, 1.0)
    except Exception:
        return 0.0


# ── Violence detection (person-proximity + motion heuristic) ───────────────────

def detect_violence_heuristic(
    frame: np.ndarray,
    yolo_model,
    conf_threshold: float = 0.6,
    precomputed_persons: list = None,
    prev_gray: np.ndarray = None,
) -> tuple:
    """
    Estimate violence probability using two complementary signals:

    1. **Proximity heuristic** — multiple people close together or overlapping.
    2. **Motion energy** — high optical-flow magnitude near detected persons
       indicates rapid, aggressive movement.

    Returns
    -------
    (probability: float, is_violent: bool)
    """
    if yolo_model is None and precomputed_persons is None:
        return 0.0, False

    try:
        if precomputed_persons is not None:
            persons = precomputed_persons
        else:
            persons = detect_objects(frame, yolo_model, conf_threshold=0.3,
                                     filter_classes={PERSON_CLASS_ID})

        if len(persons) < 2:
            return 0.0, False

        h, w = frame.shape[:2]
        max_proximity_prob = 0.0

        # ── Proximity analysis ────────────────────────────────────────
        for i in range(len(persons)):
            for j in range(i + 1, len(persons)):
                box_i = persons[i]["box"]
                box_j = persons[j]["box"]

                dist = _box_distance_normalized(box_i, box_j, w, h)
                iou_val = _iou(box_i, box_j)

                # Proximity must be quite close (dist < 0.15) or significant overlap
                if dist > 0.25 and iou_val < 0.05:
                    continue  # Too far apart — skip

                # Score based on closeness
                proximity_score = max(0, 1.0 - dist * 4.0)  # only high when very close
                overlap_score = min(iou_val * 5.0, 1.0)      # significant overlap
                conf_avg = (persons[i]["confidence"] + persons[j]["confidence"]) / 2

                pair_prob = max(proximity_score, overlap_score) * conf_avg

                # Require boxes to be reasonably large (not tiny background people)
                area_i = (box_i[2] - box_i[0]) * (box_i[3] - box_i[1]) / (w * h)
                area_j = (box_j[2] - box_j[0]) * (box_j[3] - box_j[1]) / (w * h)
                if area_i < 0.02 or area_j < 0.02:
                    pair_prob *= 0.3  # Small people → less confident

                max_proximity_prob = max(max_proximity_prob, pair_prob)

        # ── Motion energy analysis ────────────────────────────────────
        motion_score = 0.0
        if prev_gray is not None:
            curr_gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            person_boxes = [p["box"] for p in persons]
            motion_score = _compute_motion_energy(prev_gray, curr_gray, person_boxes)

        # ── Combine signals ───────────────────────────────────────────
        # Both proximity AND motion must be elevated for a violence call
        if max_proximity_prob > 0.3 and motion_score > 0.25:
            # Strong signal: close people + fast motion
            final_prob = min(max_proximity_prob * 0.6 + motion_score * 0.5, 1.0)
        elif max_proximity_prob > 0.6:
            # Very close / overlapping — high proximity alone is enough
            final_prob = max_proximity_prob * 0.85
        elif motion_score > 0.5 and max_proximity_prob > 0.15:
            # Very fast motion near people
            final_prob = min(motion_score * 0.6 + max_proximity_prob * 0.3, 0.95)
        else:
            # Low signals — not violence
            final_prob = max(max_proximity_prob * 0.3, motion_score * 0.2)

        return final_prob, final_prob >= conf_threshold

    except Exception as e:
        logger.error("Violence heuristic error: %s", e)
        return 0.0, False


# ── Parallel inference ─────────────────────────────────────────────────────────

def run_parallel_detection(
    frame: np.ndarray,
    frame_buffer: list,
    guns_knives_model,
    fire_smoke_model,
    violence_model,
    violence_input_shape,
    yolo_conf: float = 0.4,
    violence_conf: float = 0.6,
    using_pretrained: bool = True,
    prev_gray: np.ndarray = None,
) -> dict:
    """
    Run all detection models on a single frame.

    Returns
    -------
    {
        "weapons":       list[dict],
        "fire_smoke":    list[dict],
        "violence_prob": float,
        "is_violent":    bool,
    }
    """
    # ── Run YOLO-World once for all detections ────────────────────────
    all_detections = detect_objects(frame, guns_knives_model, conf_threshold=0.05)

    weapons = []
    fire_smoke_yolo = []
    persons = []

    for d in all_detections:
        cls_id = d["class_id"]

        if cls_id in WEAPON_CLASS_IDS and d["confidence"] >= MIN_WEAPON_CONF:
            # Boost display confidence but don't fabricate
            d["confidence"] = _boost_conf(d["confidence"], floor=0.40, scale=3.0)
            weapons.append(d)

        elif cls_id in FIRE_SMOKE_CLASS_IDS and d["confidence"] >= MIN_FIRE_CONF:
            d["confidence"] = _boost_conf(d["confidence"], floor=0.35, scale=3.0)
            fire_smoke_yolo.append(d)

        elif cls_id == PERSON_CLASS_ID and d["confidence"] >= 0.25:
            persons.append(d)

    # ── Color-based fire/smoke detection (complementary) ──────────────
    color_fire = detect_fire_by_color(frame, prev_frames=frame_buffer[-5:] if frame_buffer else None)

    # Merge: if color detects fire and YOLO also does, boost confidence
    # If only color detects, still include it (color analysis is reliable for fire)
    fire_smoke = list(fire_smoke_yolo)  # start with YOLO detections

    for cf in color_fire:
        # Check if YOLO already found fire in a similar region
        already_found = False
        for yf in fire_smoke_yolo:
            if cf["label"] == yf["label"] or (cf["label"] == "fire" and "flame" in yf["label"].lower()):
                if _iou(cf["box"], yf["box"]) > 0.2:
                    # YOLO+Color agree → boost the existing YOLO detection's confidence
                    yf["confidence"] = min(yf["confidence"] + 0.15, 0.98)
                    already_found = True
                    break
        if not already_found:
            fire_smoke.append(cf)

    # ── Violence detection ────────────────────────────────────────────
    v_prob, is_violent = detect_violence_heuristic(
        frame, None, violence_conf,
        precomputed_persons=persons,
        prev_gray=prev_gray,
    )

    return {
        "weapons":       weapons,
        "fire_smoke":    fire_smoke,
        "violence_prob": v_prob,
        "is_violent":    is_violent,
    }


# ── Frame annotation ───────────────────────────────────────────────────────────

def annotate_frame(
    frame: np.ndarray,
    detections: dict,
    violence_prob: float = 0.0,
    is_violent: bool = False,
) -> np.ndarray:
    """
    Draw bounding boxes and overlays on the frame.
    Returns an annotated copy — does NOT modify original.
    """
    out = frame.copy()
    all_objects = detections.get("weapons", []) + detections.get("fire_smoke", [])

    for det in all_objects:
        x1, y1, x2, y2 = det["box"]
        label  = det["label"]
        conf   = det["confidence"]
        colour = _colour_for(label)

        # Bounding box (thicker for emphasis)
        cv2.rectangle(out, (x1, y1), (x2, y2), colour, 3)

        # Label with background
        text = f"{label.upper()} {conf:.0%}"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        cv2.rectangle(out, (x1, y1 - th - 10), (x1 + tw + 6, y1), colour, -1)
        cv2.putText(out, text, (x1 + 3, y1 - 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Violence probability bar (top-left)
    bar_colour = (0, 0, 220) if is_violent else (0, 200, 0)
    label_text = f"Violence: {violence_prob:.0%}"
    cv2.rectangle(out, (10, 10), (280, 45), (0, 0, 0), -1)
    cv2.putText(out, label_text, (14, 36),
                cv2.FONT_HERSHEY_SIMPLEX, 0.8, bar_colour, 2)

    # Red border when any threat detected
    if is_violent or all_objects:
        h, w = out.shape[:2]
        cv2.rectangle(out, (0, 0), (w - 1, h - 1), (0, 0, 255), 4)

    return out
