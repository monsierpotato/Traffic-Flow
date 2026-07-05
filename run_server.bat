@echo off
echo Starting FastAPI Server...
set OPENBLAS_NUM_THREADS=1
set OMP_NUM_THREADS=1
set PYTHONPATH=src
.venv\Scripts\python.exe -m api.main
pause
