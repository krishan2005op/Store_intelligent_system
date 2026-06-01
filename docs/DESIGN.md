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

## Module 5: Funnel Engine and Dataset Profile

The received dataset contains five short CCTV MP4 files, a Brigade Bangalore layout
workbook, POS order-line data, and an assessment framework. The project now includes
a dataset profile for `ST1008 / Brigade_Bangalore` that maps camera roles:

- `CAM 3`: entrance and exterior threshold
- `CAM 1`, `CAM 2`: sales floor and browsing
- `CAM 5`: billing/cash counter
- `CAM 4`: back/storage/staff area

The funnel engine exposes `GET /stores/{id}/funnel` and computes session progression
through entry, browse, dwell, billing intent, and purchase proxy stages. The current
purchase proxy is `BILLING_QUEUE_JOIN`; POS order data will later be linked by time
window once video-derived session timestamps are calibrated.

## Module 6: Anomaly Engine

The anomaly engine exposes `GET /stores/{id}/anomalies` and runs explainable,
dataset-independent baseline rules:

- `QUEUE_SPIKE`: maximum billing queue depth exceeds the configured warning or
  critical threshold.
- `CONVERSION_DROP`: conversion proxy falls below baseline after a minimum visitor
  count is reached.
- `DEAD_ZONE`: expected customer-facing zones show no observed customer activity
  once there is enough event volume to evaluate the window.

Every finding includes severity, observed and threshold values, optional `zone_id`,
metadata, and a suggested operational action. This is intentionally transparent so
reviewers can inspect and challenge assumptions during architecture discussion.

## Module 7: Real CCTV Pipeline MVP

The project now has a real-video execution path for the received Brigade Bangalore
CCTV files. `OpenCVVideoSource` reads MP4 metadata and sampled frames. The detector
factory uses YOLOv8 when configured, while the default local path uses a CPU-safe
OpenCV motion detector so the system can run before model weights are installed.

Camera roles from the dataset profile are mapped into structured retail events:

- entrance camera detections become `ENTRY`
- sales-floor detections become `ZONE_DWELL`
- billing camera detections become `BILLING_QUEUE_JOIN`
- back-area detections become staff `ZONE_ENTER`

The MVP writes a JSONL event stream that uses the same `RetailEvent` schema as the
API. This keeps real-video event generation compatible with ingestion, metrics,
funnel, anomaly, and dashboard modules.
