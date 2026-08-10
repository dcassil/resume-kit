"""Deterministic keyword matching and gap analysis.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/services/refiner.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc  Apache-2.0
# Modified: Extracted _keyword_in_text, _extract_jd_skill_keys,
#   analyze_keyword_gaps, calculate_keyword_match, and _extract_all_text into
#   this standalone module. Replaced app.schemas.* imports with
#   resume_kit_schemas. Added typed overloads accepting ResumeDocument /
#   JobDescription (normalised via model_dump) as well as plain dict, matching
#   upstream call-site style. Removed LLM and async dependencies. All
#   deterministic re/text logic is faithfully preserved.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import resume_kit_schemas
from resume_kit_schemas import (
    KeywordGapAnalysis,
    MatchedKeyword,
    ResumeDocument,
    sanitize_keywords,
)
from resume_kit_terms import (
    AliasIndex,
    MatchResult,
    load_effective_alias_index,
    match,
    surface_form,
)
from resume_kit_terms.aliases import PROJECT_ALIAS_ENV_VAR

# Public surface ---------------------------------------------------------------

__all__ = [
    "analyze_keyword_gaps",
    "calculate_keyword_match",
]

# Type aliases for caller convenience
_ResumeInput = ResumeDocument | dict[str, Any]
_JdKeywordsInput = resume_kit_schemas.JobDescription | dict[str, Any]


# ---------------------------------------------------------------------------
# Private helpers (ported verbatim from upstream, minus logging)
# ---------------------------------------------------------------------------


def _keyword_in_text(keyword: str, text: str) -> bool:
    """Return True if *keyword* appears as a whole term in *text*.

    SVC-010 (upstream): Uses term boundaries instead of substring matching to
    avoid false positives like 'python' matching 'pythonic' or 'go' matching
    'going'.
    """
    escaped = re.escape(keyword.strip().lower())
    if not escaped:
        return False
    pattern = rf"(?<!\w){escaped}(?!\w)"
    return bool(re.search(pattern, text.lower()))


def _normalize_skill_key(skill: str) -> str:
    """Normalize a skill string for case-insensitive comparisons.

    Delegates to the shared ``resume_kit_terms.surface_form`` normalizer (the
    single source of truth for term comparison across ``matching`` and ``ats``)
    so no second divergent normalizer lives in this package. ``surface_form``
    folds case/punctuation/Unicode without stemming, which preserves the
    case-insensitive whole-key semantics this helper historically provided.
    """
    return surface_form(skill)


@lru_cache(maxsize=8)
def _effective_alias_index(project_key: str | None) -> AliasIndex:
    """Build (and cache) the effective seed+project index for *project_key*.

    The cache is keyed on the resolved project-file path string (``None`` for
    seed-only), so a changed ``RESUME_KIT_ALIAS_FILE`` yields a fresh index
    rather than a stale one — deterministic for a FIXED path, invalidatable
    across paths. Loading is offline and deterministic.
    """
    project_path = Path(project_key) if project_key is not None else None
    return load_effective_alias_index(project_path)


def _alias_index() -> AliasIndex:
    """Return the effective (seed + optional project) curated alias index.

    Resolves the project-alias path from ``RESUME_KIT_ALIAS_FILE`` (a surface
    sets it; RIT-T-0069) and delegates to the path-keyed cache. An unset / empty
    env var means seed-only.
    """
    env_value = os.environ.get(PROJECT_ALIAS_ENV_VAR)
    project_key = env_value if env_value and env_value.strip() else None
    return _effective_alias_index(project_key)


# Token pattern for splitting resume text into whole terms. Mirrors the
# word-boundary semantics of ``_keyword_in_text`` (``\w`` runs), so a keyword
# like ``python`` is compared against the token ``python`` but never against a
# fragment of ``pythonic``.
_TOKEN_RE = re.compile(r"\w+")


def _alias_windows(text: str, max_tokens: int) -> list[str]:
    """Yield contiguous whole-token windows of *text*, widths 1..*max_tokens*.

    Tokens are ``\\w`` runs (mirroring :data:`_TOKEN_RE`), and each window is the
    tokens joined by a single space — the exact surface form the shared matcher
    compares against. Widths are bounded by *max_tokens*, which callers derive
    from :attr:`AliasIndex.max_member_tokens` so the scan can assemble every
    multi-token alias the lexicon holds and NOTHING wider. Because every window
    is a run of adjacent tokens, the contiguous-boundary guarantee is preserved:
    a keyword can only match a phrase actually written as a contiguous span, so
    substring / derivational / cross-gap false positives cannot arise.
    """
    tokens = _TOKEN_RE.findall(text)
    width_cap = max(1, max_tokens)
    windows: list[str] = []
    for start in range(len(tokens)):
        for width in range(1, width_cap + 1):
            end = start + width
            if end > len(tokens):
                break
            windows.append(" ".join(tokens[start:end]))
    return windows


def _match_keyword_in_text(keyword: str, text: str) -> MatchResult | None:
    """Return the highest-precedence synonym-aware match for *keyword* in *text*.

    Comparison is delegated to ``resume_kit_terms.match`` using the shared alias
    index, so ``mentorship`` hits resume ``mentoring`` (alias), ``k8s`` hits
    ``Kubernetes`` (alias), and ``eslint`` hits ``linting`` (alias). Whole-term
    semantics are preserved two ways:

    - Exact / multi-word hits go through the original word-boundary regex
      (:func:`_keyword_in_text`), so ``machine learning`` matches only as a
      contiguous phrase and ``python`` never matches inside ``pythonic``.
    - Synonym widening tokenizes *text* into ``\\w`` runs and compares
      contiguous whole-token WINDOWS via the shared matcher, never a substring.
      The window size is bounded by :attr:`AliasIndex.max_member_tokens` — the
      longest alias surface form the lexicon actually holds — so multi-token
      aliases (``continuous integration`` ↔ ``ci``) can be assembled while the
      contiguous-boundary guarantee still rules out substring/derivational
      false positives. The window never widens past what the index can match.

    Stem-only matches are intentionally **not** accepted here: Snowball stemming
    collapses derivational forms the upstream engine keeps distinct (``python``
    ↔ ``pythonic``, ``go`` ↔ ``going``), which would violate the whole-term
    guarantee locked by the characterization suite. Genuine cross-word synonyms
    (including morphological pairs like ``mentoring`` ↔ ``mentorship``) are
    carried by the curated alias lexicon instead, so provenance stays
    ``exact`` | ``alias:<canonical>``. If the lexicon later needs a pair that is
    only reachable by stemming, widen this to accept ``stem`` for that path.

    Returns ``None`` when the keyword is absent. The returned
    :class:`MatchResult` is always ``matched=True`` with a concrete ``kind``.
    """
    if not keyword.strip():
        return None

    # Exact / multi-word: preserve the original contiguous-boundary behavior.
    if _keyword_in_text(keyword, text):
        return MatchResult(matched=True, kind="exact")

    # Alias widening: compare the keyword against each whole token in the text.
    # Alias groups are curated true synonyms, so this never introduces the
    # substring/derivational false positives that raw stemming would.
    alias_index = _alias_index()
    for window in _alias_windows(text, alias_index.max_member_tokens):
        result = match(keyword, window, alias_index)
        if result.matched and result.kind == "alias":
            return result
    return None


@lru_cache(maxsize=100)
def _extract_all_text_cached(data_json: str) -> str:
    """Cached implementation of full-resume text extraction.

    SVC-011 (upstream): LRU cache avoids re-extracting text from the same
    resume multiple times during a single analysis pass.
    """
    data: dict[str, Any] = json.loads(data_json)
    parts: list[str] = []

    # Summary
    if data.get("summary"):
        parts.append(str(data["summary"]))

    # Work experience
    for exp in data.get("workExperience", []):
        if isinstance(exp, dict):
            parts.append(str(exp.get("title", "")))
            parts.append(str(exp.get("company", "")))
            desc = exp.get("description", [])
            if isinstance(desc, list):
                parts.extend(str(d) for d in desc)

    # Education
    for edu in data.get("education", []):
        if isinstance(edu, dict):
            parts.append(str(edu.get("degree", "")))
            parts.append(str(edu.get("institution", "")))
            if edu.get("description"):
                parts.append(str(edu["description"]))

    # Projects
    for proj in data.get("personalProjects", []):
        if isinstance(proj, dict):
            parts.append(str(proj.get("name", "")))
            parts.append(str(proj.get("role", "")))
            desc = proj.get("description", [])
            if isinstance(desc, list):
                parts.extend(str(d) for d in desc)

    # Additional
    additional = data.get("additional", {})
    if isinstance(additional, dict):
        skills = additional.get("technicalSkills", [])
        if isinstance(skills, list):
            parts.extend(str(s) for s in skills)
        certs = additional.get("certificationsTraining", [])
        if isinstance(certs, list):
            parts.extend(str(c) for c in certs)
        languages = additional.get("languages", [])
        if isinstance(languages, list):
            parts.extend(str(lang) for lang in languages)
        awards = additional.get("awards", [])
        if isinstance(awards, list):
            parts.extend(str(a) for a in awards)

    # Custom sections
    custom_sections = data.get("customSections", {})
    if isinstance(custom_sections, dict):
        for section in custom_sections.values():
            if not isinstance(section, dict):
                continue
            section_type = section.get("sectionType", "")
            if section_type == "itemList":
                for item in section.get("items", []):
                    if isinstance(item, dict):
                        parts.append(str(item.get("title", "")))
                        parts.append(str(item.get("subtitle", "")))
                        desc = item.get("description", [])
                        if isinstance(desc, list):
                            parts.extend(str(d) for d in desc)
                        elif isinstance(desc, str):
                            parts.append(desc)
            elif section_type == "text":
                text = section.get("text", "")
                if isinstance(text, str):
                    parts.append(text)
            elif section_type == "stringList":
                items = section.get("strings", [])
                if isinstance(items, list):
                    parts.extend(str(i) for i in items)

    return " ".join(p for p in parts if p)


def _extract_all_text(data: dict[str, Any]) -> str:
    """Extract all text content from resume data for keyword matching.

    Produces a stable JSON key for the LRU cache, then delegates to the
    cached implementation.
    """
    data_json = json.dumps(data, sort_keys=True, default=str)
    return _extract_all_text_cached(data_json)


def _texts_near_identical(text_a: str, text_b: str) -> bool:
    """Return True when two resume texts are effectively the same source.

    Deterministic and cheap: exact string equality first, then a token-set
    Jaccard >= 0.98 fallback so trivial reordering/whitespace still counts as
    "no distinct master". Used to flag the degenerate check-gaps case where
    injectable classification is meaningless (RIT-T-0126).
    """
    if text_a == text_b:
        return True
    tokens_a = set(text_a.split())
    tokens_b = set(text_b.split())
    if not tokens_a and not tokens_b:
        return True
    union = tokens_a | tokens_b
    if not union:
        return True
    jaccard = len(tokens_a & tokens_b) / len(union)
    return jaccard >= 0.98


def _to_resume_dict(resume: _ResumeInput) -> dict[str, Any]:
    """Normalise a ResumeDocument or plain dict to a plain dict."""
    if isinstance(resume, ResumeDocument):
        return resume.model_dump()
    return resume


def _to_jd_keywords_dict(jd: _JdKeywordsInput) -> dict[str, Any]:
    """Normalise a JobDescription or plain dict to the upstream keyword shape.

    Upstream code expects a flat dict with keys ``required_skills``,
    ``preferred_skills``, and ``keywords``.  The canonical ``JobDescription``
    model uses ``requirements``, ``qualifications``, and ``keywords`` — we map
    those here so callers may pass either form.
    """
    if isinstance(jd, dict):
        return jd
    # JobDescription model → upstream keyword dict shape.
    #
    # RIT-T-0128: run every candidate through the keyword hygiene gate so full
    # requirement sentences (prose the parse step misclassified as a "skill")
    # never enter the scored denominator. A requirement's ``text`` is included
    # only when it is itself a concrete token; its prose stays on the model for
    # display but is dropped here. Fixes match, check-gaps, and check-keywords in
    # one place, since they all funnel through this boundary.
    required_raw: list[str] = []
    for req in jd.requirements:
        required_raw.append(req.text)
        required_raw.extend(req.keywords)
    preferred_raw: list[str] = []
    for qual in jd.qualifications:
        preferred_raw.append(qual.text)
        preferred_raw.extend(qual.keywords)
    return {
        "required_skills": sanitize_keywords(required_raw),
        "preferred_skills": sanitize_keywords(preferred_raw),
        "keywords": sanitize_keywords(jd.keywords),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def calculate_keyword_match(
    resume: _ResumeInput,
    jd_keywords: _JdKeywordsInput,
) -> float:
    """Return the keyword match percentage (0.0–100.0) for *resume* vs *jd_keywords*.

    SVC-009 (upstream): Returns 0.0 — not 100.0 — when the keyword set is
    empty, because 100 % would be misleading.

    Args:
        resume: A ``ResumeDocument`` instance or a plain dict in the upstream
            camelCase resume-data shape.
        jd_keywords: A ``JobDescription`` instance or a plain dict with
            ``required_skills``, ``preferred_skills``, and/or ``keywords``
            keys.

    Returns:
        Match percentage in the range [0.0, 100.0].
    """
    resume_dict = _to_resume_dict(resume)
    jd_dict = _to_jd_keywords_dict(jd_keywords)

    resume_text = _extract_all_text(resume_dict).lower()

    all_keywords: set[str] = set()
    all_keywords.update(jd_dict.get("required_skills", []))
    all_keywords.update(jd_dict.get("preferred_skills", []))
    all_keywords.update(jd_dict.get("keywords", []))

    if not all_keywords:
        return 0.0

    matched = sum(
        1 for kw in all_keywords if _match_keyword_in_text(kw, resume_text) is not None
    )
    return (matched / len(all_keywords)) * 100


def analyze_keyword_gaps(
    jd_keywords: _JdKeywordsInput,
    tailored: _ResumeInput,
    master: _ResumeInput,
) -> KeywordGapAnalysis:
    """Analyze which JD keywords are missing from the tailored resume.

    Args:
        jd_keywords: A ``JobDescription`` instance or plain dict with
            ``required_skills``, ``preferred_skills``, and/or ``keywords``.
        tailored: The currently tailored resume (``ResumeDocument`` or dict).
        master: The master / source-of-truth resume (``ResumeDocument`` or
            dict). Used to determine which missing keywords are injectable.

    Returns:
        ``KeywordGapAnalysis`` with missing, injectable, and non-injectable
        keyword lists and current / potential match percentages.
    """
    jd_dict = _to_jd_keywords_dict(jd_keywords)
    tailored_dict = _to_resume_dict(tailored)
    master_dict = _to_resume_dict(master)

    tailored_text = _extract_all_text(tailored_dict).lower()
    master_text = _extract_all_text(master_dict).lower()

    # REQ (RIT-T-0126): when tailored and master resolve to near-identical text
    # there is no distinct source to inject from, so `injectable_keywords` is
    # always empty and every miss is (misleadingly) classified non-injectable.
    # Surface that degeneracy explicitly rather than presenting it as hard gaps.
    # Deterministic: exact equality OR token-set Jaccard >= 0.98.
    warnings: list[str] = []
    if _texts_near_identical(tailored_text, master_text):
        warnings.append(
            "Tailored and master resolve to near-identical content; the "
            "injectable/non-injectable split is unreliable and missing "
            "keywords may not be true gaps. Supply a distinct master resume "
            "to classify which missing keywords are injectable."
        )

    all_jd_keywords: set[str] = set()
    all_jd_keywords.update(jd_dict.get("required_skills", []))
    all_jd_keywords.update(jd_dict.get("preferred_skills", []))
    all_jd_keywords.update(jd_dict.get("keywords", []))

    missing: list[str] = []
    injectable: list[str] = []
    non_injectable: list[str] = []
    matched_keywords: list[MatchedKeyword] = []

    # Sorted iteration so output ordering is deterministic regardless of the
    # set's iteration order (REQ: identical inputs → identical output ordering).
    for keyword in sorted(all_jd_keywords):
        result = _match_keyword_in_text(keyword, tailored_text)
        if result is not None:
            # REQ-805: a JD keyword present via exact/stem/alias is NOT missing.
            # Carry its provenance so downstream can distinguish synonym hits.
            matched_keywords.append(
                MatchedKeyword(
                    keyword=keyword,
                    kind=result.kind if result.kind is not None else "exact",
                    canonical=result.canonical,
                )
            )
            continue
        missing.append(keyword)
        if _match_keyword_in_text(keyword, master_text) is not None:
            injectable.append(keyword)
        else:
            non_injectable.append(keyword)

    total = len(all_jd_keywords) if all_jd_keywords else 1
    current_match = (total - len(missing)) / total * 100
    potential_match = (total - len(non_injectable)) / total * 100

    return KeywordGapAnalysis(
        missing_keywords=missing,
        injectable_keywords=injectable,
        non_injectable_keywords=non_injectable,
        current_match_percentage=current_match,
        potential_match_percentage=potential_match,
        matched_keywords=matched_keywords,
        warnings=warnings,
    )
