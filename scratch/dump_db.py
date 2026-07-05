import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from lib.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    
    print("=== TASKS ===")
    async for task in db.tasks.find({}):
        print(f"Task ID: {task.get('task_id')}")
        print(f"  Video ID: {task.get('video_id')}")
        print(f"  Status: {task.get('status')}")
        print(f"  Progress: {task.get('progress')}")
        print(f"  Created At: {task.get('created_at')}")
        print(f"  Updated At: {task.get('updated_at')}")
        print(f"  Result Video: {task.get('result_video_url')}")
        print(f"  Events: {task.get('events_url')}")
        print(f"  Error: {task.get('error_message')}")
        print("-" * 40)
        
    print("\n=== LANE CONFIGS ===")
    async for cfg in db.lane_configs.find({}):
        print(f"Video ID: {cfg.get('video_id')}")
        print(f"  Task ID: {cfg.get('task_id')}")
        print(f"  Lanes count: {len(cfg.get('lanes', [])) if cfg.get('lanes') else 0}")
        print("-" * 40)

    print("\n=== TRAFFIC STATISTICS ===")
    async for stat in db.traffic_statistics.find({}):
        print(f"Task ID: {stat.get('task_id')}")
        print(f"  Lane ID: {stat.get('lane_id')}")
        print(f"  Vehicle Type: {stat.get('vehicle_type')}")
        print(f"  Count: {stat.get('count')}")
        print(f"  Direction: {stat.get('direction')}")
        print("-" * 40)

if __name__ == "__main__":
    asyncio.run(main())
