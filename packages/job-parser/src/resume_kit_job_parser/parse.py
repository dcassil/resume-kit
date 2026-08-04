# ---------------------------------------------------------------------------
# Derived from apps/backend/app/services/improver.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# License: Apache-2.0
# Modified: Adapted ``extract_job_keywords`` into a provider-injected async
#   parser that produces the canonical ``resume_kit_schemas.JobDescription``.
#   Removed all ``app.llm`` / ``app.prompts`` / ``complete_json`` coupling and
#   the ``_sanitize_user_input`` helper; the LLM call now goes through the
#   ``StructuredCompletionProvider`` Protocol. Upstream returned a raw dict of
#   keywords; here the dict is MAPPED into ``JobDescription`` + ``Requirement``
#   value objects. Provider failures / malformed output are mapped to a safe
#   raw-text fallback instead of propagating, mirroring the Phase 2
#   ``document_parser.structured`` error-handling pattern.
# ---------------------------------------------------------------------------
"""Provider-injected job-description parsing.

:func:`parse_job_description` runs the no-crash pipeline: prompt construction →
LLM keyword extraction via an injected
:class:`~resume_kit_core.providers.StructuredCompletionProvider` → mapping into
the canonical :class:`~resume_kit_schemas.job.JobDescription`.

:func:`parse_job_description_text_only` is the no-provider deterministic
fallback: it returns a ``JobDescription`` carrying the raw text plus any
cheaply-derivable hints, with no LLM call.

Neither function raises on expected non-fatal failures (provider errors,
malformed provider output): both degrade to a raw-text ``JobDescription`` so
callers always get a usable result.
"""

from __future__ import annotations

import logging
from typing import Any

from resume_kit_core.providers import (
    MessageParam,
    StructuredCompletionProvider,
    StructuredCompletionRequest,
)
from resume_kit_schemas.job import JobDescription, Requirement, RequirementKind

from .prompts import EXTRACT_KEYWORDS_PROMPT

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = "You are an expert job description analyzer."


def _coerce_str(value: Any) -> str:
    """Return a stripped string for scalar values, else empty string."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return str(value)
    return ""


def _coerce_str_list(value: Any) -> list[str]:
    """Return a list of non-empty stripped strings from an arbitrary value."""
    if not isinstance(value, list):
        return []
    out: list[str] = []
    for item in value:
        text = _coerce_str(item)
        if text:
            out.append(text)
    return out


def _requirements_from(items: Any, kind: RequirementKind) -> list[Requirement]:
    """Build :class:`Requirement` objects from a list of skill/text strings."""
    return [
        Requirement(text=text, kind=kind, keywords=[text])
        for text in _coerce_str_list(items)
    ]


def _map_to_job_description(parsed: dict[str, Any], raw_text: str) -> JobDescription:
    """Map an upstream keyword-extraction dict into a ``JobDescription``.

    Recognized upstream fields: ``company``, ``role``, ``required_skills``,
    ``preferred_skills``, ``experience_requirements``,
    ``education_requirements``, ``key_responsibilities``, ``keywords``,
    ``experience_years``, ``seniority_level``. Unknown / missing fields are
    tolerated and produce sensible empty defaults.
    """
    requirements: list[Requirement] = [
        *_requirements_from(parsed.get("required_skills"), RequirementKind.REQUIRED),
        *_requirements_from(
            parsed.get("experience_requirements"), RequirementKind.REQUIRED
        ),
        *_requirements_from(
            parsed.get("education_requirements"), RequirementKind.REQUIRED
        ),
    ]
    qualifications = _requirements_from(
        parsed.get("preferred_skills"), RequirementKind.PREFERRED
    )

    # Aggregate all salient terms: explicit keywords + every skill mentioned.
    keywords: list[str] = []
    seen: set[str] = set()
    for source in (
        parsed.get("keywords"),
        parsed.get("required_skills"),
        parsed.get("preferred_skills"),
    ):
        for term in _coerce_str_list(source):
            lowered = term.casefold()
            if lowered not in seen:
                seen.add(lowered)
                keywords.append(term)

    summary_parts: list[str] = []
    seniority = _coerce_str(parsed.get("seniority_level"))
    if seniority:
        summary_parts.append(f"Seniority: {seniority}")
    years = parsed.get("experience_years")
    if isinstance(years, (int, float)) and not isinstance(years, bool):
        summary_parts.append(f"Experience: {int(years)}+ years")
    responsibilities = _coerce_str_list(parsed.get("key_responsibilities"))
    if responsibilities:
        summary_parts.append("Responsibilities: " + "; ".join(responsibilities))

    return JobDescription(
        title=_coerce_str(parsed.get("role")),
        company=_coerce_str(parsed.get("company")),
        raw_text=raw_text,
        summary="\n".join(summary_parts),
        requirements=requirements,
        qualifications=qualifications,
        keywords=keywords,
    )


async def parse_job_description(
    raw_text: str,
    provider: StructuredCompletionProvider,
) -> JobDescription:
    """Parse raw job-description text into a structured ``JobDescription``.

    Pipeline (never raises on expected non-fatal failures):

    1. Build a :class:`StructuredCompletionRequest` from
       :data:`~resume_kit_job_parser.prompts.EXTRACT_KEYWORDS_PROMPT` and
       ``raw_text``.
    2. Call ``provider.complete_json``.
    3. Map the returned upstream keyword dict into a ``JobDescription``.

    Provider failures (any :class:`Exception` from the provider) and malformed
    (non-dict) provider output are handled by falling back to
    :func:`parse_job_description_text_only`, so ``raw_text`` is always retained
    and the function never crashes.

    Args:
        raw_text: The raw job-description posting text.
        provider: Injected structured-completion provider.

    Returns:
        A :class:`JobDescription`; degraded (text-only) on provider failure.
    """
    prompt = EXTRACT_KEYWORDS_PROMPT.format(job_description=raw_text)
    request = StructuredCompletionRequest(
        messages=[
            MessageParam(role="system", content=_SYSTEM_PROMPT),
            MessageParam(role="user", content=prompt),
        ],
    )

    try:
        parsed = await provider.complete_json(request)
    except Exception as exc:  # noqa: BLE001 - degrade on any provider failure
        logger.warning(
            "parse_job_description: provider failed; using text-only fallback: %s",
            exc,
        )
        return parse_job_description_text_only(raw_text)

    if not isinstance(parsed, dict):
        logger.warning(
            "parse_job_description: non-dict provider output (%s); "
            "using text-only fallback",
            type(parsed).__name__,
        )
        return parse_job_description_text_only(raw_text)

    return _map_to_job_description(parsed, raw_text)


def parse_job_description_text_only(raw_text: str) -> JobDescription:
    """Return a ``JobDescription`` from raw text with no provider call.

    Deterministic no-LLM fallback. It always preserves ``raw_text`` and makes a
    best-effort, cheap guess at the ``title`` from the first non-empty line of
    the posting (a common convention for pasted postings). No requirements or
    keywords are inferred without a provider.

    Args:
        raw_text: The raw job-description posting text.

    Returns:
        A minimal :class:`JobDescription` carrying ``raw_text`` and a
        best-effort ``title``.
    """
    title = ""
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped:
            title = stripped
            break

    return JobDescription(title=title, raw_text=raw_text)
