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

Module 7 includes:

- OpenCV MP4 video reader
- CPU-safe OpenCV motion detector fallback
- detector factory with YOLOv8 adapter support
- camera-role-to-event builder for the received CCTV files
- JSONL event output from real videos
- tests with a synthetic MP4 fixture

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

Run Module 7 tests only:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_real_video_pipeline.py
```

Run the Brigade CCTV pipeline:

```powershell
$env:DETECTOR_BACKEND='opencv_motion'
$env:PIPELINE_FRAME_STRIDE='30'
$env:PIPELINE_MAX_FRAMES_PER_CAMERA='80'
.\.venv\Scripts\python.exe -m pipeline.run dataset --dataset-dir "C:\Users\hp\Downloads\CCTV Footage-20260529T160731Z-3-00144614ea\CCTV Footage" --output "artifacts\events\brigade_events.jsonl"
```

Install optional CV/model dependencies locally when running the real CCTV pipeline:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-cv.txt
```
## Running with Docker Compose

The application can be launched locally using Docker Compose:

```bash
docker compose up --build
```

- The API will be available at `http://localhost:8000`.
- The dashboard UI (served by Nginx) will be reachable at `http://localhost`.
- Use `docker compose down` to stop and remove containers.

Make sure the environment variables defined in `.env.example` are set (you can copy the file to `.env`).
