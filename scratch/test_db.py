import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import pprint
from lib.config import settings

async def main():
    client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = client[settings.MONGODB_DB_NAME]
    task = await db.tasks.find_one({}, sort=[('_id', -1)])
    if not task:
        print('No tasks')
        return
    task_id = task['task_id']
    print('Task ID:', task_id)
    config = await db.lane_configs.find_one({'task_id': task_id})
    print('Config:')
    pprint.pprint(config)

asyncio.run(main())
