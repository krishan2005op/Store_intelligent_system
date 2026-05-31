from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class StoreIntelligenceError(Exception):
    message: str
    code: str
    details: dict[str, Any] = field(default_factory=dict)


class ConfigurationError(StoreIntelligenceError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="CONFIGURATION_ERROR", details=details or {})


class IngestionValidationError(StoreIntelligenceError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="INGESTION_VALIDATION_ERROR", details=details or {})


class PipelineDependencyError(StoreIntelligenceError):
    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message=message, code="PIPELINE_DEPENDENCY_ERROR", details=details or {})

