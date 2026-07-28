import logging
import json
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from shared.database import db_instance
from shared.config import settings
from shared.r2_client import r2_client

logger = logging.getLogger(__name__)


def _delete_key(key: str, label: str):
    if not key:
        return
    try:
        r2_client.delete_file(key)
    except Exception as e:
        logger.warning(f"Could not delete {label} {key}: {str(e)}")

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

    for task in expired_tasks:
        task_id = task["task_id"]
        video_id = task["video_id"]
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
        for key in keys:
            _delete_key(key, "task asset")

        # 3. Delete result video and events if task was completed
        if task.get("result_video_url"):
            result_video_key = task.get("result_video_key") or f"results/{task_id}.mp4"
            _delete_key(result_video_key, "result video")
            _delete_key(f"results/{task_id}/output.mp4", "legacy result video")

        if task.get("events_url"):
            events_key = task.get("events_key") or f"results/{task_id}/events.jsonl"
            _delete_key(events_key, "events log")

        # 4. Update MongoDB Task document: clear file references and mark as archived
        await db.tasks.update_one(
            {"task_id": task_id},
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
async def cleanup_expired_chunk_sessions() -> int:
    """Remove abandoned resumable-upload sessions and their temporary files."""
    chunk_dir = Path(settings.STORAGE_DIR) / "chunks"
    if not chunk_dir.exists():
        return 0
    cutoff = datetime.utcnow() - timedelta(seconds=settings.CHUNK_SESSION_TTL_SECONDS)
    removed = 0
    for upload_dir in chunk_dir.iterdir():
        if not upload_dir.is_dir():
            continue
        meta_path = upload_dir / "meta.json"
        try:
            created_at = datetime.fromisoformat(json.loads(meta_path.read_text(encoding="utf-8")).get("created_at", ""))
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            created_at = datetime.utcfromtimestamp(upload_dir.stat().st_mtime)
        if created_at < cutoff:
            shutil.rmtree(upload_dir, ignore_errors=True)
            removed += 1
    if removed:
        logger.info("Removed %s expired chunk upload sessions", removed)
    return removed


async def reconcile_stale_tasks():
    """Mark jobs that stopped reporting progress as failed and recoverable.

    Celery is configured to requeue jobs lost with a worker process, but a
    callback can still be interrupted after the worker finishes. This small
    reconciliation pass prevents the UI from displaying an endless spinner.
    """
    db = db_instance.db
    if db is None:
        return 0

    cutoff = datetime.utcnow() - timedelta(seconds=settings.TASK_STALE_TIMEOUT_SECONDS)
    cursor = db.tasks.find({
        "status": {"$in": ["pending", "processing"]},
        "updated_at": {"$lt": cutoff},
    })
    stale_tasks = await cursor.to_list(length=100)
    for task in stale_tasks:
        await db.tasks.update_one(
            {
                "task_id": task.get("task_id"),
                "status": {"$in": ["pending", "processing"]},
            },
            {
                "$set": {
                    "status": "failed",
                    "stage": "stale_task_reconciled",
                    "stage_detail": "No worker progress was received before the task timeout",
                    "error_message": "Task timed out waiting for worker progress",
                    "updated_at": datetime.utcnow(),
                }
            },
        )
    if stale_tasks:
        logger.warning("Reconciled %s stale processing tasks", len(stale_tasks))
    return len(stale_tasks)
