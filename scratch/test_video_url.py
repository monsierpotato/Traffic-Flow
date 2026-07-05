import requests
import cv2
import tempfile
import os

url = "https://pub-ee38a176dedc498d9e01b6f961efd070.r2.dev/uploads/c92cdf9d-df9d-4174-b3d8-ebd3e2ce8d07.mp4"
print("Fetching headers from:", url)
try:
    r = requests.head(url, timeout=10)
    print("Status:", r.status_code)
    print("Content-Length:", r.headers.get("Content-Length"))
    print("Content-Type:", r.headers.get("Content-Type"))
    
    # Download first 1MB
    print("Downloading first 5MB...")
    r = requests.get(url, stream=True, timeout=20)
    content = b""
    for chunk in r.iter_content(chunk_size=1024*1024):
        content += chunk
        if len(content) >= 5 * 1024 * 1024:
            break
    print("Downloaded", len(content), "bytes")
    
    # Try saving and reading with opencv
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as f:
        f.write(content)
        temp_name = f.name
    
    print("Checking with OpenCV...")
    cap = cv2.VideoCapture(temp_name)
    print("Is opened:", cap.isOpened())
    if cap.isOpened():
        print("Frames:", cap.get(cv2.CAP_PROP_FRAME_COUNT))
        print("Width:", cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        print("Height:", cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    cap.release()
    os.unlink(temp_name)

except Exception as e:
    print("Failed:", e)
