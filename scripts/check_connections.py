import asyncio
import time
from motor.motor_asyncio import AsyncIOMotorClient
import redis
import boto3
from botocore.config import Config
import sys; sys.path.insert(0, "src")
from lib.config import settings

async def check_mongo():
    try:
        client = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=5000)
        await client.server_info()
        print("MongoDB: OK")
    except Exception as e:
        print(f"MongoDB: Error - {e}")

def check_redis():
    max_retries = 3
    for i in range(max_retries):
        try:
            r = redis.from_url(settings.REDIS_URL, socket_connect_timeout=5)
            r.ping()
            print("Redis (Celery broker): OK")
            return
        except Exception as e:
            if i == max_retries - 1:
                print(f"Redis (Celery broker): Error - {e}")
            time.sleep(2)

def check_r2():
    try:
        endpoint_url = f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
        s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=settings.R2_ACCESS_KEY_ID,
            aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
            config=Config(signature_version="s3v4"),
            region_name="auto"
        )
        # Test by putting a dummy object
        s3.put_object(Bucket=settings.R2_BUCKET_NAME, Key="test_connection.txt", Body=b"test")
        s3.delete_object(Bucket=settings.R2_BUCKET_NAME, Key="test_connection.txt")
        print("Cloudflare R2: OK")
    except Exception as e:
        print(f"Cloudflare R2: Error - {e}")

async def main():
    print("Checking connections again...")
    await check_mongo()
    check_redis()
    check_r2()

if __name__ == "__main__":
    asyncio.run(main())
