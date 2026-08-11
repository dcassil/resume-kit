"""Provider- and transport-agnostic result-shaping substrate.

This is the single shared adapter layer over :class:`InterfaceResponse` that
every Phase 5 transport (CLI, MCP, API, bridge) reuses so no transport invents
its own envelope, error handling, or exit-code policy.

No transport dependency (Typer, MCP SDK, FastAPI, uvicorn, httpx) is imported
here.  Everything depends inward on ``resume_kit_core`` value types only.
"""

from __future__ import annotations

from enum import IntEnum

from pydantic import ValidationError

from resume_kit_core.errors import (
    CoreError,
    CoreWarning,
    ErrorCode,
    ResumeKitError,
)
from resume_kit_core.response import InterfaceResponse, ProvenanceRef, Question
from resume_kit_core.storage import ArtifactRef

# ---------------------------------------------------------------------------
# Exit-code policy
# ---------------------------------------------------------------------------


class ExitCode(IntEnum):
    """Deterministic process exit codes shared by all transports.

    Warnings alone never map to a non-zero code; only errors and the
    human-input-required state do.
    """

    OK = 0
    INVALID_INPUT = 2
    PROVIDER_NOT_CONFIGURED = 3
    PROVIDER_UNAVAILABLE = 4
    HUMAN_INPUT_REQUIRED = 5
    INTERNAL_ERROR = 70


# Map from ErrorCode to the exit code its presence should produce.
_ERROR_CODE_EXIT_MAP: dict[ErrorCode, ExitCode] = {
    ErrorCode.INVALID_INPUT: ExitCode.INVALID_INPUT,
    ErrorCode.MISSING_REQUIRED_FIELD: ExitCode.INVALID_INPUT,
    ErrorCode.VALIDATION_FAILED: ExitCode.INVALID_INPUT,
    ErrorCode.SCHEMA_MISMATCH: ExitCode.INVALID_INPUT,
    ErrorCode.PROVIDER_NOT_CONFIGURED: ExitCode.PROVIDER_NOT_CONFIGURED,
    ErrorCode.PROVIDER_UNAVAILABLE: ExitCode.PROVIDER_UNAVAILABLE,
    ErrorCode.PROVIDER_TIMEOUT: ExitCode.PROVIDER_UNAVAILABLE,
    ErrorCode.PROVIDER_RATE_LIMITED: ExitCode.PROVIDER_UNAVAILABLE,
    ErrorCode.PROVIDER_INVALID_RESPONSE: ExitCode.PROVIDER_UNAVAILABLE,
    ErrorCode.PROVIDER_JSON_PARSE_FAILED: ExitCode.PROVIDER_UNAVAILABLE,
}


def exit_code_for(response: InterfaceResponse[object]) -> int:
    """Select the deterministic exit code for a finished response.

    Precedence: hard errors first (in the order they appear), then the
    human-input-required state, then success.  Warnings never affect the
    result.
    """
    for error in response.errors:
        mapped = _ERROR_CODE_EXIT_MAP.get(error.code)
        if mapped is not None:
            return int(mapped)
        return int(ExitCode.INTERNAL_ERROR)
    if response.requires_human_input:
        return int(ExitCode.HUMAN_INPUT_REQUIRED)
    return int(ExitCode.OK)


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------


def build_success[T](
    data: T,
    *,
    warnings: list[CoreWarning] | None = None,
    artifacts: list[ArtifactRef] | None = None,
    provenance: list[ProvenanceRef] | None = None,
    strict: bool = False,
) -> InterfaceResponse[T]:
    """Build a success response from engine output.

    Preserves ``warnings``, ``artifacts``, and ``provenance`` separately in the
    envelope.  When ``strict`` is True and any warnings are present, the result
    is escalated to a failure whose errors mirror the offending warnings.
    """
    warns = warnings or []
    if strict and warns:
        errors = _warnings_as_errors(warns)
        return InterfaceResponse[T](data=None, errors=errors, warnings=warns)
    return InterfaceResponse.success(
        data,
        warnings=warns,
        artifacts=artifacts or [],
        provenance=provenance or [],
    )


def _warnings_as_errors(warnings: list[CoreWarning]) -> list[CoreError]:
    """Convert advisory warnings into validation errors (strict mode)."""
    return [
        CoreError(
            code=ErrorCode.VALIDATION_FAILED,
            message=w.message,
            details={"warning_code": str(w.code), **w.details},
        )
        for w in warnings
    ]


def escalate_warnings(warnings: list[CoreWarning]) -> InterfaceResponse[None]:
    """Escalate advisory warnings to a validation failure (strict mode)."""
    return InterfaceResponse.failure(_warnings_as_errors(warnings), warnings=warnings)


def build_provider_not_configured(
    message: str = "No LLM provider is configured for this operation.",
    *,
    details: dict[str, object] | None = None,
) -> InterfaceResponse[None]:
    """Build the standard provider-not-configured failure (REQ-507).

    Used whenever an LLM path is invoked without a configured provider.
    """
    error = CoreError(
        code=ErrorCode.PROVIDER_NOT_CONFIGURED,
        message=message,
        details=dict(details or {}),
    )
    return InterfaceResponse.failure([error])


def from_resume_kit_error(exc: ResumeKitError) -> InterfaceResponse[None]:
    """Map a :class:`ResumeKitError` to a failure preserving its ErrorCode."""
    return InterfaceResponse.failure([exc.error])


def from_validation_error(exc: ValidationError) -> InterfaceResponse[None]:
    """Map a pydantic ``ValidationError`` to a ``validation`` failure (RIT-T-0156).

    A schema validation failure is a *validation*-class error, not an opaque
    internal error: it names the offending field(s) and entry so the caller can
    act on it. Unlike :func:`from_exception`, the field locations and messages
    are safe to surface (they describe the schema contract, not secret content).
    """
    errors = exc.errors()
    fields = [
        ".".join(str(part) for part in err.get("loc", ())) for err in errors
    ]
    field_summary = ", ".join(field for field in fields if field)
    detail = f" ({field_summary})" if field_summary else ""
    message = (
        f"{len(errors)} schema validation error(s) in "
        f"{exc.title}{detail}"
    )
    return InterfaceResponse.failure(
        [
            CoreError(
                code=ErrorCode.VALIDATION_FAILED,
                message=message,
                details={
                    "exception_type": type(exc).__name__,
                    "model": exc.title,
                    "fields": field_summary,
                    "error_count": str(len(errors)),
                },
            )
        ]
    )


def from_value_error(exc: ValueError) -> InterfaceResponse[None]:
    """Map a caller-input :class:`ValueError` to a ``validation`` failure.

    Deterministic capabilities raise ``ValueError`` for bad *caller input*
    (e.g. an orphan source, a missing alias file). Those are the caller's fault,
    not an internal fault, so they must surface as ``VALIDATION_FAILED`` with an
    actionable message rather than being masked as ``INTERNAL_ERROR`` by
    :func:`from_exception`. The exception message IS actionable caller-facing
    text (it describes what input was wrong), so it is included verbatim.
    """
    error = CoreError(
        code=ErrorCode.VALIDATION_FAILED,
        message=str(exc) or "Invalid input.",
    )
    return InterfaceResponse.failure([error])


def from_exception(
    exc: BaseException,
    *,
    message: str = "An internal error occurred.",
) -> InterfaceResponse[None]:
    """Map an unexpected exception to an internal-error failure.

    A pydantic ``ValidationError`` is reclassified as a ``validation`` failure
    (see :func:`from_validation_error`) so schema-contract violations surface a
    specific, actionable field-naming message instead of the opaque
    ``internal_error``. Everything else remains an internal error.

    For non-validation exceptions this deliberately does NOT embed the
    exception's string or any content in the envelope, to avoid leaking secrets
    or user data.  Only the exception's type name is recorded for diagnostics.
    """
    if isinstance(exc, ValidationError):
        return from_validation_error(exc)
    error = CoreError(
        code=ErrorCode.INTERNAL_ERROR,
        message=message,
        details={"exception_type": type(exc).__name__},
    )
    return InterfaceResponse.failure([error])


def build_needs_input(
    questions: list[Question],
    *,
    warnings: list[CoreWarning] | None = None,
) -> InterfaceResponse[None]:
    """Build a human-input-required response wrapping ``questions``."""
    return InterfaceResponse.needs_input(questions, warnings=warnings or [])
