"""Schemas for the health endpoint."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Static success payload. Contains no configuration or secrets."""

    status: Literal["ok"]
    app: str
    version: str
    environment: str
