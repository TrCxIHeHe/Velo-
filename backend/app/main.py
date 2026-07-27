import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.config import settings
from app.core.exceptions import AppException
from app.core.rate_limit import limiter
from app.core.response import error_response, success_response
from app.core.security_headers import SecurityHeadersMiddleware
from app.dock.router import router as dock_router
from app.notifications.router import router as notifications_router
from app.payments.router import router as payments_router
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

    # CORS_ORIGINS="*" is dev-only shorthand. Wildcard origin + credentialed
    # requests is a spec violation browsers reject anyway, so credentials are
    # only enabled once real origins are configured.
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    is_wildcard = origins == ["*"]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=not is_wildcard,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)

    app.state.limiter = limiter
    app.add_exception_handler(
        RateLimitExceeded,
        lambda request, exc: error_response("RATE_LIMITED", "Too many requests. Try again shortly.", 429),
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
    app.include_router(payments_router, prefix=settings.API_V1_PREFIX)
    app.include_router(notifications_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()
