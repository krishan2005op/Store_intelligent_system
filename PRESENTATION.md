# Store Intelligence Platform

## CCTV-to-Retail Analytics System

**Submission Theme:** AI / Computer Vision / Retail Analytics  
**Store Dataset:** Store 1 `ST1008` and Store 2 `ST1076`  
**Stack:** FastAPI, PostgreSQL, Redis, Docker, OpenCV, YOLO-ready pipeline, WebSockets

---

## Problem

Retail stores have CCTV footage, but most of it is not converted into useful operational intelligence.

The goal is to transform raw multi-camera footage into metrics that store teams can act on:

- How many unique visitors entered?
- Where did shoppers spend time?
- Did customers reach billing?
- Where did shoppers drop off?
- Is the billing queue building up?
- Are there dead zones in the store?

---

## Solution

The project builds a production-oriented Store Intelligence Platform:

```text
Raw CCTV Video
-> Detection Pipeline
-> Structured Retail Events
-> FastAPI Ingestion API
-> PostgreSQL Event Store
-> Metrics / Funnel / Anomaly Services
-> Live Dashboard
```

The system is designed to work before and after dataset arrival:

- simulation mode for development
- real MP4 pipeline for received CCTV footage
- adapter interfaces for YOLO, ByteTrack, and ReID integration

---

## Dataset Used

Received dataset includes:

- Store 1 CCTV: `CAM 1 - zone.mp4`, `CAM 2 - zone.mp4`, `CAM 3 - entry.mp4`,
  and `CAM 5 - billing.mp4`
- Store 1 layout image and POS/order CSV for `ST1008`
- Store 2 CCTV: `entry 1.mp4`, `entry 2.mp4`, `zone.mp4`, and `billing_area.mp4`
- Store 2 layout image and sample JSONL events for `ST1076`

Dataset profile:

```text
Store 1 / ST1008:
CAM 1, CAM 2 -> sales floor zones
CAM 3 -> entrance
CAM 5 -> billing / cash counter

Store 2 / ST1076:
entry 1, entry 2 -> entrance coverage
zone -> sales floor zones
billing_area -> billing queue
```

---

## Core Events

The pipeline produces typed retail events:

```text
ENTRY
EXIT
ZONE_ENTER
ZONE_EXIT
ZONE_DWELL
BILLING_QUEUE_JOIN
BILLING_QUEUE_ABANDON
REENTRY
```

Each event includes:

- UUID event ID
- store ID
- camera ID
- timestamp
- confidence score
- session ID
- track/person identity
- zone ID
- bounding box
- metadata

---

## Architecture

```text
pipeline/
  detect.py        Detector interfaces and YOLO/OpenCV/mock implementations
  tracker.py       Tracker interfaces and ByteTrack/mock adapters
  reid.py          ReID interfaces and TorchReID/mock adapters
  simulator.py     Deterministic simulation event stream
  dataset_runner.py Real CCTV MP4 processing

app/
  routes/          FastAPI endpoints
  services/        Business logic
  db/              SQLAlchemy models, repositories, migrations
  core/            Config, logging, dataset profile

dashboard/
  templates/
  static/
```

The design separates pipeline, ingestion, storage, business logic, and dashboard.

---

## API Endpoints

Implemented endpoints:

```text
GET  /health
POST /events/ingest
GET  /stores/{id}/metrics
GET  /stores/{id}/heatmap
GET  /stores/{id}/funnel
GET  /stores/{id}/anomalies
GET  /dashboard
WS   /stores/{id}/live
```

The API supports:

- idempotent ingestion
- duplicate event handling
- structured error responses
- async SQLAlchemy
- request trace IDs
- structured logging

---

## Metrics Engine

The metrics service computes:

- unique visitors
- active sessions
- conversion rate
- average dwell time
- current queue depth
- maximum queue depth
- abandonment rate
- re-entry count
- heatmap intensity

Staff events are excluded from customer metrics.

---

## Funnel Engine

Funnel stages:

```text
ENTRY
-> BROWSE
-> DWELL
-> BILLING_INTENT
-> PURCHASE_PROXY
```

Current purchase proxy:

```text
BILLING_QUEUE_JOIN
```

This can later be replaced with POS-linked purchase attribution once session timestamps and POS transactions are calibrated.

---

## Anomaly Engine

Supported anomalies:

```text
QUEUE_SPIKE
CONVERSION_DROP
DEAD_ZONE
```

Severity levels:

```text
INFO
WARN
CRITICAL
```

Each anomaly includes:

- observed value
- threshold value
- severity
- zone ID where relevant
- suggested action

---

## Real CCTV Processing

The project includes a real-video MVP:

- reads MP4 files with OpenCV
- samples frames
- detects motion/person-like regions using CPU-safe fallback
- maps detections to retail events using camera roles
- writes JSONL event stream

Generated from provided CCTV:

```text
913 structured events
5 videos processed
```

Event mix:

```text
ZONE_DWELL           596
ENTRY                138
BILLING_QUEUE_JOIN   155
ZONE_ENTER            24
```

---

## Dashboard

The dashboard is served by FastAPI/Nginx and includes:

- KPI cards
- funnel chart
- heatmap panel
- anomaly feed
- live event table
- WebSocket connection status
- database/feed health status

Dashboard URL:

```text
http://localhost
```

---

## Deployment

Docker Compose runs:

```text
PostgreSQL
Redis
FastAPI app
Nginx
```

Verified:

```text
app       healthy
nginx     healthy
postgres  healthy
redis     healthy
```

Health endpoint:

```text
http://localhost:8000/health
```

---

## Testing

Automated test coverage includes:

- event schema validation
- simulation mode
- real video pipeline
- idempotent ingestion
- duplicate handling
- health checks
- metrics
- funnel
- anomalies
- dashboard routes
- WebSocket broadcast
- JSONL ingestion

Current result:

```text
46 passed
88% coverage
```

---

## How To Run

Start the stack:

```powershell
docker compose up -d --build
```

Open dashboard:

```text
http://localhost
```

Check API:

```text
http://localhost:8000/health
```

Run tests:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

---

## Generate Events From CCTV

```powershell
$env:DETECTOR_BACKEND='opencv_motion'
$env:PIPELINE_FRAME_STRIDE='30'
$env:PIPELINE_MAX_FRAMES_PER_CAMERA='80'

.\.venv\Scripts\python.exe -m pipeline.run dataset `
  --profile store1 `
  --dataset-dir "<PATH_TO_STORE_1_FOLDER>" `
  --output "artifacts\events\store1_events.jsonl"

.\.venv\Scripts\python.exe -m pipeline.run dataset `
  --profile store2 `
  --dataset-dir "<PATH_TO_STORE_2_FOLDER>" `
  --output "artifacts\events\store2_events.jsonl"
```

Ingest generated events:

```powershell
.\.venv\Scripts\python.exe -m pipeline.run ingest `
  --file "artifacts\events\store1_events.jsonl" `
  --api-url "http://localhost:8000"

.\.venv\Scripts\python.exe -m pipeline.run ingest `
  --file "<PATH_TO_SAMPLE_EVENTS_JSONL>" `
  --api-url "http://localhost:8000"
```

---

## Engineering Decisions

Key decisions:

- Use structured events as the system contract.
- Keep detection adapters separate from business logic.
- Use simulation mode before dataset arrival.
- Use CPU-safe OpenCV fallback for reliable local execution.
- Keep YOLO/ByteTrack/ReID integration points ready.
- Use repository pattern for testable services.
- Use Docker Compose for reviewer-friendly execution.
- Keep anomaly rules explainable rather than opaque.

---

## Tradeoffs

Current limitations:

- OpenCV fallback is less accurate than YOLO.
- Person identity is approximate without full ReID calibration.
- POS data is not yet linked to individual CCTV sessions.
- Queue and purchase are currently inferred using event proxies.

Why acceptable:

- The assessment rewards end-to-end system design and working business logic.
- The architecture allows model upgrades without changing API/dashboard code.
- The system performs real computation on provided CCTV files.

---

## Future Work

Next improvements:

- replace OpenCV fallback with YOLOv8 weights
- integrate ByteTrack for stable per-camera tracks
- integrate TorchReID for cross-camera identity
- calibrate zones using store layout
- link POS transactions with CCTV session windows
- add historical baselines for anomaly detection
- deploy public demo

---

## Summary

This project demonstrates an end-to-end retail analytics platform:

- real CCTV input
- structured event stream
- production-style API
- persistent event store
- business metrics
- funnel analysis
- anomaly detection
- live dashboard
- Dockerized deployment
- automated tests

It is designed to be reviewed, extended, containerized, and defended in an architecture interview.
