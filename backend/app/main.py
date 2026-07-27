import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.config import settings
from app.core.exceptions import AppException
from app.core.response import error_response, success_response
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


def create_app() -> FastAPI:
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

    # ── Global exception handlers ───────────────────────────────────────────────
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return error_response(exc.code, exc.message, exc.http_status)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", 500)

    # ── Health checks ────────────────────────────────────────────────────────────
    # Canonical health endpoint per docs/api/common.md's frozen Phase 1 contract.
    @app.get(f"{settings.API_V1_PREFIX}/health", tags=["health"])
    async def health_v1():
        """Liveness probe. Returns 200 when the service is up."""
        return success_response({"status": "ok"})

    # Unversioned alias — kept for load balancers / uptime checks that expect
    # a bare /health path, and for local smoke checks.
    @app.get("/health", tags=["health"])
    async def health():
        return {"status": "ok"}

    # ── Routers ──────────────────────────────────────────────────────────────────
    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(ride_router, prefix=settings.API_V1_PREFIX)
    app.include_router(dock_router, prefix=settings.API_V1_PREFIX)
    app.include_router(wallet_router, prefix=settings.API_V1_PREFIX)
    app.include_router(admin_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
