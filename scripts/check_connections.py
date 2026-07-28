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
        print(f"MongoDB: BLOCKED - {e}")
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
        print(f"Redis (Celery broker): BLOCKED - {e}")
        return False

def check_r2():
    if settings.R2_ACCOUNT_ID.startswith("placeholder_"):
        print("Cloudflare R2: SKIPPED - placeholder credentials")
        return True
    print("Cloudflare R2: UNCHECKED - use the application health path for authorized storage validation")
    return True

async def main():
    print("Checking local TrafficFlow dependencies...")
    results = [await check_mongo(), check_redis(), check_r2()]
    return 0 if all(results) else 1

if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
