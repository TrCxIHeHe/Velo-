import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.config import settings
from app.dock.router import router as dock_router
from app.ride.router import router as ride_router
from app.wallet.router import router as wallet_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Velo backend starting up — env=%s", settings.ENVIRONMENT)
    yield
    logger.info("Velo backend shutting down")


app = FastAPI(
    title="Velo — Smart Micromobility API",
    version="1.0.0",
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten per-env in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception on %s %s", request.method, request.url)
    return JSONResponse(
        status_code=500,
        content={"success": False, "error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred."}},
    )


prefix = settings.API_V1_PREFIX

app.include_router(auth_router, prefix=prefix)
app.include_router(ride_router, prefix=prefix)
app.include_router(dock_router, prefix=prefix)
app.include_router(wallet_router, prefix=prefix)
app.include_router(admin_router, prefix=prefix)


@app.get("/health")
async def health():
    return {"status": "ok"}
