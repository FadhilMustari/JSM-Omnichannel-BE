# JSM-Omnichannel-BE

Backend service for omnichannel webhook handling (WhatsApp/Telegram/LINE), session management, and AI-assisted replies.

## Prerequisites

- Python 3.10+
- Postgres (or compatible DB for SQLAlchemy)

## Setup

1. Create and activate a virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Create `.env` file for local development (see variables below).
4. Run migrations:
   ```bash
   alembic upgrade head
   ```

## Required Environment Variables

Local development: set these in `.env` (and optionally `.env.local`) or export them in your shell.

Production (Cloud Run): set environment variables in Cloud Run (do not rely on `.env`).
`BASE_URL` is required in production to generate absolute links and webhook URLs.

```
ENVIRONMENT=development
PORT=8000
BASE_URL=
DATABASE_URL=
JIRA_BASE=
JIRA_EMAIL=
JIRA_TOKEN=
JIRA_SERVICE_DESK_ID=
SMTP_HOST=
SMTP_PORT=
SMTP_USERNAME=
SMTP_PASSWORD=
SMTP_FROM_EMAIL=
SMTP_USE_TLS=true
WHATSAPP_TOKEN=
WHATSAPP_PHONE_NUMBER_ID=
WHATSAPP_APP_SECRET=
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
LLM_API_KEY=
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
RATE_LIMIT_WINDOW_SECONDS=60
RATE_LIMIT_MAX=30
```

## Webhook Endpoint

The service exposes:

```
POST /webhook/{platform}
```

Supported platforms: `whatsapp`, `telegram`, `line`.

## Webhook Setup

Point each platform webhook to:

```
{BASE_URL}/webhook/{platform}
```

Telegram:

- Use BotFather to create a bot and get `TELEGRAM_BOT_TOKEN`.
- Set webhook URL to `{BASE_URL}/webhook/telegram` and configure `TELEGRAM_WEBHOOK_SECRET`.
  Example:
  ```bash
  curl -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook" \
       -d "url=${BASE_URL}/webhook/telegram" \
       -d "secret_token=${TELEGRAM_WEBHOOK_SECRET}"
  ```

LINE:

- Create a LINE Messaging API channel and get `LINE_CHANNEL_ACCESS_TOKEN` and `LINE_CHANNEL_SECRET`.
- Set webhook URL to `{BASE_URL}/webhook/line`.
  Example:
  ```bash
  curl -X POST "https://api.line.me/v2/bot/channel/webhook/endpoint" \
       -H "Authorization: Bearer ${LINE_CHANNEL_ACCESS_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{"endpoint":"'"${BASE_URL}/webhook/line"'"}'
  ```

WhatsApp Cloud API:

- Create a Meta App and WhatsApp Business account to get `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, and `WHATSAPP_APP_SECRET`.
- Set webhook URL to `{BASE_URL}/webhook/whatsapp`.
  Example:
  ```bash
  curl -X POST "https://graph.facebook.com/v17.0/${WHATSAPP_PHONE_NUMBER_ID}/webhooks" \
       -H "Authorization: Bearer ${WHATSAPP_TOKEN}" \
       -H "Content-Type: application/json" \
       -d '{"url":"'"${BASE_URL}/webhook/whatsapp"'","verify_token":"your_verify_token"}'
  ```

## Running the App

Start the API:

```bash
uvicorn main:app --reload
```

Start the outbox worker (separate terminal):

```bash
PYTHONPATH=. python scripts/outbox_worker.py
```

## Running with Docker Compose

- External DB (recommended): set `DATABASE_URL` in `.env` to your external Postgres, then run:
  - `docker compose up --build`
- Local Postgres in Docker: run with the extra compose file:
  - `docker compose -f docker-compose.yml -f docker-compose.localdb.yml up --build`

## Deploying API + Worker (Cloud Run)

- API: deploy as a Cloud Run Service using the default container command.
- Worker:
  - Recommended: deploy as a Cloud Run Job with command `python scripts/outbox_worker.py`, or
  - Alternative (Cloud Run Service): deploy with command `uvicorn scripts.worker_service:app --host 0.0.0.0 --port $PORT`.

## Notes

- The worker processes queued replies from the outbox table. Keep it running in production.
- If you update the database schema, re-run `alembic upgrade head`.
