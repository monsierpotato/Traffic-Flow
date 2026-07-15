import copy
import json
import logging
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

import certifi
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from shared.config import settings

logger = logging.getLogger(__name__)


class _InsertOneResult:
    def __init__(self, inserted_id: Any):
        self.inserted_id = inserted_id


class _UpdateResult:
    def __init__(self, matched_count: int, modified_count: int, upserted_id: Any = None):
        self.matched_count = matched_count
        self.modified_count = modified_count
        self.upserted_id = upserted_id


class _DeleteResult:
    def __init__(self, deleted_count: int):
        self.deleted_count = deleted_count


class LocalCursor:
    def __init__(self, docs: List[dict]):
        self._docs = docs

    def sort(self, key: str, direction: int = 1):
        reverse = direction < 0
        self._docs.sort(key=lambda doc: doc.get(key), reverse=reverse)
        return self

    def limit(self, count: int):
        self._docs = self._docs[:count]
        return self

    async def to_list(self, length: Optional[int] = None):
        docs = self._docs if length is None else self._docs[:length]
        return copy.deepcopy(docs)


class LocalJsonCollection:
    def __init__(self, database: "LocalJsonDatabase", name: str):
        self._database = database
        self._name = name

    def _docs(self) -> List[dict]:
        return self._database._data.setdefault(self._name, [])

    def _matches(self, doc: dict, query: Optional[dict]) -> bool:
        if not query:
            return True
        for key, expected in query.items():
            actual = doc.get(key)
            if isinstance(expected, dict):
                if "$lt" in expected and not (actual is not None and actual < expected["$lt"]):
                    return False
                if "$lte" in expected and not (actual is not None and actual <= expected["$lte"]):
                    return False
                if "$gt" in expected and not (actual is not None and actual > expected["$gt"]):
                    return False
                if "$gte" in expected and not (actual is not None and actual >= expected["$gte"]):
                    return False
                if "$in" in expected and actual not in expected["$in"]:
                    return False
            elif actual != expected:
                return False
        return True

    async def insert_one(self, doc: dict):
        async with self._database.lock:
            stored = copy.deepcopy(doc)
            stored.setdefault("_id", self._database.next_id())
            self._docs().append(stored)
            self._database.save()
            return _InsertOneResult(stored["_id"])

    async def insert_many(self, docs: Iterable[dict]):
        inserted = []
        async with self._database.lock:
            for doc in docs:
                stored = copy.deepcopy(doc)
                stored.setdefault("_id", self._database.next_id())
                self._docs().append(stored)
                inserted.append(stored["_id"])
            self._database.save()
        return type("InsertManyResult", (), {"inserted_ids": inserted})()

    async def find_one(self, query: Optional[dict] = None):
        async with self._database.lock:
            for doc in self._docs():
                if self._matches(doc, query):
                    return copy.deepcopy(doc)
        return None

    def find(self, query: Optional[dict] = None):
        docs = [copy.deepcopy(doc) for doc in self._docs() if self._matches(doc, query)]
        return LocalCursor(docs)

    async def update_one(self, query: dict, update: dict, upsert: bool = False):
        async with self._database.lock:
            for doc in self._docs():
                if self._matches(doc, query):
                    if "$set" in update:
                        doc.update(copy.deepcopy(update["$set"]))
                    else:
                        doc.update(copy.deepcopy(update))
                    self._database.save()
                    return _UpdateResult(1, 1)
            if upsert:
                new_doc = copy.deepcopy(query)
                if "$set" in update:
                    new_doc.update(copy.deepcopy(update["$set"]))
                else:
                    new_doc.update(copy.deepcopy(update))
                new_doc.setdefault("_id", self._database.next_id())
                self._docs().append(new_doc)
                self._database.save()
                return _UpdateResult(0, 0, new_doc["_id"])
        return _UpdateResult(0, 0)

    async def delete_many(self, query: Optional[dict] = None):
        async with self._database.lock:
            original = len(self._docs())
            self._database._data[self._name] = [doc for doc in self._docs() if not self._matches(doc, query)]
            deleted = original - len(self._database._data[self._name])
            self._database.save()
            return _DeleteResult(deleted)

    async def count_documents(self, query: Optional[dict] = None):
        async with self._database.lock:
            return sum(1 for doc in self._docs() if self._matches(doc, query))

    def aggregate(self, pipeline: list):
        return LocalCursor([])


class LocalJsonDatabase:
    def __init__(self, path: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.lock = _AsyncThreadLock()
        self._counter = 0
        self._data: Dict[str, List[dict]] = {}
        self.load()

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        return LocalJsonCollection(self, name)

    def __getitem__(self, name: str):
        return LocalJsonCollection(self, name)

    def next_id(self) -> str:
        self._counter += 1
        return f"local-{self._counter}"

    def load(self):
        if self.path.exists():
            try:
                payload = json.loads(self.path.read_text(encoding="utf-8"))
                self._counter = int(payload.get("_counter", 0))
                self._data = {k: v for k, v in payload.items() if k != "_counter"}
            except Exception as exc:
                logger.warning("Could not read local DB %s: %s", self.path, exc)
                self._data = {}

    def save(self):
        payload = {"_counter": self._counter, **self._data}
        self.path.write_text(json.dumps(payload, default=str, ensure_ascii=False, indent=2), encoding="utf-8")


class _AsyncThreadLock:
    def __init__(self):
        self._lock = threading.RLock()

    async def __aenter__(self):
        self._lock.acquire()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        self._lock.release()


class Database:
    client: Optional[AsyncIOMotorClient] = None
    db = None
    using_local_fallback: bool = False


db_instance = Database()


async def connect_to_mongo():
    logger.info("Connecting to MongoDB Atlas...")
    client = AsyncIOMotorClient(
        settings.MONGODB_URI,
        tlsCAFile=certifi.where(),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
    )
    try:
        await client.admin.command("ping")
        db_instance.client = client
        db_instance.db = client[settings.MONGODB_DB_NAME]
        db_instance.using_local_fallback = False
        logger.info("Connected to MongoDB successfully!")
    except (ServerSelectionTimeoutError, PyMongoError, OSError) as exc:
        client.close()
        if not settings.MONGODB_LOCAL_FALLBACK:
            raise
        db_instance.client = None
        db_instance.db = LocalJsonDatabase(settings.LOCAL_DB_PATH)
        db_instance.using_local_fallback = True
        logger.warning(
            "MongoDB unavailable (%s). Falling back to local JSON DB at %s",
            exc,
            settings.LOCAL_DB_PATH,
        )


async def close_mongo_connection():
    logger.info("Closing MongoDB connection...")
    if db_instance.client:
        db_instance.client.close()
        logger.info("MongoDB connection closed.")
    db_instance.client = None


def get_database():
    """Dependency helper to retrieve the database instance."""
    return db_instance.db
