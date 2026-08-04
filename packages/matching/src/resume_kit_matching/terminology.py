"""Deterministic terminology-alignment analysis over alias match provenance.

Turns synonym-aware keyword-match provenance (RIT-I-0008) into "mirror the
employer's exact wording" suggestions. For every job-description keyword the
resume already satisfies, but only under a *different* surface form reached
through the curated alias lexicon (an ``alias`` match), this emits a
:class:`resume_kit_schemas.TerminologyAlignment` naming the JD keyword as the
proposed target wording, the resume's current alias surface form, and every
resume path where that current wording occurs.

Invariants (REQ-1001):

- Only ``alias`` hits yield suggestions. An ``exact`` hit needs no mirroring; a
  no-match keyword stays a gap and is never turned into a suggestion here.
- Location-finding is whole-term (each string leaf is tokenised into ``\\w``
  runs and each token compared via the shared matcher), never a substring probe.
- Output is deterministic: suggestions and their locations are sorted, so
  identical inputs produce an identical list with no set-order leakage.

Analysis-only: no mutation, no policy/truth calls (that is RIT-T-0073).
"""

from __future__ import annotations

from typing import Any

from resume_kit_schemas import TerminologyAlignment
from resume_kit_terms import match, surface_form

from .keywords import (
    _TOKEN_RE,
    _alias_index,
    _JdKeywordsInput,
    _ResumeInput,
    _to_jd_keywords_dict,
    _to_resume_dict,
)

__all__ = [
    "analyze_terminology_alignment",
]


def _string_leaves(node: Any, path: str) -> list[tuple[str, str]]:
    """Yield ``(dot+bracket path, text)`` for every string leaf under *node*.

    Paths use dot notation for dict keys and bracket notation for list indices,
    e.g. ``workExperience[0].description[1]``. Non-string scalars are skipped.
    Traversal is structural (deterministic dict-insertion / list order), so the
    resulting leaf order is stable for a fixed input.
    """
    leaves: list[tuple[str, str]] = []
    if isinstance(node, str):
        leaves.append((path, node))
    elif isinstance(node, dict):
        for key, value in node.items():
            child_path = f"{path}.{key}" if path else str(key)
            leaves.extend(_string_leaves(value, child_path))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            leaves.extend(_string_leaves(value, f"{path}[{index}]"))
    return leaves


def analyze_terminology_alignment(
    job: _JdKeywordsInput,
    resume: _ResumeInput,
) -> list[TerminologyAlignment]:
    """Return terminology-mirroring suggestions for *resume* against *job*.

    For each JD keyword satisfied by *resume* only through the curated alias
    lexicon, emits a :class:`~resume_kit_schemas.TerminologyAlignment` proposing
    the JD keyword as the mirror target, naming the resume's current alias
    surface form, and listing every resume path where it occurs.

    Args:
        job: A ``JobDescription`` instance or a plain dict with
            ``required_skills``, ``preferred_skills``, and/or ``keywords`` keys.
        resume: The resume to inspect (``ResumeDocument`` or plain dict).

    Returns:
        Deterministically sorted list of ``TerminologyAlignment``. Exact hits
        and no-match keywords contribute nothing.
    """
    jd_dict = _to_jd_keywords_dict(job)
    resume_dict = _to_resume_dict(resume)
    alias_index = _alias_index()

    all_keywords: set[str] = set()
    all_keywords.update(jd_dict.get("required_skills", []))
    all_keywords.update(jd_dict.get("preferred_skills", []))
    all_keywords.update(jd_dict.get("keywords", []))

    leaves = _string_leaves(resume_dict, "")

    suggestions: list[TerminologyAlignment] = []
    # Sorted keyword iteration so build order is deterministic before the final
    # sort (belt-and-suspenders against set-iteration leakage).
    for keyword in sorted(all_keywords):
        if not keyword.strip():
            continue
        # (current_wording surface) -> {canonical, sorted locations}. Grouping by
        # the alias surface form collapses repeated occurrences of the same
        # current wording into one suggestion with all its locations.
        grouped: dict[str, tuple[str, list[str]]] = {}
        for path, text in leaves:
            for token in _TOKEN_RE.findall(text):
                result = match(keyword, token, alias_index)
                if not (result.matched and result.kind == "alias"):
                    continue
                # An exact surface match is reported as ``exact`` by ``match``,
                # so an already-mirrored token never reaches here — no guard
                # needed, but assert the intent for the reader.
                current = surface_form(token)
                canonical = result.canonical if result.canonical is not None else ""
                existing = grouped.get(current)
                if existing is None:
                    grouped[current] = (canonical, [path])
                elif path not in existing[1]:
                    existing[1].append(path)
        for current in sorted(grouped):
            canonical, locations = grouped[current]
            suggestions.append(
                TerminologyAlignment(
                    jd_keyword=keyword,
                    current_wording=current,
                    locations=sorted(locations),
                    canonical=canonical,
                    match_kind="alias",
                )
            )

    suggestions.sort(
        key=lambda s: (s.jd_keyword, s.current_wording, s.canonical, s.locations)
    )
    return suggestions
