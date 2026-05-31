from __future__ import annotations

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FunnelStage(StrEnum):
    ENTRY = "ENTRY"
    BROWSE = "BROWSE"
    DWELL = "DWELL"
    BILLING_INTENT = "BILLING_INTENT"
    PURCHASE_PROXY = "PURCHASE_PROXY"


class FunnelStageMetric(BaseModel):
    model_config = ConfigDict(extra="forbid")

    stage: FunnelStage
    count: int = Field(ge=0)
    conversion_from_previous: float = Field(ge=0.0, le=1.0)
    conversion_from_entry: float = Field(ge=0.0, le=1.0)
    dropoff_from_previous: int = Field(ge=0)


class FunnelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: UUID
    stages: list[FunnelStageMetric]
    entry_sessions: int = Field(ge=0)
    completed_sessions: int = Field(ge=0)
    reentry_sessions: int = Field(ge=0)
    staff_sessions_excluded: int = Field(ge=0)
    overall_conversion_rate: float = Field(ge=0.0, le=1.0)
    notes: list[str] = Field(default_factory=list)
