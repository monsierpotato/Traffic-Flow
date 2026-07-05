import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from lib.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    
    print("=== ALL TASKS ===")
    async for task in db.tasks.find({}):
        print(f"Task ID: {task.get('task_id')}")
        print(f"  video_id: {task.get('video_id')}")
        print(f"  status: {task.get('status')}")
        print(f"  progress: {task.get('progress')}")
        print(f"  created_at: {task.get('created_at')}")
        print(f"  updated_at: {task.get('updated_at')}")
        print(f"  error_message: {task.get('error_message')}")
        print()
        
    print("=== ALL LANE CONFIGS ===")
    async for config in db.lane_configs.find({}):
        print(f"Task ID: {config.get('task_id')}")
        print(f"  video_id: {config.get('video_id')}")
        print(f"  lanes: {config.get('lanes')}")
        print()

    print("=== ALL TRAFFIC STATISTICS ===")
    async for stat in db.traffic_statistics.find({}):
        print(stat)

if __name__ == "__main__":
    asyncio.run(main())
