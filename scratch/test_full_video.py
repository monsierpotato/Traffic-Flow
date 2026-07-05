import cv2
import sys
import os
sys.path.append(r"d:\Backend_traffic_flow\Traffic-Flow_Frontend")

from tfengine.core_ai.detector import YoloByteTrackDetector

def main():
    video_path = r"D:\VID_20260622_194043.mp4"
    if not os.path.exists(video_path):
        print(f"Video not found: {video_path}")
        return

    # Initialize the same detector used in engine.py
    # We use confidence=0.1 to see if we're missing them due to threshold
    detector = YoloByteTrackDetector(model_path="models/yolov8n.pt", confidence=0.1)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Cannot open video")
        return

    motorcycles_by_track_id = {}
    
    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        detections = detector.detect_and_track(frame)
        
        for d in detections:
            if d.class_name in ["motorcycle", "motorbike"]:
                if d.track_id not in motorcycles_by_track_id:
                    motorcycles_by_track_id[d.track_id] = []
                motorcycles_by_track_id[d.track_id].append({
                    "frame": frame_idx,
                    "confidence": d.confidence,
                    "bbox": d.bbox_xyxy
                })
                
        frame_idx += 1
        if frame_idx % 100 == 0:
            print(f"Processed {frame_idx} frames...")

    cap.release()
    
    print(f"\n--- Total Frames: {frame_idx} ---")
    print(f"Total unique motorcycles (track IDs) found: {len(motorcycles_by_track_id)}")
    
    for track_id, records in motorcycles_by_track_id.items():
        max_conf = max(r["confidence"] for r in records)
        min_conf = min(r["confidence"] for r in records)
        avg_conf = sum(r["confidence"] for r in records) / len(records)
        frames_present = len(records)
        start_frame = records[0]["frame"]
        end_frame = records[-1]["frame"]
        print(f"Track ID {track_id}: {frames_present} frames (from {start_frame} to {end_frame}), conf range: [{min_conf:.3f} - {max_conf:.3f}], avg: {avg_conf:.3f}")

if __name__ == "__main__":
    main()
