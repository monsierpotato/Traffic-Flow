@echo off
echo Starting Celery worker...
echo Note: Using --pool=solo because Celery prefork is not fully supported on Windows.
.venv\Scripts\celery.exe -A backend.core.celery_app worker --pool=solo -l info
pause
