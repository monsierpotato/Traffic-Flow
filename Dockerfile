# Stage 1: Build React frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# Stage 2: Python app with GPU support via nvidia-container-toolkit
FROM python:3.12-slim

WORKDIR /app

# System deps for OpenCV + ffmpeg
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libglib2.0-0 libgomp1 libsm6 libxext6 ffmpeg nodejs \
        && rm -rf /var/lib/apt/lists/*

# Install torch CUDA 12.4 (compatible with RTX 5070 Ti via driver forward compat)
RUN pip install --no-cache-dir \
    torch --index-url https://download.pytorch.org/whl/cu124

# Install remaining deps
RUN pip install --no-cache-dir \
    ultralytics>=8.0.0 \
    fastapi>=0.110.0 \
    "uvicorn[standard]>=0.29.0" \
    motor>=3.3.0 \
    apscheduler>=3.10.0 \
    boto3>=1.34.0 \
    python-multipart>=0.0.9 \
    celery>=5.3.0 \
    redis>=5.0.0 \
    requests>=2.31.0 \
    urllib3>=2.0.0 \
    yt-dlp>=2025.0.0 \
    "opencv-python-headless==4.10.0.84" \
    numpy>=1.24.0 \
    "pydantic-settings>=2.0.0" \
    "python-dotenv>=0.21.0" \
    certifi>=2023.0.0 \
    scipy>=1.10.0 \
    lap>=0.5.12

# Ultralytics can pull the latest opencv-python (currently 5.x), which triggers
# cv::gemm crashes in the live YOLO/Kalman path. Force the known-stable build.
RUN pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless && \
    pip install --no-cache-dir "opencv-python-headless==4.10.0.84"

COPY src/ src/
COPY models/ models/
COPY --from=frontend-builder /frontend/dist/ frontend/dist/

RUN mkdir -p /app/storage/uploads /app/storage/previews /app/storage/results /app/storage/chunks

ENV PYTHONPATH=/app/src
ENV AI_LOCAL=true

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
