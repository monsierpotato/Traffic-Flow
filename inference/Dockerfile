FROM pytorch/pytorch:2.5.1-cuda12.4-cudnn9-runtime

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libgl1-mesa-glx \
        libglib2.0-0 \
        && rm -rf /var/lib/apt/lists/*

COPY inference/serving/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY inference/serving/ serving/
COPY src/tfengine/ tfengine/
COPY inference/models/ models/

ENV PYTHONPATH=/app

EXPOSE 8000

ENTRYPOINT ["python", "-m", "serving.app"]
CMD ["--model", "models/yolov8n.pt", "--device", "cpu", "--host", "0.0.0.0", "--port", "8000"]
