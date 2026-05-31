from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from typing import Literal
from uuid import UUID

from dotenv import load_dotenv


Environment = Literal["local", "test", "staging", "production"]


def _bool_from_env(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    return raw_value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _int_from_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer") from exc


@dataclass(frozen=True, slots=True)
class AppSettings:
    app_name: str
    environment: Environment
    log_level: str
    simulation_mode: bool
    real_pipeline_mode: bool
    database_url: str
    redis_url: str | None
    groq_api_key: str | None
    groq_model: str
    default_store_id: UUID
    event_stale_after_seconds: int

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def pipeline_mode(self) -> Literal["simulation", "real", "disabled"]:
        if self.simulation_mode:
            return "simulation"
        if self.real_pipeline_mode:
            return "real"
        return "disabled"


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    load_dotenv()

    environment = os.getenv("ENVIRONMENT", "local").strip().lower()
    if environment not in {"local", "test", "staging", "production"}:
        raise ValueError("ENVIRONMENT must be one of local, test, staging, production")

    simulation_mode = _bool_from_env("SIMULATION_MODE", True)
    real_pipeline_mode = _bool_from_env("REAL_PIPELINE_MODE", False)
    if simulation_mode and real_pipeline_mode:
        raise ValueError("SIMULATION_MODE and REAL_PIPELINE_MODE cannot both be true")

    default_store_id = UUID(
        os.getenv("DEFAULT_STORE_ID", "00000000-0000-4000-8000-000000000001")
    )

    return AppSettings(
        app_name=os.getenv("APP_NAME", "store-intelligence"),
        environment=environment,  # type: ignore[arg-type]
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        simulation_mode=simulation_mode,
        real_pipeline_mode=real_pipeline_mode,
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://store_intel:store_intel@localhost:5432/store_intel",
        ),
        redis_url=os.getenv("REDIS_URL"),
        groq_api_key=os.getenv("GROQ_API_KEY"),
        groq_model=os.getenv("GROQ_MODEL", "llama-3.3-70b"),
        default_store_id=default_store_id,
        event_stale_after_seconds=_int_from_env("EVENT_STALE_AFTER_SECONDS", 90),
    )

