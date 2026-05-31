# Store Intelligence Platform Design

This document will be expanded module-by-module. Module 1 establishes the service
boundaries, configuration contract, structured logging setup, and event schema
language shared by the detection pipeline and API.

## AI-Assisted Decisions

- Start dataset-agnostic with simulator-compatible schemas and dependency injection seams.
- Keep pipeline schemas importable by the API to avoid drift between producers and consumers.
- Use CPU-safe defaults until real video, model weights, and deployment hardware are known.

## Module 2: Pipeline Abstractions and Simulator

The detection layer is split into `Detector`, `Tracker`, `ReIDManager`, and
`ZoneResolver` contracts. Real implementations are kept behind lazy imports so local
simulation and API development do not require GPU libraries or model weights.

The simulator emits validated `RetailEvent` objects for realistic pre-dataset cases:
group entry, re-entry, staff movement, partial occlusion, empty-store intervals,
queue buildup, queue abandonment, and overlapping front-door cameras.

## Module 3: Ingestion API and Persistence Boundary

FastAPI now exposes `POST /events/ingest` and `GET /health`. Ingestion is handled
through an `IngestionService` and `EventRepository` protocol so the production
PostgreSQL implementation can be swapped for an in-memory implementation in tests.

The service performs idempotent ingestion by checking duplicate `event_id` values
inside the request and against storage. Structured responses preserve per-event
results in request order, which is important for pipeline replay and partial retry.

SQLAlchemy models and an Alembic baseline migration define the `retail_events`
table with uniqueness on `event_id` plus indexes for store/time, event type,
session sequencing, zone, and global person identity.

## Module 4: Metrics Engine

Metrics are computed in `MetricsService` from the event repository rather than in
route handlers. The service currently supports unique visitors, conversion rate,
average dwell, current and maximum queue depth, queue abandonment, active sessions,
reentry count, staff filtering, and heatmap normalization.

Customer-facing metrics exclude `STAFF` events. Unique visitors are deduplicated by
`global_person_id` when available and fall back to `session_id`. This mirrors the
future real pipeline where ReID may not be available for every track.
