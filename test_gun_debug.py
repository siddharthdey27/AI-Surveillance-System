"""Debug: test different YOLO-World prompts for gun detection."""
import cv2, sys
sys.path.insert(0, "e:/AI Serveillance/backend")

from ultralytics import YOLO
from pathlib import Path

# Load YOLO-World
model_path = Path("e:/AI Serveillance/yolov8s-world.pt")
model = YOLO(str(model_path))

# Read frames from gun.mp4
cap = cv2.VideoCapture("e:/AI Serveillance/gun.mp4")
frames = []
for i in range(200):
    ret, f = cap.read()
    if not ret:
        break
    if i % 10 == 0:
        frames.append(cv2.resize(f, (640, 480)))
cap.release()
print(f"Testing {len(frames)} frames from gun.mp4\n")

# Test different prompt sets
prompt_sets = [
    ["gun", "knife", "fire", "smoke", "person"],
    ["weapon", "firearm", "person"],
    ["gun", "pistol", "weapon", "person"],
]

for prompts in prompt_sets:
    model.set_classes(prompts)
    print(f"Prompts: {prompts}")
    found = 0
    
    for fi, frame in enumerate(frames):
        results = model(frame, conf=0.01, verbose=False)
        for r in results:
            names = r.names
            # Handle both dict and list name formats
            for box in r.boxes:
                cls_id = int(box.cls[0])
                if isinstance(names, dict):
                    label = names.get(cls_id, str(cls_id))
                elif isinstance(names, list):
                    label = names[cls_id] if cls_id < len(names) else str(cls_id)
                else:
                    label = str(cls_id)
                conf = float(box.conf[0])
                if "person" not in label.lower():
                    found += 1
                    print(f"  Frame {fi}: {label} conf={conf:.4f}")
    
    if found == 0:
        print("  (no non-person detections)")
    print()

# Also test: what does standard YOLOv8n find?
print("=" * 50)
print("Testing with YOLOv8n (COCO 80 classes)...")
model_n = YOLO("e:/AI Serveillance/yolov8n.pt")
for fi, frame in enumerate(frames[:5]):
    results = model_n(frame, conf=0.25, verbose=False)
    for r in results:
        for box in r.boxes:
            cls_id = int(box.cls[0])
            label = r.names.get(cls_id, str(cls_id))
            conf = float(box.conf[0])
            if label.lower() not in ("person",):
                print(f"  Frame {fi}: {label} (cls={cls_id}) conf={conf:.3f}")
