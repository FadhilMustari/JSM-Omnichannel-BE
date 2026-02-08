import contextvars
import json
import logging
import logging.config
import os
from datetime import datetime, timezone

_BUILTIN_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}

_trace_id_var = contextvars.ContextVar("trace_id", default=None)
_span_id_var = contextvars.ContextVar("span_id", default=None)
_trace_sampled_var = contextvars.ContextVar("trace_sampled", default=None)
_project_id: str | None = None


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "severity": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "time": datetime.now(timezone.utc).isoformat(),
        }

        trace_id = _trace_id_var.get()
        span_id = _span_id_var.get()
        sampled = _trace_sampled_var.get()

        if trace_id:
            project = _project_id or os.getenv("GOOGLE_CLOUD_PROJECT") or os.getenv("GCP_PROJECT")
            if project:
                payload["trace"] = f"projects/{project}/traces/{trace_id}"
            payload["traceId"] = trace_id
        if span_id:
            payload["spanId"] = span_id
        if sampled is not None:
            payload["trace_sampled"] = sampled

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        for key, value in record.__dict__.items():
            if key in _BUILTIN_ATTRS:
                continue
            payload[key] = _safe_json_value(value)

        return json.dumps(payload, ensure_ascii=False)


def _safe_json_value(value):
    try:
        json.dumps(value)
        return value
    except TypeError:
        return str(value)


def setup_logging(level: str = "INFO", project_id: str | None = None) -> None:
    global _project_id
    _project_id = project_id
    config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "json": {"()": "core.logging.JsonFormatter"},
        },
        "handlers": {
            "stdout": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "json",
            }
        },
        "root": {"level": level, "handlers": ["stdout"]},
        "loggers": {
            "uvicorn": {"level": level, "handlers": ["stdout"], "propagate": False},
            "uvicorn.error": {"level": level, "handlers": ["stdout"], "propagate": False},
            "uvicorn.access": {"level": "WARNING", "handlers": ["stdout"], "propagate": False},
        },
    }

    logging.config.dictConfig(config)


def set_trace_context(trace_id: str | None, span_id: str | None, sampled: bool | None) -> None:
    _trace_id_var.set(trace_id)
    _span_id_var.set(span_id)
    _trace_sampled_var.set(sampled)


def clear_trace_context() -> None:
    _trace_id_var.set(None)
    _span_id_var.set(None)
    _trace_sampled_var.set(None)
