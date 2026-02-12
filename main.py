import logging
import time
from fastapi import FastAPI, Request
from dotenv import load_dotenv
from endpoints.webhook import router as webhook_router
from endpoints.jira_webhook import router as jira_webhook_router
from endpoints.admin import router as admin_router
from endpoints.auth import router as auth_router
from core.http_client import init_async_client, close_async_client
from core.config import settings
from core.logging import setup_logging, set_trace_context, clear_trace_context

load_dotenv()
setup_logging(settings.log_level, settings.gcp_project_id)
app = FastAPI()

app.include_router(jira_webhook_router)
app.include_router(webhook_router)
app.include_router(auth_router)
app.include_router(admin_router)

http_logger = logging.getLogger("http.request")

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

@app.on_event("shutdown")
async def shutdown() -> None:
    await close_async_client()

@app.get("/")
def root():
    return {"message": "Omnichannel BE running"}
