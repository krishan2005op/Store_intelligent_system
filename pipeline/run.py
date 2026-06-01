from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from pipeline.config import get_simulation_seed
from pipeline.dataset_runner import run_brigade_dataset_pipeline
from pipeline.emit import EventSink, InMemoryEventSink
from pipeline.simulator import build_default_simulator


logger = get_logger(__name__)


async def run_simulation_once(sink: EventSink | None = None) -> InMemoryEventSink | EventSink:
    settings = get_settings()
    target_sink = sink or InMemoryEventSink()
    simulator = build_default_simulator(settings.default_store_id, seed=get_simulation_seed())
    await target_sink.emit(simulator.generate_batch())
    return target_sink


async def _run_dataset(args: argparse.Namespace) -> None:
    configure_logging(get_settings())
    result = await run_brigade_dataset_pipeline(
        dataset_dir=Path(args.dataset_dir),
        output_path=Path(args.output),
    )
    logger.info(
        "dataset_pipeline_completed",
        event_count=result.event_count,
        video_count=len(result.video_metadata),
        output_path=str(result.output_path),
    )


async def _run_ingest(args: argparse.Namespace) -> None:
    configure_logging(get_settings())
    from pipeline.dataset_runner import load_events_from_jsonl
    events = load_events_from_jsonl(Path(args.file))
    if not events:
        logger.warning("no_events_found", file=args.file)
        return

    logger.info("loading_events", file=args.file, total_count=len(events))

    if args.api_url:
        import httpx

        from pipeline.schemas import EventIngestRequest

        batch_size = 200
        async with httpx.AsyncClient(timeout=30.0) as client:
            for i in range(0, len(events), batch_size):
                batch = events[i:i + batch_size]
                payload = EventIngestRequest(events=batch).model_dump(mode="json")
                response = await client.post(
                    f"{args.api_url.rstrip('/')}/events/ingest",
                    json=payload,
                )
                if response.status_code != 202:
                    logger.error(
                        "api_ingestion_failed",
                        status_code=response.status_code,
                        body=response.text,
                    )
                    return
                logger.info(
                    "ingested_batch",
                    start=i,
                    end=min(i + batch_size, len(events)),
                )
    else:
        from app.db.session import AsyncSessionFactory
        from app.db.repositories import SQLAlchemyEventRepository
        from app.services.ingestion_service import IngestionService

        async with AsyncSessionFactory() as session:
            repo = SQLAlchemyEventRepository(session)
            service = IngestionService(repo)
            result = await service.ingest_events(events)
            logger.info(
                "db_ingestion_completed",
                accepted=result.accepted_count,
                duplicates=result.duplicate_count,
                rejected=result.rejected_count,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Store intelligence pipeline runner")
    subparsers = parser.add_subparsers(dest="command")

    dataset_parser = subparsers.add_parser(
        "dataset",
        help="Run the real-video MVP pipeline against the Brigade CCTV folder.",
    )
    dataset_parser.add_argument("--dataset-dir", required=True)
    dataset_parser.add_argument(
        "--output",
        default="artifacts/events/brigade_events.jsonl",
    )

    ingest_parser = subparsers.add_parser(
        "ingest",
        help="Load events from a JSONL file into the database or API.",
    )
    ingest_parser.add_argument("--file", required=True, help="Path to JSONL event file.")
    ingest_parser.add_argument(
        "--api-url",
        default=None,
        help="If provided, ingest via this API endpoint (e.g. http://127.0.0.1:8000).",
    )

    args = parser.parse_args()
    if args.command == "dataset":
        asyncio.run(_run_dataset(args))
    elif args.command == "ingest":
        asyncio.run(_run_ingest(args))
    else:
        asyncio.run(run_simulation_once())


if __name__ == "__main__":
    main()
