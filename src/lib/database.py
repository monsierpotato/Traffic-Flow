import logging
import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from lib.config import settings

logger = logging.getLogger(__name__)

class Database:
    client: AsyncIOMotorClient = None
    db = None

db_instance = Database()

async def connect_to_mongo():
    logger.info("Connecting to MongoDB Atlas...")
    db_instance.client = AsyncIOMotorClient(settings.MONGODB_URI, tlsCAFile=certifi.where())
    db_instance.db = db_instance.client[settings.MONGODB_DB_NAME]
    logger.info("Connected to MongoDB successfully!")

async def close_mongo_connection():
    logger.info("Closing MongoDB connection...")
    if db_instance.client:
        db_instance.client.close()
        logger.info("MongoDB connection closed.")

def get_database():
    """Dependency helper to retrieve the database instance."""
    return db_instance.db
