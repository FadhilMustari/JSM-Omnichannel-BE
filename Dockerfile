FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt .

RUN pip install --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Default: API service (Cloud Run Service). For a worker Cloud Run Service, override to:
#   uvicorn scripts.worker_service:app --host 0.0.0.0 --port ${PORT:-8080}
#
# For Cloud Run Jobs (no HTTP port needed), you can run:
#   python scripts/outbox_worker.py
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
