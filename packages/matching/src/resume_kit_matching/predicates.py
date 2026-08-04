# ---------------------------------------------------------------------------
# Derived from apps/backend/tests/evals/scorers.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# License: Apache-2.0
# Modified: Ported ``jd_keywords_present`` and ``is_valid_resume`` predicates
#   only. Replaced ``app.schemas.ResumeData`` with
#   ``resume_kit_schemas.ResumeDocument``. Accept both model instance and dict.
#   Private helpers are local copies (keywords.py is file-disjoint by design).
# ---------------------------------------------------------------------------
"""Pure deterministic validation predicates for resume evaluation.

These helpers never call an LLM, never touch the network, and never read from
disk.  They form the cheap first line of defence in the eval harness.

Public API
----------
jd_keywords_present(tailored, keywords)
    Fraction of JD keywords that appear in the resume text.

is_valid_resume(data)
    True iff *data* validates against the :class:`~resume_kit_schemas.ResumeDocument`
    schema.
"""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from resume_kit_schemas.resume import ResumeDocument

# ---------------------------------------------------------------------------
# Private text-flattening helpers (local copies; deduplication is a Phase 5
# concern once all file-disjoint tasks have landed).
# ---------------------------------------------------------------------------


def _iter_text_fragments(value: Any) -> list[str]:
    """Recursively collect every string fragment inside *value*."""
    fragments: list[str] = []
    if value is None:
        return fragments
    if isinstance(value, str):
        if value:
            fragments.append(value)
    elif isinstance(value, dict):
        for item in value.values():
            fragments.extend(_iter_text_fragments(item))
    elif isinstance(value, (list, tuple, set)):
        for item in value:
            fragments.extend(_iter_text_fragments(item))
    else:
        fragments.append(str(value))
    return fragments


def _flatten_resume_text(data: dict[str, Any]) -> str:
    """Flatten an entire resume dict into one lowercased text blob.

    Used for case-insensitive keyword search across every field — summary,
    bullets, skills, custom sections, the lot.
    """
    return " ".join(_iter_text_fragments(data)).lower()


# ---------------------------------------------------------------------------
# Public predicates
# ---------------------------------------------------------------------------


def jd_keywords_present(
    tailored: ResumeDocument | dict[str, Any],
    keywords: list[str],
) -> float:
    """Fraction (0.0–1.0) of *keywords* that appear in the tailored resume.

    Matching is case-insensitive substring search over the flattened resume
    text.  With an empty *keywords* list there is nothing to miss, so the
    score is 1.0.

    Parameters
    ----------
    tailored:
        The tailored resume, either as a :class:`~resume_kit_schemas.ResumeDocument`
        instance or a plain ``dict``.
    keywords:
        JD keywords to look for.

    Returns
    -------
    float
        Hit rate in [0.0, 1.0].
    """
    if not keywords:
        return 1.0

    raw: dict[str, Any] = (
        tailored.model_dump() if isinstance(tailored, ResumeDocument) else tailored
    )

    haystack = _flatten_resume_text(raw)
    hits = sum(1 for kw in keywords if kw and kw.lower() in haystack)
    return hits / len(keywords)


def is_valid_resume(data: ResumeDocument | dict[str, Any]) -> bool:
    """Return ``True`` iff *data* validates against :class:`~resume_kit_schemas.ResumeDocument`.

    Parameters
    ----------
    data:
        Resume payload to validate, either as a
        :class:`~resume_kit_schemas.ResumeDocument` instance (always valid) or
        a plain ``dict`` that will be coerced through
        :meth:`~pydantic.BaseModel.model_validate`.

    Returns
    -------
    bool
        ``True`` when validation succeeds, ``False`` otherwise.
    """
    if isinstance(data, ResumeDocument):
        return True
    try:
        ResumeDocument.model_validate(data)
    except ValidationError:
        return False
    return True
