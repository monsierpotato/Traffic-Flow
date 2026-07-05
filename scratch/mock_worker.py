import os
import sys
import time
import httpx
from pymongo import MongoClient

# Add root folder to sys.path to resolve imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Simple script to simulate worker progress updates and completion callbacks
# Running this script helps test the PUT /progress callback and GET /result endpoints.

def main():
    backend_url = "http://localhost:8000"
    mongo_uri = "mongodb://localhost:27017/"
    
    # 1. Connect to MongoDB to find the latest queued/pending task
    print("Connecting to MongoDB...")
    client = MongoClient(mongo_uri)
    db = client["trafficflow"]
    
    # Find the latest pending task
    task = db.tasks.find_one({"status": "pending"})
    if not task:
        # Fallback to any configured/uploaded task for manual testing
        task = db.tasks.find_one({"status": {"$in": ["configured", "uploaded"]}})
        if not task:
            print("No tasks found in database! Please upload a video and run the process endpoint first.")
            return
        else:
            print(f"No pending task, using task found with status '{task['status']}': {task['task_id']}")
    else:
        print(f"Found pending task: {task['task_id']}")
        
    task_id = task["task_id"]
    
    # 2. Simulate processing phases (10% to 90%)
    for pct in [10, 30, 60, 90]:
        print(f"Simulating processing progress: {pct}%...")
        payload = {
            "status": "processing",
            "progress": pct
        }
        res = httpx.put(f"{backend_url}/api/v1/tasks/progress/{task_id}", json=payload)
        print(f"Progress callback response: {res.status_code}")
        time.sleep(2)
        
    # 3. Simulate uploading output files (create mock output files locally under static dir)
    print("Simulating R2 upload of processed video and event logs...")
    # Ensure local mockup folders exist
    os.makedirs("../storage/results", exist_ok=True)
    os.makedirs(f"../storage/results/{task_id}", exist_ok=True)
    
    # Write empty placeholder files for mock verification
    with open(f"../storage/results/{task_id}/output.mp4", "wb") as f:
        f.write(b"MOCK_PROCESSED_VIDEO_BYTES")
    with open(f"../storage/results/{task_id}/events.jsonl", "wb") as f:
        f.write(b'{"timestamp": 123456.78, "lane": "1", "vehicle": "car"}\n')
        
    # Mock URLs (mock R2 serving locally via FastAPI static route)
    result_video_url = f"{backend_url}/static/results/{task_id}/output.mp4"
    events_url = f"{backend_url}/static/results/{task_id}/events.jsonl"
    
    # 4. Final completion callback with mock counting statistics
    print("Sending completion callback with counting statistics...")
    payload = {
        "status": "completed",
        "progress": 100,
        "result_video_url": result_video_url,
        "events_url": events_url,
        "statistics": [
            {"lane_id": "lane-1", "vehicle_type": "car", "count": 42, "direction": "in"},
            {"lane_id": "lane-1", "vehicle_type": "truck", "count": 8, "direction": "in"},
            {"lane_id": "lane-1", "vehicle_type": "motorbike", "count": 156, "direction": "in"},
            {"lane_id": "lane-2", "vehicle_type": "car", "count": 31, "direction": "out"},
            {"lane_id": "lane-2", "vehicle_type": "bus", "count": 3, "direction": "out"},
            {"lane_id": "lane-2", "vehicle_type": "motorbike", "count": 97, "direction": "out"}
        ]
    }
    
    res = httpx.put(f"{backend_url}/api/v1/tasks/progress/{task_id}", json=payload)
    print(f"Final callback status response: {res.status_code}")
    print(res.json())
    print(f"Task {task_id} marked as completed. You can now call GET /api/v1/tasks/result/{task_id} to fetch details.")

if __name__ == "__main__":
    main()
