"""Quick test script for fire, gun, and violence detection."""
import cv2
import sys
import numpy as np

sys.path.insert(0, "e:/AI Serveillance/backend")
from detection import detect_fire_by_color, detect_objects, detect_violence_heuristic
from model_loader import load_all_models

print("=" * 60)
print("AI Surveillance Detection Test")
print("=" * 60)

# Load models
print("\n[1] Loading models...")
models = load_all_models()
yolo_model = models["guns_knives_model"]
print(f"    Models loaded: {models['loaded_count']}/3")

# ── Test fire.mp4 ──────────────────────────────────────────
print("\n[2] Testing FIRE detection on fire.mp4...")
cap = cv2.VideoCapture("e:/AI Serveillance/fire.mp4")
fire_count = 0
prev_frames = []
tested = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    tested += 1
    if tested % 10 != 0:
        continue

    display = cv2.resize(frame, (640, 480))
    prev_frames.append(display)
    if len(prev_frames) > 5:
        prev_frames.pop(0)

    # Color-based fire detection
    color_results = detect_fire_by_color(display, prev_frames)

    # YOLO-World fire detection
    yolo_results = detect_objects(display, yolo_model, conf_threshold=0.05,
                                  filter_classes={5, 6, 7})

    if color_results or yolo_results:
        fire_count += 1
        for r in color_results:
            print(f"    Frame {tested}: [COLOR] {r['label']} conf={r['confidence']:.2f}")
        for r in yolo_results:
            print(f"    Frame {tested}: [YOLO]  {r['label']} conf={r['confidence']:.3f}")

    if tested > 150:
        break

cap.release()
print(f"    Fire detected in {fire_count} sampled frames")

# ── Test gun.mp4 ───────────────────────────────────────────
print("\n[3] Testing GUN detection on gun.mp4...")
cap = cv2.VideoCapture("e:/AI Serveillance/gun.mp4")
gun_count = 0
tested = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break
    tested += 1
    if tested % 10 != 0:
        continue

    display = cv2.resize(frame, (640, 480))
    results = detect_objects(display, yolo_model, conf_threshold=0.05,
                             filter_classes={0, 1, 2, 3, 4})

    if results:
        gun_count += 1
        for r in results:
            print(f"    Frame {tested}: [YOLO] {r['label']} conf={r['confidence']:.3f}")

    if tested > 150:
        break

cap.release()
print(f"    Weapons detected in {gun_count} sampled frames")

# ── Test fighting1.mp4 ─────────────────────────────────────
print("\n[4] Testing VIOLENCE detection on fighting1.mp4...")
cap = cv2.VideoCapture("e:/AI Serveillance/fighting1.mp4")
violence_count = 0
tested = 0
prev_gray = None

while True:
    ret, frame = cap.read()
    if not ret:
        break
    tested += 1
    if tested % 5 != 0:
        continue

    display = cv2.resize(frame, (640, 480))

    # Detect persons
    persons = detect_objects(display, yolo_model, conf_threshold=0.05,
                             filter_classes={8})

    # Violence heuristic
    v_prob, is_violent = detect_violence_heuristic(
        display, None, 0.60,
        precomputed_persons=persons,
        prev_gray=prev_gray,
    )
    prev_gray = cv2.cvtColor(display, cv2.COLOR_BGR2GRAY)

    if v_prob > 0.3:
        violence_count += 1
        marker = "VIOLENT" if is_violent else "motion"
        print(f"    Frame {tested}: [{marker}] prob={v_prob:.2f} persons={len(persons)}")

    if tested > 150:
        break

cap.release()
print(f"    Violence signals in {violence_count} sampled frames")

print("\n" + "=" * 60)
print("Test complete!")
print("=" * 60)
