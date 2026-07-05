import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import sys; sys.path.insert(0, "src")
from lib.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    
    # Print counts
    task_count = await db.tasks.count_documents({})
    lane_count = await db.lane_configs.count_documents({})
    stat_count = await db.traffic_statistics.count_documents({})
    
    print("=== Collection Counts ===")
    print(f"Tasks: {task_count}")
    print(f"Lane Configs: {lane_count}")
    print(f"Traffic Statistics: {stat_count}")
    print()
    
    # Latest Task
    task = await db.tasks.find_one({}, sort=[('_id', -1)])
    print("=== Latest Task ===")
    if task:
        print(f"task_id: {task.get('task_id')}")
        print(f"video_id: {task.get('video_id')}")
        print(f"status: {task.get('status')}")
    else:
        print("No task found")
    print()
        
    # Latest Lane Config
    lane_config = await db.lane_configs.find_one({}, sort=[('_id', -1)])
    print("=== Latest Lane Config ===")
    if lane_config:
        print(f"video_id: {lane_config.get('video_id')}")
        print(f"task_id: {lane_config.get('task_id')}")
        print(f"keys: {list(lane_config.keys())}")
    else:
        print("No lane config found")
    print()

    # Latest Traffic Statistic
    stat = await db.traffic_statistics.find_one({}, sort=[('_id', -1)])
    print("=== Latest Traffic Statistic ===")
    if stat:
        print(f"task_id: {stat.get('task_id')}")
        print(f"lane_id: {stat.get('lane_id')}")
        print(f"vehicle_type: {stat.get('vehicle_type')}")
        print(f"count: {stat.get('count')}")
    else:
        print("No traffic statistic found")
    print()

if __name__ == "__main__":
    asyncio.run(main())
