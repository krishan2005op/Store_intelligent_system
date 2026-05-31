from __future__ import annotations

import asyncio

from app.core.config import get_settings
from pipeline.config import get_simulation_seed
from pipeline.emit import EventSink, InMemoryEventSink
from pipeline.simulator import build_default_simulator


async def run_simulation_once(sink: EventSink | None = None) -> InMemoryEventSink | EventSink:
    settings = get_settings()
    target_sink = sink or InMemoryEventSink()
    simulator = build_default_simulator(settings.default_store_id, seed=get_simulation_seed())
    await target_sink.emit(simulator.generate_batch())
    return target_sink


def main() -> None:
    asyncio.run(run_simulation_once())


if __name__ == "__main__":
    main()
