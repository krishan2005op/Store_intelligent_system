# Technical Choices

This document records architecture tradeoffs as the implementation grows.

## Module 1

- Configuration uses `python-dotenv` and a frozen dataclass rather than framework-specific
  global settings. This keeps startup explicit and easy to test.
- Event schemas live in `pipeline.schemas` and are re-exported by `app.schemas` because the
  pipeline owns event production while the API owns ingestion.
- Structured logs are configured once through `structlog` with request context binding hooks
  ready for middleware in the API module.

## Module 2

- Heavy CV libraries are imported lazily inside real adapters. This keeps tests and
  simulator mode CPU-compatible and avoids failing startup before model assets exist.
- The simulator returns the same `RetailEvent` schema as the real pipeline will produce.
  This makes API, DB, metrics, anomaly detection, and dashboard development independent
  from dataset arrival.
- ByteTrack and TorchReID wrappers are intentionally adapter-shaped now. Their internals
  will become dataset-aware after frame rate, camera layout, and sample footage are known.

## Module 3

- Repository protocol keeps API/service tests independent from PostgreSQL while preserving
  the same behavior expected from the production SQLAlchemy repository.
- Idempotency is based on `event_id` because upstream pipeline retries should be safe and
  deterministic. Session-level deduplication belongs in the metrics layer, not ingestion.
- Health reports stale feeds using the latest event timestamp. Empty feeds are not marked
  stale because a newly deployed store may legitimately have no events yet.

## Module 4

- Metrics are derived from stored immutable events instead of separate mutable counters.
  This keeps the first implementation auditable and replay-friendly.
- Conversion is currently modeled as customers who joined the billing queue divided by
  unique customer visitors. A future POS integration can replace this with completed
  purchase events without changing the route contract.
- Heatmap intensity combines zone event count and dwell seconds, then normalizes against
  the strongest zone for the requested store/time window.
