"""
model_loader.py
---------------
Loads and caches all AI models used by the surveillance system.

Strategy:
    We use YOLO-World (yolov8s-world.pt) as a unified model for all detections.
    YOLO-World supports open-vocabulary detection, allowing us to detect custom
    classes like firearms, bladed weapons, fire, smoke, and people.

    Class prompt list is designed to maximise zero-shot recall:
        0: handgun    4: machete
        1: pistol     5: fire
        2: rifle      6: flame
        3: knife      7: smoke
        8: person

    Violence detection is handled via a person-proximity + optical-flow
    heuristic in detection.py using 'person' detections from YOLO-World.

Compatibility:
    Python 3.10+, Windows 10/11, CPU or CUDA.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---- Paths -------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
ROOT_DIR = BASE_DIR.parent


# ---- YOLO loader -------------------------------------------------------------

def load_yolo_model(model_name_or_path: str = "yolov8n.pt", device: str = ""):
    """
    Load a YOLOv8 model.
    
    If model_name_or_path is just a name like 'yolov8n.pt', ultralytics will
    auto-download it on first run.  If it's a path to a custom .pt file,
    it loads from that path.
    
    device='' means CPU, 'cuda' for GPU.
    """
    try:
        from ultralytics import YOLO

        # Check if it's a custom model file path
        custom_path = Path(model_name_or_path)
        if custom_path.is_absolute() and custom_path.exists():
            model = YOLO(str(custom_path))
            logger.info("YOLO loaded (custom): %s  device=%s", custom_path.name, device or "cpu")
        else:
            # Also check backend/ and project root for custom models
            for d in (BASE_DIR, ROOT_DIR):
                p = d / model_name_or_path
                if p.exists():
                    model = YOLO(str(p))
                    logger.info("YOLO loaded (local): %s  device=%s", p.name, device or "cpu")
                    if device:
                        model.to(device)
                    return model

            # Fall back to pretrained (auto-download)
            model = YOLO(model_name_or_path)
            logger.info("YOLO loaded (pretrained): %s  device=%s", model_name_or_path, device or "cpu")

        if device:
            model.to(device)
        return model

    except Exception as e:
        logger.error("YOLO load failed (%s): %s", model_name_or_path, e)
        return None


# ---- Device detection --------------------------------------------------------

def get_device() -> str:
    """Return 'cuda' if a GPU is available, else '' (CPU)."""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else ""
    except ImportError:
        return ""


# ---- Main factory ------------------------------------------------------------

def load_all_models() -> dict:
    """
    Load all detection models.  Safe to call even if some models fail.
    
    Strategy:
      1. Load YOLO-World (yolov8s-world.pt) for open-vocabulary detection.
      2. Set descriptive class prompts that maximise zero-shot accuracy.
      3. Violence model (Keras) is skipped — detection.py uses a 
         person-proximity + optical-flow heuristic instead.
    """
    device = get_device()
    logger.info("Device: %s", device or "cpu")

    # ── Try custom models first, fall back to YOLO-World ──────────────────
    yolo_world_model = None
    for name in ("yolov8s-world.pt", "yolov8s-worldv2.pt"):
        for d in (BASE_DIR, ROOT_DIR):
            p = d / name
            if p.exists():
                yolo_world_model = load_yolo_model(str(p), device)
                break
        if yolo_world_model:
            break

    if yolo_world_model is None:
        logger.warning("Local YOLO-World model not found. Using pretrained yolov8s-world.pt")
        yolo_world_model = load_yolo_model("yolov8s-world.pt", device)

    if yolo_world_model:
        # Set descriptive class prompts for better zero-shot performance.
        # Using multiple synonyms per category increases recall.
        # Class IDs: 0=handgun, 1=pistol, 2=rifle, 3=knife, 4=machete,
        #            5=fire, 6=flame, 7=smoke, 8=person
        try:
            yolo_world_model.set_classes([
                "handgun", "pistol", "rifle",       # weapons - firearms
                "knife", "machete",                  # weapons - bladed
                "fire", "flame", "smoke",            # fire/smoke
                "person",                            # for violence heuristic
            ])
            logger.info("YOLO-World classes set: handgun, pistol, rifle, knife, machete, fire, flame, smoke, person")
        except Exception as e:
            logger.error("Failed to set YOLO-World classes: %s", e)

    # We reuse the same model instance since detection.py runs it once per frame
    guns_knives_model = yolo_world_model
    fire_smoke_model = yolo_world_model

    # Violence model — skip Keras entirely, use heuristic in detection.py
    violence_model = None
    violence_input_shape = None
    logger.info("Violence detection: using person-proximity + optical-flow heuristic")

    loaded_count = sum([
        guns_knives_model is not None,
        fire_smoke_model is not None,
    ])
    # Count violence as "loaded" since the heuristic is always available
    loaded_count += 1

    logger.info("Models loaded: %d / 3", loaded_count)

    return {
        "violence_model":       violence_model,
        "violence_input_shape": violence_input_shape,
        "guns_knives_model":    guns_knives_model,
        "fire_smoke_model":     fire_smoke_model,
        "device":               device,
        "loaded_count":         loaded_count,
        "using_pretrained":     True,
    }
