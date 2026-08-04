"""Stable error/warning taxonomy and value types for resume-kit-core."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    """Canonical error codes used across all resume-kit interfaces."""

    # Provider / completion errors
    PROVIDER_NOT_CONFIGURED = "provider_not_configured"
    PROVIDER_UNAVAILABLE = "provider_unavailable"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_RATE_LIMITED = "provider_rate_limited"
    PROVIDER_INVALID_RESPONSE = "provider_invalid_response"
    PROVIDER_JSON_PARSE_FAILED = "provider_json_parse_failed"

    # Storage / artifact errors
    ARTIFACT_NOT_FOUND = "artifact_not_found"
    ARTIFACT_STORE_UNAVAILABLE = "artifact_store_unavailable"
    ARTIFACT_SERIALIZATION_FAILED = "artifact_serialization_failed"

    # Validation / schema errors
    VALIDATION_FAILED = "validation_failed"
    SCHEMA_MISMATCH = "schema_mismatch"

    # Input errors
    INVALID_INPUT = "invalid_input"
    MISSING_REQUIRED_FIELD = "missing_required_field"

    # Catch-all
    INTERNAL_ERROR = "internal_error"
    UNKNOWN = "unknown"


class WarningCode(StrEnum):
    """Canonical warning codes; warnings are non-fatal advisory notices."""

    # Provider / completion warnings
    PROVIDER_FALLBACK_USED = "provider_fallback_used"
    PROVIDER_LOW_CONFIDENCE = "provider_low_confidence"
    PROVIDER_PARAM_DROPPED = "provider_param_dropped"

    # Data quality warnings
    INCOMPLETE_DATA = "incomplete_data"
    AMBIGUOUS_FIELD = "ambiguous_field"
    TRUNCATED_OUTPUT = "truncated_output"

    # Human review hints
    HUMAN_REVIEW_SUGGESTED = "human_review_suggested"

    # Catch-all
    UNKNOWN = "unknown"


class CoreError(BaseModel):
    """Structured error value type.

    Carries a stable ``code`` so callers can match on it, a human-readable
    ``message``, and optional free-form ``details`` for diagnostics.
    """

    code: ErrorCode = Field(description="Stable machine-readable error code.")
    message: str = Field(description="Human-readable description of the error.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional free-form diagnostic context.",
    )


class CoreWarning(BaseModel):
    """Structured warning value type.

    Distinct from :class:`CoreError`: warnings do not indicate failure and
    callers may choose to ignore them.
    """

    code: WarningCode = Field(description="Stable machine-readable warning code.")
    message: str = Field(description="Human-readable description of the warning.")
    details: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional free-form advisory context.",
    )


class ResumeKitError(Exception):
    """Base exception for resume-kit-core failures.

    Wraps a :class:`CoreError` value type so structured context is always
    available alongside the exception message.
    """

    def __init__(self, error: CoreError) -> None:
        super().__init__(error.message)
        self.error = error

    @classmethod
    def from_code(
        cls,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> ResumeKitError:
        """Convenience constructor from constituent parts."""
        return cls(
            CoreError(code=code, message=message, details=details or {})
        )
