import asyncio
import os

from fastapi import FastAPI

from scripts.outbox_worker import process_outbox

app = FastAPI()


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.on_event("startup")
async def startup() -> None:
    shutdown_event: asyncio.Event = asyncio.Event()
    app.state.shutdown_event = shutdown_event
    app.state.worker_task = asyncio.create_task(_run_worker(shutdown_event))


@app.on_event("shutdown")
async def shutdown() -> None:
    shutdown_event: asyncio.Event = app.state.shutdown_event
    shutdown_event.set()

    worker_task: asyncio.Task = app.state.worker_task
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass


async def _run_worker(shutdown_event: asyncio.Event) -> None:
    batch_size = int(os.getenv("WORKER_BATCH_SIZE", "10"))
    poll_seconds = float(os.getenv("WORKER_POLL_SECONDS", "1"))

    while not shutdown_event.is_set():
        processed = await asyncio.to_thread(process_outbox, limit=batch_size)
        await asyncio.sleep(0.1 if processed else poll_seconds)

