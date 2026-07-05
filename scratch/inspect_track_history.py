import cv2
import requests
import json
import tempfile
import os
from worker.services.counting_service import CountingState, bbox_center, point_in_polygon

def main():
    ai_base_url = "https://tienpm205--trafficflow-inference-fastapi-app.modal.run"
    video_url = "https://pub-ee38a176dedc498d9e01b6f961efd070.r2.dev/uploads/c92cdf9d-df9d-4174-b3d8-ebd3e2ce8d07.mp4"
    
    print("Downloading video...")
    r = requests.get(video_url)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
        f.write(r.content)
        temp_name = f.name
        
    lane_config = {
        'lanes': [
            {'lane_id': 'lane_1', 'valid_zone': [[624.18, 397.31], [922.74, 386.5], [738.84, 1011.75], [7.59, 955.5]], 'counting_line': [[371.05, 968.48], [795.09, 388.66]], 'direction': [[825.38, 477.36], [708.55, 654.77]], 'class_allowed': ['car', 'bus', 'truck', 'motorcycle']},
            {'lane_id': 'lane_2', 'valid_zone': [[948.7, 386.5], [1219.13, 386.5], [1612.88, 1009.59], [831.87, 1016.08]], 'counting_line': [[1085.0, 380.0], [1232.11, 1011.75]], 'direction': [[1273.22, 866.8], [1212.64, 600.68]], 'class_allowed': ['car', 'bus', 'truck', 'motorcycle']}
        ]
    }
    
    cap = cv2.VideoCapture(temp_name)
    r_session = requests.post(f"{ai_base_url.rstrip('/')}/v1/session", timeout=30)
    session_id = r_session.json().get("session_id")
    print(f"AI Session: {session_id}")
    
    track_history = {} # track_id -> list of (frame_idx, center, in_lane_1, in_lane_2)
    
    frame_idx = 0
    frame_skip = 2
    max_frames = 150
    
    try:
        while frame_idx < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_idx % frame_skip != 0:
                frame_idx += 1
                continue
                
            success, jpeg_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_jpeg = jpeg_buf.tobytes()
            
            resp = requests.post(
                f"{ai_base_url.rstrip('/')}/v1/detect",
                files={"image": ("frame.jpg", frame_jpeg, "image/jpeg")},
                data={"session_id": session_id},
                timeout=30
            )
            detections = resp.json().get("detections", [])
            
            for det in detections:
                track_id = det.get("track_id")
                bbox = det.get("bbox_xyxy")
                center = bbox_center(bbox)
                
                in_l1 = point_in_polygon(center[0], center[1], lane_config["lanes"][0]["valid_zone"])
                in_l2 = point_in_polygon(center[0], center[1], lane_config["lanes"][1]["valid_zone"])
                
                if track_id not in track_history:
                    track_history[track_id] = []
                track_history[track_id].append((frame_idx, center, in_l1, in_l2))
                
            frame_idx += 1
            
    finally:
        cap.release()
        os.unlink(temp_name)
        requests.delete(f"{ai_base_url.rstrip('/')}/v1/session/{session_id}", timeout=10)
        
    print("\n=== Track Histories ===")
    for tid, history in sorted(track_history.items()):
        if len(history) > 2: # only print tracks seen multiple times
            print(f"Track {tid} (length {len(history)}):")
            for f_idx, center, in_l1, in_l2 in history:
                print(f"  - Frame {f_idx}: center={center}, in_l1={in_l1}, in_l2={in_l2}")

if __name__ == "__main__":
    main()
