from fastapi import FastAPI

from app.wallet.router import router as wallet_router

app = FastAPI(title="Velo Backend")


@app.get("/")
def root():
    return {"status": "ok"}


app.include_router(wallet_router, prefix="/api/v1")