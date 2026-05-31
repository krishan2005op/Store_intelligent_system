from __future__ import annotations

from typing import Protocol

from pipeline.schemas import RetailEvent


class EventSink(Protocol):
    async def emit(self, events: list[RetailEvent]) -> None:
        """Send structured events to the next system boundary."""


class InMemoryEventSink:
    def __init__(self) -> None:
        self.events: list[RetailEvent] = []

    async def emit(self, events: list[RetailEvent]) -> None:
        self.events.extend(events)
