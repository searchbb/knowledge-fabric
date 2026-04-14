"""Common API DTOs for the Phase 2 scaffold."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ApiEnvelope(BaseModel):
    """Generic API response wrapper."""

    success: bool = True
    message: str = ""
    data: dict[str, Any] | list[Any] | None = None


class PaginationSchema(BaseModel):
    """Basic pagination metadata."""

    limit: int = Field(default=50, ge=1)
    offset: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)
