"""Upgrade legacy non-unique indexes to the production uniqueness contract.

Dry-run is the default. Use --apply only against an approved staging/production
maintenance window after taking a backup.
"""

from __future__ import annotations

import argparse
import os

from pymongo import MongoClient

from shared.config import settings


DESIRED = {
    "tasks": [("task_id",), ("video_id",)],
    "lane_configs": [("task_id",), ("video_id",)],
    "live_sources": [("source_id",)],
    "live_sessions": [("session_id",)],
    "traffic_statistics": [("task_id", "lane_id", "vehicle_type", "direction")],
}


def duplicate_count(collection, fields: tuple[str, ...]) -> int:
    rows = collection.aggregate([
        {"$group": {"_id": {field: f"${field}" for field in fields}, "count": {"$sum": 1}}},
        {"$match": {"count": {"$gt": 1}}},
        {"$count": "duplicates"},
    ])
    first = next(iter(rows), None)
    return int((first or {}).get("duplicates", 0))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="drop conflicting non-unique indexes and create unique ones")
    args = parser.parse_args()
    uri = os.environ.get("MONGODB_URI", settings.MONGODB_URI)
    client = MongoClient(uri, serverSelectionTimeoutMS=settings.MONGODB_SERVER_SELECTION_TIMEOUT_MS)
    db = client[os.environ.get("MONGODB_DB_NAME", settings.MONGODB_DB_NAME)]

    actions = []
    for collection_name, fields_list in DESIRED.items():
        collection = db[collection_name]
        indexes = collection.index_information()
        for fields in fields_list:
            key = tuple((field, 1) for field in fields)
            existing = [
                (name, spec)
                for name, spec in indexes.items()
                if tuple(spec.get("key", [])) == key
            ]
            if any(spec.get("unique") for _, spec in existing):
                continue
            duplicates = duplicate_count(collection, fields)
            if duplicates:
                raise RuntimeError(f"{collection_name} {fields} has {duplicates} duplicate groups; cleanup is required first")
            actions.append((collection, collection_name, fields, [name for name, _ in existing]))

    for collection, collection_name, fields, old_names in actions:
        new_name = "uq_" + collection_name + "_" + "_".join(fields)
        print(f"{collection_name}: {fields} -> {new_name}; old={old_names or 'none'}")
        if args.apply:
            for old_name in old_names:
                if old_name != "_id_":
                    collection.drop_index(old_name)
            collection.create_index([(field, 1) for field in fields], unique=True, name=new_name)
    if not args.apply and actions:
        print("Dry-run only. Re-run with --apply during an approved maintenance window.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
