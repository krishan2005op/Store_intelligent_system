from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from app.core.config import AppSettings


def configure_logging(settings: AppSettings) -> None:
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            timestamper,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(settings.log_level)
        ),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.log_level,
        force=True,
    )


def bind_request_context(
    *,
    trace_id: str,
    endpoint: str,
    store_id: str | None = None,
    event_count: int | None = None,
) -> None:
    structlog.contextvars.bind_contextvars(
        trace_id=trace_id,
        endpoint=endpoint,
        store_id=store_id,
        event_count=event_count,
    )


def clear_request_context() -> None:
    structlog.contextvars.clear_contextvars()


def get_logger(name: str) -> Any:
    return structlog.get_logger(name)

