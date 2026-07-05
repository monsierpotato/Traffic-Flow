import cv2
import requests
import json
import tempfile
import os

def main():
    ai_base_url = "https://tienpm205--trafficflow-inference-fastapi-app.modal.run"
    video_url = "https://pub-ee38a176dedc498d9e01b6f961efd070.r2.dev/uploads/c92cdf9d-df9d-4174-b3d8-ebd3e2ce8d07.mp4"
    
    print("Downloading video...")
    r = requests.get(video_url)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
        f.write(r.content)
        temp_name = f.name
        
    cap = cv2.VideoCapture(temp_name)
    # Read frame 50
    for _ in range(51):
        ret, frame = cap.read()
    cap.release()
    os.unlink(temp_name)
    
    print("Frame 50 read, shape:", frame.shape)
    
    # Crop parameters
    min_x, min_y = 3, 335
    width, height = 1650, 715
    cropped_frame = frame[min_y:min_y+height, min_x:min_x+width]
    print("Cropped Frame shape:", cropped_frame.shape)
    
    # Call AI on both
    session_url = f"{ai_base_url.rstrip('/')}/v1/session"
    r_sess = requests.post(session_url)
    session_id = r_sess.json()["session_id"]
    print("Session:", session_id)
    
    # 1. Uncropped
    _, buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    resp = requests.post(
        f"{ai_base_url.rstrip('/')}/v1/detect",
        files={"image": ("frame.jpg", buf.tobytes(), "image/jpeg")},
        data={"session_id": session_id},
        timeout=30
    )
    print("\n--- Uncropped Detections ---")
    print(json.dumps(resp.json(), indent=2))
    
    # 2. Cropped
    _, buf_cropped = cv2.imencode('.jpg', cropped_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    resp_cropped = requests.post(
        f"{ai_base_url.rstrip('/')}/v1/detect",
        files={"image": ("frame.jpg", buf_cropped.tobytes(), "image/jpeg")},
        data={"session_id": session_id},
        timeout=30
    )
    print("\n--- Cropped Detections ---")
    print(json.dumps(resp_cropped.json(), indent=2))
    
    # Cleanup
    requests.delete(f"{ai_base_url.rstrip('/')}/v1/session/{session_id}")

if __name__ == "__main__":
    main()
