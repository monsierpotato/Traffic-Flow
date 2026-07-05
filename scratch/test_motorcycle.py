import cv2
import sys
import os
sys.path.append(r"d:\Backend_traffic_flow\Traffic-Flow_Frontend")

from tfengine.core_ai.detector import YoloByteTrackDetector

def test_video(video_path):
    print(f"Testing video: {video_path}")
    if not os.path.exists(video_path):
        print("Video not found.")
        return

    # Use a lower confidence to see if it's a threshold issue
    detector = YoloByteTrackDetector(model_path="models/yolov8n.pt", confidence=0.05)
    
    cap = cv2.VideoCapture(video_path)
    frame_idx = 0
    motorcycles_found = 0
    motorcycle_confs = []

    while True:
        ret, frame = cap.read()
        if not ret or frame_idx > 300: # check first 300 frames
            break
        
        detections = detector.detect_and_track(frame)
        for d in detections:
            if d.class_name in ["motorcycle", "motorbike"]:
                motorcycles_found += 1
                motorcycle_confs.append(d.confidence)
                
        frame_idx += 1

    cap.release()
    print(f"Frames processed: {frame_idx}")
    print(f"Total motorcycle detections across all frames: {motorcycles_found}")
    if motorcycle_confs:
        print(f"Max confidence: {max(motorcycle_confs):.4f}")
        print(f"Min confidence: {min(motorcycle_confs):.4f}")
        print(f"Avg confidence: {sum(motorcycle_confs)/len(motorcycle_confs):.4f}")

if __name__ == "__main__":
    test_video(r"D:\VID_20260622_194043.mp4")
