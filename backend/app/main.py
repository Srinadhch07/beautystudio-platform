"""FastAPI application factory and entrypoint."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import admin_router, auth_router, health_router, public_router
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.logging import configure_logging
from app.db.indexes import ensure_indexes
from app.db.mongo import close_database, get_database, init_database
from app.services.mail import is_email_configured
from app.storage.s3 import is_s3_configured

logger = logging.getLogger(__name__)

ALLOWED_METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"]
ALLOWED_HEADERS = [
    "Accept",
    "Authorization",
    "Content-Type",
    "X-CSRF-Token",
    "X-Requested-With",
]


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare shared resources on start-up and release them on shutdown."""
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info(
        "Starting %s v%s (environment=%s, api_prefix=%s)",
        settings.app_name,
        settings.app_version,
        settings.environment,
        settings.api_prefix,
    )

    # Infrastructure readiness is logged only - the app stays up either way.
    if await init_database(settings):
        await ensure_indexes(get_database())
    else:
        logger.warning(
            "MongoDB not reachable; indexes were not ensured and database features are unavailable."
        )

    logger.info(
        "Infrastructure flags: storage_mode=%s, s3_configured=%s, email_configured=%s",
        settings.storage_mode,
        is_s3_configured(settings),
        is_email_configured(settings),
    )

    # Configuration problems that silently weaken auth are logged loudly at
    # start-up, where an operator will see them, instead of at the first failed
    # login. The values themselves are never logged.
    for warning in settings.auth_transport_warnings():
        logger.warning("Authentication configuration: %s", warning)

    if not settings.is_auth_configured:
        logger.error(
            "Authentication is NOT usable: JWT_SECRET is missing or too short. "
            "All protected endpoints will reject every request until it is set."
        )

    try:
        yield
    finally:
        await close_database()
        logger.info("Shutdown complete")


def create_app() -> FastAPI:
    settings = get_settings()

    # The interactive docs and the raw schema describe every admin endpoint, so
    # they are served only outside production. Gated on the existing
    # ``environment`` derivation rather than a new setting, so ``DEBUG=false``
    # is the single switch.
    expose_docs = settings.environment == "development"

    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if expose_docs else None,
        redoc_url="/redoc" if expose_docs else None,
        openapi_url="/openapi.json" if expose_docs else None,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=ALLOWED_METHODS,
        allow_headers=ALLOWED_HEADERS,
    )

    install_exception_handlers(application)

    version_prefix = f"{settings.api_prefix}/v1"
    application.include_router(health_router, prefix=settings.api_prefix)
    application.include_router(auth_router, prefix=version_prefix)
    application.include_router(public_router, prefix=f"{version_prefix}/public")
    application.include_router(admin_router, prefix=f"{version_prefix}/admin")

    @application.get("/", include_in_schema=False)
    async def root() -> dict[str, str | None]:
        return {
            "app": settings.app_name,
            "version": settings.app_version,
            "docs": "/docs" if expose_docs else None,
            "health": settings.health_path,
            "public_api": f"{version_prefix}/public",
            "admin_api": f"{version_prefix}/admin",
        }

    return application


app = create_app()
