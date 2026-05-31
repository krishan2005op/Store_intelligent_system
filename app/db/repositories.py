from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import RetailEventRecord
from pipeline.schemas import RetailEvent


class EventRepository(Protocol):
    async def existing_event_ids(self, event_ids: Iterable[UUID]) -> set[UUID]:
        """Return event IDs already persisted."""

    async def add_events(self, events: list[RetailEvent]) -> None:
        """Persist accepted events atomically."""

    async def latest_event_at(self, store_id: UUID | None = None) -> datetime | None:
        """Return the newest event timestamp for feed freshness checks."""

    async def list_events_for_store(
        self,
        store_id: UUID,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[RetailEvent]:
        """Return events for one store in chronological order."""


class SQLAlchemyEventRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def existing_event_ids(self, event_ids: Iterable[UUID]) -> set[UUID]:
        ids = list(event_ids)
        if not ids:
            return set()

        statement: Select[tuple[UUID]] = select(RetailEventRecord.event_id).where(
            RetailEventRecord.event_id.in_(ids)
        )
        result = await self._session.execute(statement)
        return set(result.scalars().all())

    async def add_events(self, events: list[RetailEvent]) -> None:
        if not events:
            return

        self._session.add_all([RetailEventRecord.from_schema(event) for event in events])
        await self._session.commit()

    async def latest_event_at(self, store_id: UUID | None = None) -> datetime | None:
        statement = select(func.max(RetailEventRecord.occurred_at))
        if store_id is not None:
            statement = statement.where(RetailEventRecord.store_id == store_id)
        result = await self._session.execute(statement)
        return result.scalar_one_or_none()

    async def list_events_for_store(
        self,
        store_id: UUID,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
    ) -> list[RetailEvent]:
        statement = select(RetailEventRecord).where(RetailEventRecord.store_id == store_id)
        if start_at is not None:
            statement = statement.where(RetailEventRecord.occurred_at >= start_at)
        if end_at is not None:
            statement = statement.where(RetailEventRecord.occurred_at <= end_at)
        statement = statement.order_by(
            RetailEventRecord.occurred_at.asc(),
            RetailEventRecord.sequence_number.asc(),
        )

        result = await self._session.execute(statement)
        return [record.to_schema() for record in result.scalars().all()]
