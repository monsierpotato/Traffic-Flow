import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from lib.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    
    task_id = "8d09401f-d689-4901-bc13-28e69d22db92"
    
    # 1. Print Task info
    task = await db.tasks.find_one({"task_id": task_id})
    print("=== TASK ===")
    if task:
        for k, v in task.items():
            print(f"{k}: {v}")
    else:
        print("Task not found")
        
    # 2. Print Lane Config info
    lane_config = await db.lane_configs.find_one({"task_id": task_id})
    print("\n=== LANE CONFIG ===")
    if lane_config:
        for k, v in lane_config.items():
            if k == 'lanes':
                print(f"{k}:")
                for lane in v:
                    print(f"  - {lane}")
            else:
                print(f"{k}: {v}")
    else:
        print("Lane config not found")
        
    # 3. Print Traffic Statistics
    print("\n=== TRAFFIC STATISTICS ===")
    async for stat in db.traffic_statistics.find({"task_id": task_id}):
        print(stat)

if __name__ == "__main__":
    asyncio.run(main())
