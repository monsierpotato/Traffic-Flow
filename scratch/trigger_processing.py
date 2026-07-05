import requests
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from lib.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    
    # Find latest task
    task = await db.tasks.find_one({}, sort=[('_id', -1)])
    if not task:
        print("No task found in database")
        return
        
    task_id = task.get("task_id")
    video_id = task.get("video_id")
    status = task.get("status")
    print(f"Latest task in DB: task_id={task_id}, video_id={video_id}, status={status}")
    
    # We will trigger processing via the API
    url = "http://localhost:8000/api/v1/tasks/process"
    payload = {"video_id": video_id}
    print(f"Sending POST to {url} with payload {payload}...")
    try:
        r = requests.post(url, json=payload, timeout=10)
        print("Status Code:", r.status_code)
        print("Response:", r.text)
    except Exception as e:
        print("Failed to trigger:", e)

if __name__ == "__main__":
    asyncio.run(main())
