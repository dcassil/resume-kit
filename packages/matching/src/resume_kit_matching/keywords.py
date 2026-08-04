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
import re
from functools import lru_cache
from typing import Any

import resume_kit_schemas
from resume_kit_schemas import KeywordGapAnalysis, ResumeDocument

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
    """Normalize a skill string for case-insensitive comparisons."""
    return re.sub(r"\s+", " ", skill.strip()).casefold()


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
    # JobDescription model → upstream keyword dict shape
    required_skills: list[str] = []
    for req in jd.requirements:
        required_skills.append(req.text)
        required_skills.extend(req.keywords)
    preferred_skills: list[str] = []
    for qual in jd.qualifications:
        preferred_skills.append(qual.text)
        preferred_skills.extend(qual.keywords)
    return {
        "required_skills": required_skills,
        "preferred_skills": preferred_skills,
        "keywords": list(jd.keywords),
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

    matched = sum(1 for kw in all_keywords if _keyword_in_text(kw, resume_text))
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

    all_jd_keywords: set[str] = set()
    all_jd_keywords.update(jd_dict.get("required_skills", []))
    all_jd_keywords.update(jd_dict.get("preferred_skills", []))
    all_jd_keywords.update(jd_dict.get("keywords", []))

    missing: list[str] = []
    injectable: list[str] = []
    non_injectable: list[str] = []

    for keyword in all_jd_keywords:
        if not _keyword_in_text(keyword, tailored_text):
            missing.append(keyword)
            if _keyword_in_text(keyword, master_text):
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
    )
