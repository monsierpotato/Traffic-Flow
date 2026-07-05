import logging
from datetime import datetime
from lib.database import db_instance
from lib.r2_client import r2_client

logger = logging.getLogger(__name__)

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

        # 1. Delete original video
        video_key = f"uploads/{video_id}.mp4"
        try:
            r2_client.delete_file(video_key)
        except Exception as e:
            logger.warning(f"Could not delete original video {video_key}: {str(e)}")

        # 2. Delete preview frame
        preview_key = f"previews/{video_id}.jpg"
        try:
            r2_client.delete_file(preview_key)
        except Exception as e:
            logger.warning(f"Could not delete preview frame {preview_key}: {str(e)}")

        # 3. Delete result video and events if task was completed
        if task.get("result_video_url"):
            result_video_key = f"results/{task_id}/output.mp4"
            try:
                r2_client.delete_file(result_video_key)
            except Exception as e:
                logger.warning(f"Could not delete result video {result_video_key}: {str(e)}")

        if task.get("events_url"):
            events_key = f"results/{task_id}/events.jsonl"
            try:
                r2_client.delete_file(events_key)
            except Exception as e:
                logger.warning(f"Could not delete events log {events_key}: {str(e)}")

        # 4. Update MongoDB Task document: clear file references and mark as archived
        await db.tasks.update_one(
            {"task_id": task_id},
            {
                "$set": {
                    "video_url": None,
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
