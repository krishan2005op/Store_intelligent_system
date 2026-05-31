from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated, Any, Self
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def utc_now() -> datetime:
    return datetime.now(UTC)


class EventType(StrEnum):
    ENTRY = "ENTRY"
    EXIT = "EXIT"
    ZONE_ENTER = "ZONE_ENTER"
    ZONE_EXIT = "ZONE_EXIT"
    ZONE_DWELL = "ZONE_DWELL"
    BILLING_QUEUE_JOIN = "BILLING_QUEUE_JOIN"
    BILLING_QUEUE_ABANDON = "BILLING_QUEUE_ABANDON"
    REENTRY = "REENTRY"


class PersonType(StrEnum):
    CUSTOMER = "CUSTOMER"
    STAFF = "STAFF"
    UNKNOWN = "UNKNOWN"


class EventSource(StrEnum):
    SIMULATOR = "SIMULATOR"
    REALTIME_PIPELINE = "REALTIME_PIPELINE"
    BATCH_REPLAY = "BATCH_REPLAY"
    MANUAL_FIXTURE = "MANUAL_FIXTURE"


Confidence = Annotated[float, Field(ge=0.0, le=1.0)]
NonNegativeInt = Annotated[int, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class BoundingBox(BaseModel):
    model_config = ConfigDict(frozen=True)

    x: Annotated[float, Field(ge=0.0)]
    y: Annotated[float, Field(ge=0.0)]
    width: Annotated[float, Field(gt=0.0)]
    height: Annotated[float, Field(gt=0.0)]


class EventMetadata(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True)

    occlusion_ratio: Annotated[float | None, Field(ge=0.0, le=1.0)] = None
    camera_overlap_group: str | None = None
    paired_camera_id: str | None = None
    scenario: str | None = None
    queue_depth: NonNegativeInt | None = None
    dwell_seconds: Annotated[float | None, Field(ge=0.0)] = None
    detector_version: str | None = None
    tracker_version: str | None = None


class RetailEvent(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)

    event_id: UUID = Field(default_factory=uuid4)
    store_id: UUID
    camera_id: str = Field(min_length=1, max_length=128)
    event_type: EventType
    occurred_at: datetime = Field(default_factory=utc_now)
    source: EventSource = EventSource.SIMULATOR
    confidence: Confidence
    sequence_number: NonNegativeInt
    session_id: UUID = Field(default_factory=uuid4)
    track_id: str | None = Field(default=None, max_length=128)
    global_person_id: str | None = Field(default=None, max_length=128)
    person_type: PersonType = PersonType.CUSTOMER
    zone_id: str | None = Field(default=None, max_length=128)
    bbox: BoundingBox | None = None
    metadata: EventMetadata = Field(default_factory=EventMetadata)

    @field_validator("occurred_at")
    @classmethod
    def ensure_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("occurred_at must include timezone information")
        return value.astimezone(UTC)

    @field_validator("camera_id", "track_id", "global_person_id", "zone_id")
    @classmethod
    def strip_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @model_validator(mode="after")
    def validate_event_semantics(self) -> Self:
        zone_event_types = {
            EventType.ZONE_ENTER,
            EventType.ZONE_EXIT,
            EventType.ZONE_DWELL,
            EventType.BILLING_QUEUE_JOIN,
            EventType.BILLING_QUEUE_ABANDON,
        }
        if self.event_type in zone_event_types and not self.zone_id:
            raise ValueError(f"{self.event_type} requires zone_id")

        if self.event_type == EventType.ZONE_DWELL and self.metadata.dwell_seconds is None:
            raise ValueError("ZONE_DWELL requires metadata.dwell_seconds")

        if self.event_type in {
            EventType.BILLING_QUEUE_JOIN,
            EventType.BILLING_QUEUE_ABANDON,
        } and self.metadata.queue_depth is None:
            raise ValueError(f"{self.event_type} requires metadata.queue_depth")

        return self


class EventIngestRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    events: list[RetailEvent] = Field(min_length=1, max_length=1_000)

    @property
    def event_count(self) -> int:
        return len(self.events)


class EventIngestResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_id: UUID
    accepted: bool
    duplicate: bool = False
    error_code: str | None = None
    message: str | None = None


class EventIngestResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: UUID
    accepted_count: NonNegativeInt
    duplicate_count: NonNegativeInt
    rejected_count: NonNegativeInt
    results: list[EventIngestResult]


class StructuredError(BaseModel):
    model_config = ConfigDict(extra="forbid")

    trace_id: UUID
    code: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
