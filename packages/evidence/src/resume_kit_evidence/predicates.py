"""Deterministic structural truth predicates over resume data.

# ---------------------------------------------------------------------------
# Derived from apps/backend/tests/evals/scorers.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc  Apache-2.0
# Modified: Extracted the pure structural scorers _is_nonempty,
#   _iter_text_fragments, flatten_resume_text, _employer_names,
#   sections_preserved, no_fabricated_employers, and personal_info_unchanged
#   into this standalone module. Replaced the app.schemas ResumeData import
#   with resume_kit_schemas.ResumeDocument. Added typed acceptance of
#   ResumeDocument (normalised via model_dump) alongside plain dict, matching
#   upstream call-site style. jd_keywords_present / is_valid_resume were NOT
#   ported here — they live in packages/matching. All deterministic text logic
#   is faithfully preserved.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Any

from resume_kit_schemas import ResumeDocument

# Public surface ---------------------------------------------------------------

__all__ = [
    "flatten_resume_text",
    "no_fabricated_employers",
    "personal_info_unchanged",
    "sections_preserved",
]

# Type alias for caller convenience
_ResumeInput = ResumeDocument | dict[str, Any]

# Top-level resume sections whose presence we care about. ``workExperience``
# and ``education`` are the load-bearing ones a tailoring must never drop.
_TRACKED_SECTIONS: tuple[str, ...] = (
    "summary",
    "workExperience",
    "education",
    "personalProjects",
    "additional",
)


def _to_resume_dict(resume: _ResumeInput) -> dict[str, Any]:
    """Normalise a ResumeDocument or plain dict to a camelCase dict."""
    if isinstance(resume, ResumeDocument):
        return resume.model_dump(by_alias=True)
    return resume


def _is_nonempty(value: Any) -> bool:
    """Return True when ``value`` carries real content.

    Empty strings, empty lists/dicts, ``None``, and dicts whose values are all
    themselves empty (e.g. an ``additional`` block of empty lists) count as
    empty. Everything else is considered present.
    """
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, tuple, set)):
        return len(value) > 0
    if isinstance(value, dict):
        return any(_is_nonempty(v) for v in value.values())
    return True


def _iter_text_fragments(value: Any) -> list[str]:
    """Recursively collect every string fragment inside ``value``."""
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


def flatten_resume_text(data: _ResumeInput) -> str:
    """Flatten an entire resume into one lowercased text blob.

    Used for case-insensitive keyword search across every field — summary,
    bullets, skills, custom sections, the lot.
    """
    return " ".join(_iter_text_fragments(_to_resume_dict(data))).lower()


def _employer_names(data: dict[str, Any]) -> list[str]:
    """Return the (stripped, non-empty) company names in ``workExperience``."""
    names: list[str] = []
    for entry in data.get("workExperience", []) or []:
        if not isinstance(entry, dict):
            continue
        company = entry.get("company")
        if isinstance(company, str) and company.strip():
            names.append(company.strip())
    return names


def sections_preserved(original: _ResumeInput, tailored: _ResumeInput) -> bool:
    """No populated top-level section may vanish during tailoring.

    For each tracked section that was non-empty in ``original``, the same
    section must still be non-empty in ``tailored``. Sections that were empty
    to begin with are ignored (tailoring is allowed to leave them empty).

    Returns True when every originally-populated section survives, else False.
    """
    original_dict = _to_resume_dict(original)
    tailored_dict = _to_resume_dict(tailored)
    for section in _TRACKED_SECTIONS:
        if _is_nonempty(original_dict.get(section)) and not _is_nonempty(
            tailored_dict.get(section)
        ):
            return False
    return True


def no_fabricated_employers(
    original: _ResumeInput, tailored: _ResumeInput
) -> list[str]:
    """Detect company names that appear in ``tailored`` but not in ``original``.

    Tailoring may re-word bullets but must never invent an employer the
    candidate never worked for. Comparison is case-insensitive and
    whitespace-trimmed.

    Returns the list of fabricated company names (in the casing they appear in
    ``tailored``). An empty list means the work history is truthful.
    """
    original_names = {name.lower() for name in _employer_names(_to_resume_dict(original))}
    fabricated: list[str] = []
    seen: set[str] = set()
    for name in _employer_names(_to_resume_dict(tailored)):
        key = name.lower()
        if key not in original_names and key not in seen:
            fabricated.append(name)
            seen.add(key)
    return fabricated


def personal_info_unchanged(
    original: _ResumeInput, tailored: _ResumeInput
) -> bool:
    """Return True iff the ``personalInfo`` block is byte-for-byte identical.

    The candidate's identity (name, contact details) must never be rewritten by
    tailoring. A missing block is treated as an empty dict on either side.
    """
    original_dict = _to_resume_dict(original)
    tailored_dict = _to_resume_dict(tailored)
    return bool(
        original_dict.get("personalInfo", {}) == tailored_dict.get("personalInfo", {})
    )
