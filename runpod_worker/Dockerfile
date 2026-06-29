FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

# System deps
RUN apt-get update && apt-get install -y \
    ffmpeg wget curl git \
    libglib2.0-0 libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 libpango-1.0-0 \
    libcairo2 libx11-6 libx11-xcb1 libxcb1 libxext6 \
    && rm -rf /var/lib/apt/lists/*

COPY runpod_worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

# Copy full repo (handler imports backend modules)
COPY . .

ENV PYTHONPATH=/app

# Pre-download Whisper model (cached in image layer)
RUN python -c "import whisper; whisper.load_model('large-v3-turbo')"

# Pre-download YOLO base weights (custom model mounted at runtime via RunPod volume)
RUN python -c "from ultralytics import YOLO; YOLO('yolo11s.pt')"

CMD ["python", "-u", "runpod_worker/handler.py"]
