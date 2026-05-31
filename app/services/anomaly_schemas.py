from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AnomalyType(StrEnum):
    QUEUE_SPIKE = "QUEUE_SPIKE"
    CONVERSION_DROP = "CONVERSION_DROP"
    DEAD_ZONE = "DEAD_ZONE"


class AnomalySeverity(StrEnum):
    INFO = "INFO"
    WARN = "WARN"
    CRITICAL = "CRITICAL"


class AnomalyFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    anomaly_id: str
    type: AnomalyType
    severity: AnomalySeverity
    title: str
    description: str
    suggested_action: str
    observed_value: float = Field(ge=0.0)
    threshold_value: float = Field(ge=0.0)
    zone_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnomalyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    store_id: UUID
    generated_at: datetime
    anomaly_count: int = Field(ge=0)
    anomalies: list[AnomalyFinding]
