from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, Float, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import JSON

from pipeline.schemas import BoundingBox, EventMetadata, RetailEvent


class Base(DeclarativeBase):
    pass


class RetailEventRecord(Base):
    __tablename__ = "retail_events"
    __table_args__ = (
        Index("ix_retail_events_store_occurred_at", "store_id", "occurred_at"),
        Index("ix_retail_events_store_event_type", "store_id", "event_type"),
        Index("ix_retail_events_session_sequence", "session_id", "sequence_number"),
    )

    event_id: Mapped[UUID] = mapped_column(primary_key=True)
    store_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    camera_id: Mapped[str] = mapped_column(String(128), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    session_id: Mapped[UUID] = mapped_column(index=True, nullable=False)
    track_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    global_person_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    person_type: Mapped[str] = mapped_column(String(32), nullable=False)
    zone_id: Mapped[str | None] = mapped_column(String(128), index=True, nullable=True)
    bbox: Mapped[dict[str, Any] | None] = mapped_column(JSON().with_variant(JSONB, "postgresql"))
    event_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSON().with_variant(JSONB, "postgresql"),
        nullable=False,
        default=dict,
    )

    @classmethod
    def from_schema(cls, event: RetailEvent) -> RetailEventRecord:
        return cls(
            event_id=event.event_id,
            store_id=event.store_id,
            camera_id=event.camera_id,
            event_type=str(event.event_type),
            occurred_at=event.occurred_at,
            source=str(event.source),
            confidence=event.confidence,
            sequence_number=event.sequence_number,
            session_id=event.session_id,
            track_id=event.track_id,
            global_person_id=event.global_person_id,
            person_type=str(event.person_type),
            zone_id=event.zone_id,
            bbox=event.bbox.model_dump(mode="json") if event.bbox else None,
            event_metadata=event.metadata.model_dump(mode="json", exclude_none=True),
        )

    def to_schema(self) -> RetailEvent:
        return RetailEvent(
            event_id=self.event_id,
            store_id=self.store_id,
            camera_id=self.camera_id,
            event_type=self.event_type,
            occurred_at=self.occurred_at,
            source=self.source,
            confidence=self.confidence,
            sequence_number=self.sequence_number,
            session_id=self.session_id,
            track_id=self.track_id,
            global_person_id=self.global_person_id,
            person_type=self.person_type,
            zone_id=self.zone_id,
            bbox=BoundingBox.model_validate(self.bbox) if self.bbox else None,
            metadata=EventMetadata.model_validate(self.event_metadata),
        )
