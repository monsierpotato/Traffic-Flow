import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from lib.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    
    await db.tasks.delete_many({})
    await db.lane_configs.delete_many({})
    await db.traffic_statistics.delete_many({})
    print("Database cleared successfully!")

if __name__ == "__main__":
    asyncio.run(main())
