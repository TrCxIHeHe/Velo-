import logging

from fastapi import FastAPI, Request
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="Scooter Platform API",
        version="1.0.0",
        docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
        redoc_url=None,
    )

    # ── Global exception handler ──────────────────────────────────────────────
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException) -> JSONResponse:
        return error_response(exc.code, exc.message, exc.http_status)

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception: %s", exc)
        return error_response("INTERNAL_ERROR", "An unexpected error occurred.", 500)

    # ── Health check ──────────────────────────────────────────────────────────
    # Canonical health endpoint per docs/api/common.md's frozen Phase 1 contract.
    @app.get(f"{settings.API_V1_PREFIX}/health", tags=["health"])
    async def health():
        """Liveness probe. Returns 200 when the service is up."""
        return success_response({"status": "ok"})

    # Unversioned dev-convenience alias (Track B). Not part of the frozen
    # API contract — kept only for local/adminer-style smoke checks.
    @app.get("/", tags=["health"])
    async def root():
        return {"status": "ok"}

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
    app.include_router(ride_router, prefix=settings.API_V1_PREFIX)
    app.include_router(dock_router, prefix=settings.API_V1_PREFIX)
    app.include_router(wallet_router, prefix=settings.API_V1_PREFIX)
    app.include_router(admin_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
