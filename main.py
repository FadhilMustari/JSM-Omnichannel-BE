from fastapi import FastAPI
from endpoints.webhook import router as webhook_router
from endpoints.admin import router as admin_router
from endpoints.auth import router as auth_router
from core.http_client import init_async_client, close_async_client

app = FastAPI()

app.include_router(webhook_router)
app.include_router(auth_router)
app.include_router(admin_router)

@app.on_event("startup")
async def startup() -> None:
    init_async_client()

@app.on_event("shutdown")
async def shutdown() -> None:
    await close_async_client()

@app.get("/")
def root():
    return {"message": "Omnichannel BE running"}
