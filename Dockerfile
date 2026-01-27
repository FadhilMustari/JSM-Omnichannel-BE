FROM python:3.11-slim

WORKDIR /app

# Cloud Run logs/stdio + faster startup; PYTHONPATH needed because worker runs as a script.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

# Default: API service. For the worker service, override command/args to:
#   python scripts/outbox_worker.py
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]

