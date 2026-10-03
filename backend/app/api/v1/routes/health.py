"""Liveness endpoint."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import SettingsDependency
from app.schemas.health import HealthResponse

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness probe",
    description="Returns a static success payload. Performs no database or network I/O.",
)
async def health(settings: SettingsDependency) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
    )
