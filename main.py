import asyncio
import logging
import time
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from endpoints.webhooks import router as webhook_router
from endpoints.auth import router as auth_router
from endpoints.dashboard.conversations import router as conversations_router
from endpoints.dashboard.tickets import router as tickets_router
from endpoints.dashboard.organizations import router as organizations_router
from endpoints.dashboard.stats import router as stats_router
from endpoints.broadcast import router as broadcast_router
from endpoints.sync import router as sync_router
from core.http_client import init_async_client, close_async_client
from core.config import settings
from core.logging import setup_logging, set_trace_context, clear_trace_context
from core.database import SessionLocal
from services.jira_service import JiraService
from services.jira_sync_service import JiraSyncService

load_dotenv()
setup_logging(settings.log_level, settings.gcp_project_id)
app = FastAPI()

app.include_router(webhook_router)
app.include_router(auth_router)
app.include_router(conversations_router)
app.include_router(tickets_router)
app.include_router(organizations_router)
app.include_router(stats_router)
app.include_router(sync_router)
app.include_router(broadcast_router)

http_logger = logging.getLogger("http.request")
sync_task: asyncio.Task | None = None

async def _run_periodic_sync() -> None:
    while True:
        await asyncio.sleep(60 * 60 * 24)
        try:
            db = SessionLocal()
            sync_service = JiraSyncService(JiraService())
            await sync_service.sync_jira_organizations_and_users(db)
            await sync_service.sync_jira_tickets(db)
        except Exception:
            logging.getLogger(__name__).exception("JSM periodic sync failed")
        finally:
            try:
                db.close()
            except Exception:
                pass

@app.middleware("http")
async def trace_context_middleware(request: Request, call_next):
    header = request.headers.get("X-Cloud-Trace-Context")
    trace_id = None
    span_id = None
    sampled = None
    if header:
        try:
            trace_part, *rest = header.split("/")
            trace_id = trace_part or None
            if rest:
                span_part = rest[0]
                if ";" in span_part:
                    span_part, options = span_part.split(";", 1)
                    if options.startswith("o="):
                        sampled = options[2:] == "1"
                span_id = span_part or None
        except ValueError:
            trace_id = None
            span_id = None
            sampled = None

    set_trace_context(trace_id, span_id, sampled)
    start = time.perf_counter()
    try:
        response = await call_next(request)
        return response
    finally:
        duration = time.perf_counter() - start
        request_size = request.headers.get("content-length")
        response_size = None
        try:
            response_size = response.headers.get("content-length") if "response" in locals() else None
        except Exception:
            response_size = None
        http_request = {
            "requestMethod": request.method,
            "requestUrl": str(request.url),
            "status": getattr(response, "status_code", None) if "response" in locals() else 500,
            "userAgent": request.headers.get("user-agent"),
            "remoteIp": request.client.host if request.client else None,
            "referer": request.headers.get("referer"),
            "protocol": f"HTTP/{request.scope.get('http_version', '1.1')}",
            "latency": f"{duration:.6f}s",
        }
        if request_size:
            http_request["requestSize"] = request_size
        if response_size:
            http_request["responseSize"] = response_size
        http_logger.info("HTTP request", extra={"httpRequest": http_request})
        clear_trace_context()

@app.on_event("startup")
async def startup() -> None:
    settings.validate_runtime()
    init_async_client()
    try:
        db = SessionLocal()
        sync_service = JiraSyncService(JiraService())
        await sync_service.sync_jira_organizations_and_users(db)
        await sync_service.sync_jira_tickets(db)
    except Exception:
        logging.getLogger(__name__).exception("JSM sync on startup failed")
    finally:
        try:
            db.close()
        except Exception:
            pass
    global sync_task
    sync_task = asyncio.create_task(_run_periodic_sync())

@app.on_event("shutdown")
async def shutdown() -> None:
    global sync_task
    if sync_task:
        sync_task.cancel()
        sync_task = None
    await close_async_client()

@app.get("/healthz")
def root():
    return {"message": "Omnichannel BE running"}
