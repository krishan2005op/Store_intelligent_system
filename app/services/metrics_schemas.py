from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class StoreMetricsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: UUID
    event_count: int = Field(ge=0)
    unique_visitors: int = Field(ge=0)
    staff_event_count: int = Field(ge=0)
    conversion_rate: float = Field(ge=0.0, le=1.0)
    avg_dwell_seconds: float = Field(ge=0.0)
    current_queue_depth: int = Field(ge=0)
    max_queue_depth: int = Field(ge=0)
    abandonment_rate: float = Field(ge=0.0, le=1.0)
    reentry_count: int = Field(ge=0)
    active_sessions: int = Field(ge=0)


class HeatmapCell(BaseModel):
    model_config = ConfigDict(extra="forbid")

    zone_id: str
    event_count: int = Field(ge=0)
    dwell_seconds: float = Field(ge=0.0)
    normalized_intensity: float = Field(ge=0.0, le=1.0)


class HeatmapResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: UUID
    cells: list[HeatmapCell]
