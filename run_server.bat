@echo off
echo Starting FastAPI Server...
set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=1
set PYTHONPATH=src
.venv\Scripts\python.exe -m uvicorn api.app:create_app --factory --host 0.0.0.0 --port 8000
pause

