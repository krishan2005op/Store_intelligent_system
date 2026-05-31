# Store Intelligence Platform

Production-oriented skeleton for converting raw CCTV footage into realtime retail
analytics through a detection pipeline, structured event stream, intelligence API,
and live dashboard.

Module 1 includes:

- project directory skeleton
- dependency declaration
- environment configuration contract
- `structlog` setup
- shared Pydantic v2 event schemas
- initial schema validation tests

Module 2 includes:

- detector, tracker, ReID, and zone resolver interfaces
- CPU-safe mock implementations
- lazy real adapter shells for YOLOv8, ByteTrack, and TorchReID
- deterministic simulator for pre-dataset event streams

Module 3 includes:

- FastAPI app factory and request logging middleware
- `POST /events/ingest`
- `GET /health`
- idempotent ingestion service
- SQLAlchemy event model and repository protocol
- Alembic baseline migration
- API tests with in-memory repository overrides

Module 4 includes:

- `GET /stores/{id}/metrics`
- `GET /stores/{id}/heatmap`
- metrics service and response schemas
- repository query support for store/time windows
- tests for empty store, staff-only traffic, zero purchase, reentry, queue abandonment,
  and heatmap normalization

Module 5 includes:

- `GET /stores/{id}/funnel`
- session funnel service and response schemas
- dataset profile for `ST1008 / Brigade_Bangalore`
- camera role mapping for the received CCTV files
- tests for empty funnel, staff exclusion, reentry dedupe, drop-off, time windows,
  and billing queue purchase proxy

Module 6 includes:

- `GET /stores/{id}/anomalies`
- `QUEUE_SPIKE`, `CONVERSION_DROP`, and `DEAD_ZONE`
- `INFO`, `WARN`, and `CRITICAL` severities
- suggested actions for each anomaly
- tests for empty windows, queue spikes, conversion drops, dead zones, and normal windows

## Testing

Run the full suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run Module 4 tests only:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_metrics.py
```

Run Module 5 tests only:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_funnel.py tests/test_dataset_config.py
```

Run Module 6 tests only:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_anomalies.py
```
