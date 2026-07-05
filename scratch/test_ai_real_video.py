import cv2
import requests
import json
import os

def main():
    ai_base_url = "https://tienpm205--trafficflow-inference-fastapi-app.modal.run"
    video_path = r"D:\VID_20260622_194043.mp4"
    
    if not os.path.exists(video_path):
        print(f"File not found: {video_path}")
        return

    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        print("Failed to open video")
        return
        
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Total frames: {total_frames}")

    session_url = f"{ai_base_url.rstrip('/')}/v1/session"
    r = requests.post(session_url, timeout=30)
    session_id = r.json().get("session_id")
    print(f"Session: {session_id}")
    
    motorcycles_by_track = {}

    frame_idx = 0
    # Process every 5th frame to speed things up but still get a good look
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_idx % 5 == 0:
            success, jpeg_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            if not success:
                frame_idx += 1
                continue
            
            detect_url = f"{ai_base_url.rstrip('/')}/v1/detect"
            try:
                resp = requests.post(
                    detect_url,
                    files={"image": ("frame.jpg", jpeg_buf.tobytes(), "image/jpeg")},
                    data={"session_id": session_id, "confidence": 0.1},
                    timeout=30
                )
                if resp.status_code == 200:
                    detections = resp.json().get("detections", [])
                    for d in detections:
                        if d["class_name"] in ["motorcycle", "motorbike"]:
                            tid = d["track_id"]
                            if tid not in motorcycles_by_track:
                                motorcycles_by_track[tid] = []
                            motorcycles_by_track[tid].append({
                                "frame": frame_idx,
                                "conf": d["confidence"]
                            })
                else:
                    print(f"Error at frame {frame_idx}: {resp.status_code}")
            except Exception as e:
                print(f"Exception at frame {frame_idx}: {e}")
                
            if frame_idx % 50 == 0:
                print(f"Processed {frame_idx}/{total_frames}")
                
        frame_idx += 1
        if frame_idx > 300: # Limit to first 300 frames to save time
            break

    cap.release()
    requests.delete(f"{ai_base_url.rstrip('/')}/v1/session/{session_id}", timeout=10)
    
    print("\n--- Summary ---")
    print(f"Total unique motorcycles (track IDs) found: {len(motorcycles_by_track)}")
    for tid, records in motorcycles_by_track.items():
        max_conf = max(r["conf"] for r in records)
        frames_present = len(records)
        start_frame = records[0]["frame"]
        end_frame = records[-1]["frame"]
        print(f"Track ID {tid}: {frames_present} hits (from {start_frame} to {end_frame}), max conf: {max_conf:.3f}")

if __name__ == "__main__":
    main()
