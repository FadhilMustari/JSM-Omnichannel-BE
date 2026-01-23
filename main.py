from fastapi import FastAPI
from endpoints.webhook import router as webhook_router
from endpoints.auth import router as auth_router

app = FastAPI()

app.include_router(webhook_router)
app.include_router(auth_router)

@app.get("/")
def root():
    return {"message": "Omnichannel BE running"}
