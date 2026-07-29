"""Read-only local dependency health check.

This command never writes objects to R2. Use it when validating an operator
environment before starting the
local stack.
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from motor.motor_asyncio import AsyncIOMotorClient
import redis

from shared.config import settings
from shared.r2_client import r2_client
from shared.safe_errors import safe_error_message

async def check_mongo():
    try:
        client = AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS,
            connectTimeoutMS=settings.MONGODB_CONNECT_TIMEOUT_MS,
        )
        await client.server_info()
        print("MongoDB: OK")
    except Exception as e:
        print(f"MongoDB: BLOCKED - {safe_error_message(e)}")
        return False
    return True

def check_redis():
    try:
        r = redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
            socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
        )
        r.ping()
        print("Redis (Celery broker): OK")
        return True
    except Exception as e:
        print(f"Redis (Celery broker): BLOCKED - {safe_error_message(e)}")
        return False

def check_r2():
    if settings.R2_ACCOUNT_ID.startswith("placeholder_"):
        print("Cloudflare R2: SKIPPED - placeholder credentials")
        return True
    try:
        r2_client.s3_client.head_bucket(Bucket=settings.R2_BUCKET_NAME)
        print("Cloudflare R2: OK")
        return True
    except Exception as exc:
        print(f"Cloudflare R2: BLOCKED - {safe_error_message(exc)}")
        return False

async def main():
    print("Checking local TrafficFlow dependencies...")
    results = [await check_mongo(), check_redis(), check_r2()]
    return 0 if all(results) else 1

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
