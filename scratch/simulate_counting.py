import cv2
import requests
import json
import tempfile
import os
from worker.services.counting_service import CountingState, bbox_center, point_in_polygon

def main():
    ai_base_url = "https://tienpm205--trafficflow-inference-fastapi-app.modal.run"
    video_url = "https://pub-ee38a176dedc498d9e01b6f961efd070.r2.dev/uploads/c92cdf9d-df9d-4174-b3d8-ebd3e2ce8d07.mp4"
    
    # 1. Download video
    print("Downloading video...")
    r = requests.get(video_url)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
        f.write(r.content)
        temp_name = f.name
        
    # 2. Setup config
    lane_config = {
        'annotation_roi': {'type': 'rectangle', 'x': 3.99, 'y': 335.86, 'width': 1650.5, 'height': 715.22, 'purpose': 'frontend_annotation_only'},
        'lanes': [
            {'lane_id': 'lane_1', 'valid_zone': [[624.18, 397.31], [922.74, 386.5], [738.84, 1011.75], [7.59, 955.5]], 'counting_line': [[371.05, 968.48], [795.09, 388.66]], 'direction': [[825.38, 477.36], [708.55, 654.77]], 'class_allowed': ['car', 'bus', 'truck', 'motorcycle']},
            {'lane_id': 'lane_2', 'valid_zone': [[948.7, 386.5], [1219.13, 386.5], [1612.88, 1009.59], [831.87, 1016.08]], 'counting_line': [[1085.0, 380.0], [1232.11, 1011.75]], 'direction': [[1273.22, 866.8], [1212.64, 600.68]], 'class_allowed': ['car', 'bus', 'truck', 'motorcycle']}
        ]
    }
    
    lanes = lane_config["lanes"]
    annotation_roi = lane_config["annotation_roi"]
    min_x = int(annotation_roi["x"])
    min_y = int(annotation_roi["y"])
    max_x = int(min_x + annotation_roi["width"])
    max_y = int(min_y + annotation_roi["height"])
    
    # Adjust coordinates
    for lane in lanes:
        for list_name in ["valid_zone", "counting_line", "direction"]:
            if list_name in lane:
                for pt in lane[list_name]:
                    pt[0] -= min_x
                    pt[1] -= min_y
                    
    counting_state = CountingState(lanes)
    
    cap = cv2.VideoCapture(temp_name)
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Total frames: {total_frames}")
    
    # Create AI Session
    r_session = requests.post(f"{ai_base_url.rstrip('/')}/v1/session", timeout=30)
    session_id = r_session.json().get("session_id")
    print(f"AI Session: {session_id}")
    
    frame_idx = 0
    frame_skip = 5  # Process every 5th frame for speed
    processed_frames = 0
    
    # We will only run first 150 frames to see what happens
    max_frames_to_process = 150
    
    try:
        while frame_idx < max_frames_to_process:
            ret, frame = cap.read()
            if not ret:
                break
                
            if frame_idx % frame_skip != 0:
                frame_idx += 1
                continue
                
            # Crop
            h_img, w_img = frame.shape[:2]
            c_min_y, c_max_y = max(0, min_y), min(h_img, max_y)
            c_min_x, c_max_x = max(0, min_x), min(w_img, max_x)
            cropped_frame = frame[c_min_y:c_max_y, c_min_x:c_max_x]
            
            # Encode
            success, jpeg_buf = cv2.imencode('.jpg', cropped_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            frame_jpeg = jpeg_buf.tobytes()
            
            # Detect
            resp = requests.post(
                f"{ai_base_url.rstrip('/')}/v1/detect",
                files={"image": ("frame.jpg", frame_jpeg, "image/jpeg")},
                data={"session_id": session_id},
                timeout=30
            )
            detections = resp.json().get("detections", [])
            
            if detections:
                print(f"\nFrame {frame_idx}: {len(detections)} detections")
                for det in detections:
                    track_id = det.get("track_id")
                    class_name = det.get("class_name")
                    bbox = det.get("bbox_xyxy")
                    center = bbox_center(bbox)
                    
                    # Print alignment details
                    print(f"  Track {track_id} ({class_name}): bbox={bbox}, center={center}")
                    
                    for lane in lanes:
                        lane_id = lane["lane_id"]
                        allowed = lane.get("class_allowed", [])
                        if allowed and class_name not in allowed:
                            print(f"    - {lane_id}: class not allowed ({class_name} vs {allowed})")
                            continue
                            
                        in_poly = point_in_polygon(center[0], center[1], lane["valid_zone"])
                        print(f"    - {lane_id}: in valid_zone = {in_poly} (valid_zone={lane['valid_zone']})")
            
            # Process detections in counting state
            counting_state.process_detections(detections)
            
            frame_idx += 1
            processed_frames += 1
            
    finally:
        cap.release()
        os.unlink(temp_name)
        requests.delete(f"{ai_base_url.rstrip('/')}/v1/session/{session_id}", timeout=10)
        
    print("\n=== Final Simulation Stats ===")
    print(counting_state.get_statistics())

if __name__ == "__main__":
    main()
