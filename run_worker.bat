@echo off
echo Starting Celery worker...
echo Note: Using --pool=solo because Celery prefork is not fully supported on Windows.
set PYTHONPATH=src
.venv\Scripts\celery.exe -A worker.celery_app worker --pool=solo -l info
pause
