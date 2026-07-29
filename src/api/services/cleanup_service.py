import logging
import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from datetime import datetime
from pathlib import Path
from shared.database import db_instance
from shared.r2_client import r2_client
from shared.safe_errors import safe_error_message
from shared.config import settings

logger = logging.getLogger(__name__)


def _delete_keys_sync(keys: list[tuple[str, str]]) -> None:
    for key, label in keys:
        if not key:
            continue
        try:
            r2_client.delete_file(key)
        except Exception as e:
            logger.warning("Could not delete %s %s: %s", label, key, safe_error_message(e))


async def _delete_keys(keys: list[tuple[str, str]]) -> None:
    if keys:
        # Keep one executor submission per cleanup run. Repeated
        # run_in_executor calls can deadlock under the constrained Python
        # runtime used by the local fallback tests.
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="trafficflow-cleanup") as executor:
            await loop.run_in_executor(executor, partial(_delete_keys_sync, keys))

async def run_data_cleanup():
    """Finds expired tasks, deletes associated video/preview files from Cloudflare R2,
    and updates task metadata while keeping statistical summaries.
    """
    logger.info("Starting data retention cleanup job...")
    db = db_instance.db
    if db is None:
        logger.error("Database connection not initialized. Skipping cleanup.")
        return

    now = datetime.utcnow()
    # Query tasks that have expired and have not been cleaned up yet (i.e. status isn't "archived")
    query = {
        "expires_at": {"$lt": now},
        "status": {"$ne": "archived"}
    }

    cursor = db.tasks.find(query)
    expired_tasks = await cursor.to_list(length=100)

    if not expired_tasks:
        logger.info("No expired files to clean up.")
        return

    logger.info(f"Found {len(expired_tasks)} expired tasks to clean up.")

    cleanup_items = []
    r2_deletions: list[tuple[str, str]] = []
    for task in expired_tasks:
        task_id = task.get("task_id") or task.get("video_id")
        video_id = task.get("video_id") or task.get("task_id")
        if not task_id or not video_id:
            logger.warning("Skipping expired task without usable identifiers")
            continue
        logger.info(f"Cleaning files for task {task_id} (video {video_id})")

        # 1. Delete upload and preview assets. Prefer metadata keys, keep legacy fallbacks.
        keys = {
            task.get("original_video_key"),
            task.get("working_video_key"),
            task.get("preview_key"),
            f"uploads/{video_id}.mp4",
            f"uploads/{video_id}_1080p.mp4",
            f"previews/{video_id}.jpg",
        }
        r2_deletions.extend((key, "task asset") for key in keys if key)

        if task.get("result_video_url"):
            result_video_key = task.get("result_video_key") or f"results/{task_id}.mp4"
            r2_deletions.extend(
                (
                    (result_video_key, "result video"),
                    (f"results/{task_id}/output.mp4", "legacy result video"),
                )
            )

        if task.get("events_url"):
            events_key = task.get("events_key") or f"results/{task_id}/events.jsonl"
            r2_deletions.append((events_key, "events log"))

        cleanup_items.append((task, task_id, video_id))

    await _delete_keys(r2_deletions)

    for task, task_id, video_id in cleanup_items:

        try:
            (Path(settings.STORAGE_DIR) / "previews" / f"{video_id}.jpg").unlink(missing_ok=True)
        except OSError as exc:
            logger.warning(
                "Could not delete local preview for video %s: %s",
                video_id,
                safe_error_message(exc),
            )

        # Update MongoDB Task document: clear file references and mark as archived
        await db.tasks.update_one(
            {"task_id": task_id} if task.get("task_id") else {"video_id": video_id},
            {
                "$set": {
                    "video_url": None,
                    "working_video_url": None,
                    "original_video_url": None,
                    "preview_url": None,
                    "result_video_url": None,
                    "events_url": None,
                    "status": "archived",
                    "updated_at": datetime.utcnow()
                }
            }
        )
        logger.info(f"Task {task_id} files successfully cleaned and task archived.")

    logger.info("Data retention cleanup job finished.")
