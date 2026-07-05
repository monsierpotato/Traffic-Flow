import asyncio, cv2, requests, tempfile, copy
from motor.motor_asyncio import AsyncIOMotorClient
from lib.config import settings
from worker.services.counting_service import bbox_center, point_in_polygon

TASK_ID = "8d09401f-d689-4901-bc13-28e69d22db92"

async def debug():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    task = await db.tasks.find_one({"task_id": TASK_ID})
    lane_config = await db.lane_configs.find_one({"task_id": TASK_ID})
    if not lane_config:
        lane_config = await db.lane_configs.find_one({"video_id": task.get("video_id")})
    
    print("=== TASK ===")
    print("video_url:", task.get("video_url"))
    print()
    print("=== LANE CONFIG ===")
    annotation_roi = lane_config.get("annotation_roi")
    print("annotation_roi:", annotation_roi)
    lanes = lane_config.get("lanes", [])
    for i, l in enumerate(lanes):
        print("Lane", i, l.get("lane_id"))
        print("  valid_zone:", l.get("valid_zone"))
        print("  counting_line:", l.get("counting_line"))
        print("  direction:", l.get("direction"))
        print("  class_allowed:", l.get("class_allowed"))
    
    # Download and test frame
    print()
    print("=== DETECTION TEST ===")
    resp = requests.get(task["video_url"])
    tf = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
    tf.write(resp.content)
    tf.close()
    cap = cv2.VideoCapture(tf.name)
    
    min_x = int(annotation_roi["x"]) if annotation_roi and "x" in annotation_roi else 0
    min_y = int(annotation_roi["y"]) if annotation_roi and "x" in annotation_roi else 0
    max_x = int(min_x + annotation_roi["width"]) if annotation_roi and "x" in annotation_roi else 0
    max_y = int(min_y + annotation_roi["height"]) if annotation_roi and "x" in annotation_roi else 0
    print("ROI crop:", min_x, min_y, max_x, max_y)
    
    # Shift lanes
    lanes_shifted = copy.deepcopy(lanes)
    if annotation_roi and "x" in annotation_roi:
        for lane in lanes_shifted:
            for k in ["valid_zone", "counting_line", "direction"]:
                if k in lane:
                    for pt in lane[k]:
                        pt[0] -= min_x
                        pt[1] -= min_y
    
    for i, l in enumerate(lanes_shifted):
        print("Shifted Lane", i, l.get("lane_id"))
        print("  valid_zone:", l.get("valid_zone"))
        print("  counting_line:", l.get("counting_line"))
    
    ai_base = settings.AI_SERVING_URL
    sess = requests.post(f"{ai_base}/v1/session").json()["session_id"]
    
    # Process first 20 frames
    for i in range(20):
        ret, frame = cap.read()
        if not ret:
            break
        if i % 2 != 0:
            continue
        
        h_img, w_img = frame.shape[:2]
        if annotation_roi and "x" in annotation_roi:
            frame = frame[max(0, min_y):min(h_img, max_y), max(0, min_x):min(w_img, max_x)]
        
        print(f"\nFrame {i}: shape={frame.shape}")
        _, buf = cv2.imencode(".jpg", frame)
        result = requests.post(
            f"{ai_base}/v1/detect",
            files={"image": ("frame.jpg", buf.tobytes(), "image/jpeg")},
            data={"session_id": sess}
        ).json()
        dets = result.get("detections", [])
        print(f"  -> {len(dets)} detections")
        for d in dets[:5]:
            c = bbox_center(d["bbox_xyxy"])
            in_z0 = point_in_polygon(c[0], c[1], lanes_shifted[0]["valid_zone"])
            in_z1 = point_in_polygon(c[0], c[1], lanes_shifted[1]["valid_zone"]) if len(lanes_shifted) > 1 else False
            print(f"    tid={d['track_id']} cls={d['class_name']} bbox={d['bbox_xyxy']} center=({c[0]:.0f},{c[1]:.0f}) in_z0={in_z0} in_z1={in_z1}")
        if len(dets) > 5:
            print(f"    ... and {len(dets) - 5} more")
    
    requests.delete(f"{ai_base}/v1/session/{sess}")

asyncio.run(debug())
