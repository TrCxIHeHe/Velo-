from fastapi import FastAPI

from app.config import settings
from app.dock.router import router as dock_router
from app.wallet.router import router as wallet_router

app = FastAPI(title="Velo Backend — Track B")


@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.ENVIRONMENT}


app.include_router(wallet_router, prefix=settings.API_V1_PREFIX)
app.include_router(dock_router, prefix=settings.API_V1_PREFIX)
