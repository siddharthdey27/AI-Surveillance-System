from ultralytics import YOLO
import sys

try:
    model = YOLO('e:/AI Serveillance/yolov8s-world.pt')
    model.set_classes(["gun", "knife", "fire", "smoke", "person"])
    print("YOLO-World loaded successfully!")
    print(model.names)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
