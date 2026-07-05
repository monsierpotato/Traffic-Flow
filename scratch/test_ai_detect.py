import cv2
import requests
import json

def main():
    ai_base_url = "https://tienpm205--trafficflow-inference-fastapi-app.modal.run"
    video_path = "sample.mp4"
    
    # 1. Read first frame from sample.mp4
    print("Reading first frame from:", video_path)
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    cap.release()
    
    if not ret:
        print("Failed to read frame from video")
        return
        
    print(f"Read frame with shape: {frame.shape}")
    
    # 2. Encode to JPEG
    success, jpeg_buf = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
    if not success:
        print("Failed to encode frame as JPEG")
        return
        
    frame_jpeg = jpeg_buf.tobytes()
    print(f"Encoded JPEG size: {len(frame_jpeg)} bytes")
    
    # 3. Create Session
    session_url = f"{ai_base_url.rstrip('/')}/v1/session"
    print("Creating AI session...")
    try:
        r = requests.post(session_url, timeout=30)
        session_id = r.json().get("session_id")
        print("Session ID:", session_id)
        
        # 4. Detect frame
        detect_url = f"{ai_base_url.rstrip('/')}/v1/detect"
        print("Sending detect request...")
        resp = requests.post(
            detect_url,
            files={"image": ("frame.jpg", frame_jpeg, "image/jpeg")},
            data={"session_id": session_id},
            timeout=30
        )
        print("Detect Status:", resp.status_code)
        print("Detect Response:", json.dumps(resp.json(), indent=2))
        
        # 5. Clean up session
        delete_url = f"{ai_base_url.rstrip('/')}/v1/session/{session_id}"
        requests.delete(delete_url, timeout=10)
        print("Session cleaned up")
        
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    main()
