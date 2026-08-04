# ---------------------------------------------------------------------------
# Derived from apps/backend/app/services/parser.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# License: Apache-2.0
# Modified: Adapted ``parse_resume_to_json`` into a provider-injected async
#   parser. Removed all ``app.llm`` / ``app.prompts`` / ``app.schemas`` /
#   ``get_llm_config`` / ``get_model_name`` / ``get_safe_max_tokens`` coupling;
#   the LLM call now goes through the ``StructuredCompletionProvider`` Protocol.
#   Text extraction is delegated to ``extract_resume_text``; failures are mapped
#   to core warnings + reduced confidence instead of raised exceptions, and the
#   result is returned as a ``ParseResult`` carrying warnings + provenance.
# ---------------------------------------------------------------------------
"""Provider-injected structured resume parsing.

:func:`parse_resume_structured` runs the full no-crash pipeline: deterministic
text extraction → LLM structuring via an injected
:class:`~resume_kit_core.providers.StructuredCompletionProvider` → date
rehydration → schema validation, returning a :class:`ParseResult`.

:func:`extract_resume_text_only` is the no-provider convenience: it performs
only deterministic extraction and returns a ``ParseResult`` with
``document=None`` plus a ``PROVIDER_FALLBACK_USED`` warning, so callers get a
uniform ``ParseResult`` surface whether or not a provider is available.
"""

from __future__ import annotations

import logging

from pydantic import ValidationError
from resume_kit_core.errors import CoreWarning, ResumeKitError, WarningCode
from resume_kit_core.providers import (
    MessageParam,
    StructuredCompletionProvider,
    StructuredCompletionRequest,
)
from resume_kit_core.response import ProvenanceRef
from resume_kit_schemas.resume import ResumeDocument

from .dates import restore_dates_from_markdown
from .prompts import PARSE_RESUME_PROMPT, RESUME_SCHEMA_EXAMPLE
from .results import ParseMethod, ParseResult
from .text_extraction import extract_resume_text

logger = logging.getLogger(__name__)

_PARSER_ID = "resume_kit_document_parser.structured.parse_resume_structured"
_SYSTEM_PROMPT = (
    "You are a JSON extraction engine. Output only valid JSON, no explanations."
)

# Confidence heuristics.
_CONFIDENCE_SUCCESS = 0.9
_CONFIDENCE_DEGRADED = 0.3
_CONFIDENCE_UNAVAILABLE = 0.0


def _provenance(filename: str, method: ParseMethod, source_type: str) -> ProvenanceRef:
    """Build a provenance record carrying parser lineage + method metadata."""
    return ProvenanceRef(
        source_id=filename,
        source_type=source_type,
        metadata={"parser": _PARSER_ID, "method": method.value},
    )


async def parse_resume_structured(
    content: bytes,
    filename: str,
    provider: StructuredCompletionProvider,
) -> ParseResult:
    """Parse resume bytes into a structured :class:`ResumeDocument` via an LLM.

    Pipeline (never raises on expected non-fatal failures):

    1. Extract markdown text with :func:`extract_resume_text`; propagate any
       extraction warnings.
    2. Build a :class:`StructuredCompletionRequest` and call
       ``provider.complete_json``.
    3. Rehydrate months the model may have dropped via
       :func:`restore_dates_from_markdown`.
    4. Validate into :class:`ResumeDocument`.

    Provider failures, empty extracted text, and validation errors are mapped
    to core warnings with a reduced confidence; ``document`` is ``None`` in
    those degraded cases.

    Args:
        content: Raw resume file bytes.
        filename: Original filename; drives extension-based extraction.
        provider: Injected structured-completion provider.

    Returns:
        A :class:`ParseResult` with ``method=ParseMethod.llm``.
    """
    extraction = extract_resume_text(content, filename)
    warnings: list[CoreWarning] = list(extraction.warnings)
    markdown_text = extraction.text
    provenance = [
        _provenance(filename, ParseMethod.deterministic, "file"),
        _provenance(filename, ParseMethod.llm, "llm_response"),
    ]

    def _degraded(warning: CoreWarning) -> ParseResult:
        return ParseResult(
            text=markdown_text,
            document=None,
            confidence=_CONFIDENCE_DEGRADED,
            warnings=[*warnings, warning],
            provenance=provenance,
        )

    # ---- Guard: empty extracted text --------------------------------------
    if not markdown_text or not markdown_text.strip():
        logger.warning("parse_resume_structured: empty text for '%s'", filename)
        return _degraded(
            CoreWarning(
                code=WarningCode.INCOMPLETE_DATA,
                message=(
                    f"No text could be extracted from '{filename}'; "
                    "structured parsing was skipped."
                ),
                details={"filename": filename},
            )
        )

    prompt = PARSE_RESUME_PROMPT.format(
        schema=RESUME_SCHEMA_EXAMPLE,
        resume_text=markdown_text,
    )
    request = StructuredCompletionRequest(
        messages=[
            MessageParam(role="system", content=_SYSTEM_PROMPT),
            MessageParam(role="user", content=prompt),
        ],
        output_schema=ResumeDocument.model_json_schema(),
    )

    # ---- Provider call -----------------------------------------------------
    try:
        parsed = await provider.complete_json(request)
    except ResumeKitError as exc:
        logger.warning(
            "parse_resume_structured: provider failed for '%s': %s", filename, exc
        )
        return _degraded(
            CoreWarning(
                code=WarningCode.PROVIDER_FALLBACK_USED,
                message=(
                    f"Structured completion provider failed for '{filename}': "
                    f"{exc}. Returning text-only result."
                ),
                details={
                    "filename": filename,
                    "error_code": exc.error.code.value,
                },
            )
        )

    if not isinstance(parsed, dict):
        logger.warning(
            "parse_resume_structured: non-dict provider output for '%s'", filename
        )
        return _degraded(
            CoreWarning(
                code=WarningCode.PROVIDER_LOW_CONFIDENCE,
                message=(
                    f"Provider returned malformed (non-object) output for "
                    f"'{filename}'; structured parsing failed."
                ),
                details={"filename": filename, "output_type": type(parsed).__name__},
            )
        )

    # ---- Date rehydration --------------------------------------------------
    parsed = restore_dates_from_markdown(parsed, markdown_text)

    # ---- Schema validation -------------------------------------------------
    try:
        document = ResumeDocument.model_validate(parsed)
    except ValidationError as exc:
        logger.warning(
            "parse_resume_structured: validation failed for '%s': %s", filename, exc
        )
        return _degraded(
            CoreWarning(
                code=WarningCode.INCOMPLETE_DATA,
                message=(
                    f"Provider output for '{filename}' did not validate against "
                    f"the resume schema: {exc.error_count()} error(s)."
                ),
                details={"filename": filename, "error_count": exc.error_count()},
            )
        )

    return ParseResult(
        text=markdown_text,
        document=document,
        confidence=_CONFIDENCE_SUCCESS,
        warnings=warnings,
        provenance=provenance,
    )


def extract_resume_text_only(content: bytes, filename: str) -> ParseResult:
    """Extract text without structured parsing, returning a uniform result.

    Use when no provider is available (text-only / no-LLM mode). The returned
    :class:`ParseResult` has ``document=None`` and carries a
    :attr:`WarningCode.PROVIDER_FALLBACK_USED` warning so callers can
    distinguish "structured parse unavailable" from "parse produced no data".

    Args:
        content: Raw resume file bytes.
        filename: Original filename; drives extension-based extraction.

    Returns:
        A :class:`ParseResult` with ``method=ParseMethod.deterministic`` and
        ``document=None``.
    """
    extraction = extract_resume_text(content, filename)
    warnings: list[CoreWarning] = list(extraction.warnings)
    warnings.append(
        CoreWarning(
            code=WarningCode.PROVIDER_FALLBACK_USED,
            message=(
                "Structured parsing is unavailable (no provider configured); "
                "returning deterministic text extraction only."
            ),
            details={"filename": filename},
        )
    )
    return ParseResult(
        text=extraction.text,
        document=None,
        confidence=_CONFIDENCE_UNAVAILABLE,
        warnings=warnings,
        provenance=[_provenance(filename, ParseMethod.deterministic, "file")],
    )
