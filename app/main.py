from __future__ import annotations

from time import perf_counter
from typing import Any
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.config import AppSettings, get_settings
from app.core.exceptions import StoreIntelligenceError
from app.core.logging import (
    bind_request_context,
    clear_request_context,
    configure_logging,
    get_logger,
)
from app.routes import anomalies, funnel, health, ingest, metrics
from pipeline.schemas import StructuredError


logger = get_logger(__name__)


def create_app(settings: AppSettings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings)

    app = FastAPI(
        title="Store Intelligence Platform",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )
    app.state.settings = resolved_settings

    app.middleware("http")(request_logging_middleware)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StoreIntelligenceError, domain_exception_handler)

    app.include_router(health.router)
    app.include_router(ingest.router)
    app.include_router(metrics.router)
    app.include_router(funnel.router)
    app.include_router(anomalies.router)
    return app


async def request_logging_middleware(request: Request, call_next: Any) -> Response:
    trace_id = _trace_id_from_request(request)
    request.state.trace_id = trace_id
    endpoint = request.url.path
    event_count, store_id = await _request_observability_fields(request)
    bind_request_context(
        trace_id=str(trace_id),
        endpoint=endpoint,
        store_id=store_id,
        event_count=event_count,
    )

    started_at = perf_counter()
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Trace-Id"] = str(trace_id)
        return response
    finally:
        latency_ms = round((perf_counter() - started_at) * 1000, 2)
        logger.info(
            "request_completed",
            latency_ms=latency_ms,
            status_code=status_code,
        )
        clear_request_context()


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid4())
    error = StructuredError(
        trace_id=trace_id,
        code="REQUEST_VALIDATION_ERROR",
        message="Request validation failed",
        details={"errors": exc.errors()},
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=error.model_dump(mode="json"),
    )


async def domain_exception_handler(
    request: Request,
    exc: StoreIntelligenceError,
) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", uuid4())
    error = StructuredError(
        trace_id=trace_id,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=error.model_dump(mode="json"),
    )


def _trace_id_from_request(request: Request) -> UUID:
    raw_trace_id = request.headers.get("X-Trace-Id")
    if not raw_trace_id:
        return uuid4()
    try:
        return UUID(raw_trace_id)
    except ValueError:
        return uuid4()


async def _request_observability_fields(request: Request) -> tuple[int | None, str | None]:
    if request.method.upper() != "POST":
        return None, None

    try:
        body = await request.json()
    except Exception:
        return None, None

    events = body.get("events") if isinstance(body, dict) else None
    if not isinstance(events, list):
        return None, None

    store_id = None
    for event in events:
        if isinstance(event, dict) and event.get("store_id"):
            store_id = str(event["store_id"])
            break
    return len(events), store_id


app = create_app()
