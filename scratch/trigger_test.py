import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
import requests

async def main():
    client = AsyncIOMotorClient('mongodb+srv://Phuc:iloveyasuo@traffic-flow.zzjhldc.mongodb.net/?appName=Traffic-flow')
    db = client['trafficflow']
    
    # Update status to configured
    await db.tasks.update_one(
        {'task_id': '01ce3c23-6ba7-428f-bafb-928a881bb8fa'}, 
        {'$set': {'status': 'configured'}}
    )
    print('Updated status of 01ce3c23-6ba7-428f-bafb-928a881bb8fa to configured')
    
    # Trigger processing
    url = 'http://localhost:8000/api/v1/tasks/process'
    r = requests.post(url, json={'video_id': 'f4e8c88e-1aaa-4bcc-b24d-28cd4b96c143'})
    print(r.status_code, r.text)

if __name__ == '__main__':
    asyncio.run(main())
