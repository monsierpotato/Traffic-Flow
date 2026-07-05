# TrafficFlow Serving — API Integration Guide

## Base URL

```
https://tienpm205--trafficflow-inference-fastapi-app.modal.run
```

> Hosted on Modal (serverless GPU). Container auto-spins on request, idle timeout 5 min.
> No authentication required. CORS open to all origins.

---

## Endpoints

### Health Check

```
GET /v1/health
```

Response `200`:
```json
{ "status": "ok" }
```

---

### Create Session

```
POST /v1/session
```

Response `200`:
```json
{ "session_id": "a1b2c3d4e5f6g7h8" }
```

> Use this if you want to pre-allocate a session before sending frames.
> Otherwise, POST /detect with an empty `session_id` will auto-create one.

---

### Delete Session

```
DELETE /v1/session/{session_id}
```

Response `200`:
```json
{ "status": "deleted" }
```

> Clean up sessions when a video stream ends to free GPU memory.

---

### Detect Objects

```
POST /v1/detect
Content-Type: multipart/form-data
```

#### Request Fields

| Field        | Type   | Required | Description |
|-------------|--------|----------|-------------|
| `image`      | file   | ✅       | JPEG/PNG frame image |
| `session_id` | string | ❌       | Tracking session ID. Leave empty to auto-create |
| `confidence` | float  | ❌       | Override confidence threshold for this request |

#### cURL Example

```bash
curl -X POST https://tienpm205--trafficflow-inference-fastapi-app.modal.run/v1/detect \
  -F "image=@frame.jpg" \
  -F "session_id=video_1"
```

#### Response `200`

```json
{
  "session_id": "video_1",
  "detections": [
    {
      "track_id": 1,
      "class_id": 2,
      "class_name": "car",
      "confidence": 0.93,
      "bbox_xyxy": [100.5, 200.3, 250.1, 350.7]
    }
  ]
}
```

| Field                  | Type                | Description |
|------------------------|---------------------|-------------|
| `session_id`           | string              | Same session_id sent in request (or newly created) |
| `detections[].track_id`| int                 | Unique object ID, persistent across frames in same session |
| `detections[].class_id`| int                 | COCO class ID |
| `detections[].class_name`| string            | One of: `car`, `bus`, `truck`, `motorcycle`, `motorbike` |
| `detections[].confidence`| float             | Detection confidence (0–1) |
| `detections[].bbox_xyxy`| [x1, y1, x2, y2]  | Bounding box in pixel coordinates (top-left, bottom-right) |

#### Error Responses

| Status | Body |
|--------|------|
| `400`  | `{ "detail": "Invalid image data" }` |
| `500`  | `{ "detail": "Internal server error" }` |

---

## Session & Tracking Behavior

| Concept | Detail |
|---------|--------|
| **Session** | One `YOLO + ByteTrack` instance per session ID |
| **Persistence** | Same `session_id` across frames → same `track_id` for same object |
| **TTL** | Session auto-evicted after 600s (10 min) of inactivity |
| **Max sessions** | 32 concurrent sessions; oldest evicted when full |

```
Frame 1 → POST /detect (session_id="video_1") → track_id=1, track_id=2
Frame 2 → POST /detect (session_id="video_1") → track_id=1, track_id=2 (same IDs)
Frame 3 → POST /detect (session_id="video_1") → track_id=1, track_id=2, track_id=3
```

---

## Python Integration Example

```python
import requests

BASE = "https://tienpm205--trafficflow-inference-fastapi-app.modal.run"

with open("frame.jpg", "rb") as f:
    resp = requests.post(
        f"{BASE}/v1/detect",
        files={"image": f},
        data={"session_id": "video_1"},
    )

print(resp.json())
# {
#   "session_id": "video_1",
#   "detections": [
#     {"track_id": 1, "class_id": 2, "class_name": "car", "confidence": 0.93, "bbox_xyxy": [100.5, 200.3, 250.1, 350.7]}
#   ]
# }
```
