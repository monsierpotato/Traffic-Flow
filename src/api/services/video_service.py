import os
import tempfile
import logging
import cv2

logger = logging.getLogger(__name__)

def extract_first_frame(video_bytes: bytes) -> bytes:
    """Writes video bytes to a temp file, extracts the first frame using OpenCV,
    and returns the frame encoded as JPEG bytes.
    """
    temp_video = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    try:
        temp_video.write(video_bytes)
        temp_video.close()

        cap = cv2.VideoCapture(temp_video.name)
        if not cap.isOpened():
            raise ValueError("Could not open video file with OpenCV.")

        success, frame = cap.read()
        cap.release()

        if not success or frame is None:
            raise ValueError("Could not read first frame from video.")

        # Encode frame as JPEG
        success, jpeg_bytes = cv2.imencode(".jpg", frame)
        if not success:
            raise ValueError("Could not encode frame to JPEG.")

        return jpeg_bytes.tobytes()

    except Exception as e:
        logger.error(f"Error extracting first frame: {str(e)}")
        raise e
    finally:
        # Clean up temporary video file
        if os.path.exists(temp_video.name):
            try:
                os.unlink(temp_video.name)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_video.name}: {str(e)}")


def crop_video(video_bytes: bytes, bbox: tuple) -> bytes:
    """
    Crops the video physically using OpenCV based on the bounding box (min_x, min_y, max_x, max_y).
    Returns the cropped video as bytes (mp4 format).
    """
    min_x, min_y, max_x, max_y = [int(v) for v in bbox]
    
    # Write input bytes to temp file
    temp_in = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_in.write(video_bytes)
    temp_in.close()

    temp_out = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    temp_out_name = temp_out.name
    temp_out.close()

    try:
        cap = cv2.VideoCapture(temp_in.name)
        if not cap.isOpened():
            raise ValueError("Could not open video file with OpenCV for cropping.")

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30.0  # fallback
            
        width = max_x - min_x
        height = max_y - min_y

        # Use mp4v codec
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(temp_out_name, fourcc, fps, (width, height))

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            # Crop the frame
            cropped_frame = frame[min_y:max_y, min_x:max_x]
            out.write(cropped_frame)

        cap.release()
        out.release()

        with open(temp_out_name, "rb") as f:
            out_bytes = f.read()

        return out_bytes
    except Exception as e:
        logger.error(f"Error cropping video: {str(e)}")
        raise e
    finally:
        if os.path.exists(temp_in.name):
            try: os.unlink(temp_in.name)
            except: pass
        if os.path.exists(temp_out_name):
            try: os.unlink(temp_out_name)
            except: pass
