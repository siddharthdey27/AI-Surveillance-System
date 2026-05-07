import cv2
import numpy as np
from model_loader import load_yolo_model
from detection import run_parallel_detection
import sys

def test():
    model = load_yolo_model("yolov8s-world.pt", "")
    if model:
        model.set_classes(["gun", "knife", "fire", "smoke", "person"])
        
        for video_path in ["../fighting1.mp4", "../gun.mp4"]:
            print(f"Testing {video_path}...")
            cap = cv2.VideoCapture(video_path)
            frame_buffer = []
            frame_idx = 0
            max_v_prob = 0.0
            weapons_found = False
            while True:
                ret, frame = cap.read()
                if not ret or frame_idx > 150:
                    break
                
                if frame_idx % 5 == 0:
                    display_frame = cv2.resize(frame, (640, 480))
                    frame_buffer.append(display_frame)
                    
                    detections = run_parallel_detection(
                        display_frame, frame_buffer,
                        model, model, None, None,
                        yolo_conf=0.4, violence_conf=0.6, using_pretrained=True
                    )
                    if detections["violence_prob"] > max_v_prob:
                        max_v_prob = detections["violence_prob"]
                    if len(detections["weapons"]) > 0:
                        weapons_found = True
                        print(f"Weapon detected in {video_path} at frame {frame_idx}:", detections["weapons"])
                frame_idx += 1
                
            print(f"Max violence probability for {video_path}:", max_v_prob)
            print(f"Weapons found in {video_path}:", weapons_found)
            cap.release()

if __name__ == "__main__":
    test()
