FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TF_CPP_MIN_LOG_LEVEL=2 \
    DEEPFACE_HOME=/app/model \
    TZ=Asia/Kuala_Lumpur \
    FACE_ENGINE=deepface

# libglib is the one system library headless OpenCV needs; tzdata so class times use Malaysia time
RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt requirements-nodeps.txt ./
RUN pip install -r requirements.txt \
    && pip install --no-deps -r requirements-nodeps.txt

# Download the face model at build time so containers start without fetching weights
RUN python -c "from deepface import DeepFace; DeepFace.build_model('Facenet')"

COPY . .

# Cloud Run provides $PORT. One worker keeps a single copy of the model in memory;
# threads let the app serve pages while a scan is running.
CMD exec gunicorn --bind :${PORT:-8080} --workers 1 --threads 4 --timeout 120 app:app
