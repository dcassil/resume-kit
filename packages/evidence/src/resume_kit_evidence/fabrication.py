"""Deterministic master-resume alignment: fabrication detection and removal.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/services/refiner.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc  Apache-2.0
# Modified: Extracted validate_master_alignment and fix_alignment_violations,
#   plus their deterministic helpers (_keyword_in_text, _normalize_skill_key,
#   _extract_all_text, _extract_all_text_cached, _deep_copy) into this
#   standalone module. Replaced app.schemas.* with resume_kit_schemas.analysis
#   (AlignmentReport / AlignmentViolation). Removed logging. All deterministic
#   re/text/comparison logic is faithfully preserved.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import copy
import json
import re
from functools import lru_cache
from typing import Any

from resume_kit_schemas import AlignmentReport, AlignmentViolation

# Public surface ---------------------------------------------------------------

__all__ = [
    "fix_alignment_violations",
    "validate_master_alignment",
]


# ---------------------------------------------------------------------------
# Private helpers (ported verbatim from upstream, minus logging/caching notes)
# ---------------------------------------------------------------------------


def _keyword_in_text(keyword: str, text: str) -> bool:
    """Check if keyword exists as a whole term in text.

    Uses term boundaries instead of substring matching to avoid false positives
    like 'python' matching 'pythonic' or 'go' matching 'going'.
    """
    escaped = re.escape(keyword.strip().lower())
    if not escaped:
        return False
    pattern = rf"(?<!\w){escaped}(?!\w)"
    return bool(re.search(pattern, text.lower()))


def _normalize_skill_key(skill: str) -> str:
    """Normalize a skill for case-insensitive comparisons."""
    return re.sub(r"\s+", " ", skill.strip()).casefold()


def _extract_all_text(data: dict[str, Any]) -> str:
    """Extract all text content from resume data for keyword matching."""
    data_json = json.dumps(data, sort_keys=True, default=str)
    return _extract_all_text_cached(data_json)


@lru_cache(maxsize=100)
def _extract_all_text_cached(data_json: str) -> str:
    """Cached implementation of text extraction."""
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


def _deep_copy(data: dict[str, Any]) -> dict[str, Any]:
    """Create a deep copy of a dictionary."""
    return copy.deepcopy(data)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def validate_master_alignment(
    tailored: dict[str, Any],
    master: dict[str, Any],
    allowed_new_skills: set[str] | None = None,
) -> AlignmentReport:
    """Verify tailored resume doesn't contain fabricated content.

    Checks that all skills, certifications, and work experience companies in the
    tailored resume exist in the master resume. Skills that are variants of a
    master skill (substring/containment) or that appear anywhere in the master
    resume text are flagged only as ``info``. Verified JD-added skills passed
    via ``allowed_new_skills`` are exempt.

    Args:
        tailored: Tailored resume data.
        master: Master resume data (source of truth).
        allowed_new_skills: Skills verified as present in the JD, allowed to be
            added even though absent from the master.

    Returns:
        AlignmentReport with violations and confidence score.
    """
    violations: list[AlignmentViolation] = []

    # Check skills - use full resume text for broader matching
    tailored_skills = {
        s.lower()
        for s in tailored.get("additional", {}).get("technicalSkills", [])
        if isinstance(s, str)
    }
    master_skills = {
        s.lower()
        for s in master.get("additional", {}).get("technicalSkills", [])
        if isinstance(s, str)
    }
    allowed_skills = {
        _normalize_skill_key(skill)
        for skill in (allowed_new_skills or set())
        if isinstance(skill, str) and skill.strip()
    }
    master_full_text = _extract_all_text(master).lower()

    for skill in tailored_skills - master_skills:
        if _normalize_skill_key(skill) in allowed_skills:
            continue
        # Check substring/containment: e.g. "Python" in "Python 3.x"
        has_substring_match = any(
            skill in ms or ms in skill for ms in master_skills if ms
        )
        # Check if skill appears anywhere in master resume text
        found_in_text = _keyword_in_text(skill, master_full_text)

        if has_substring_match or found_in_text:
            violations.append(
                AlignmentViolation(
                    field_path="additional.technicalSkills",
                    violation_type="skill_variant",
                    value=skill,
                    severity="info",
                )
            )
        else:
            violations.append(
                AlignmentViolation(
                    field_path="additional.technicalSkills",
                    violation_type="fabricated_skill",
                    value=skill,
                    severity="critical",
                )
            )

    # Check certifications
    tailored_certs = {
        c.lower()
        for c in tailored.get("additional", {}).get("certificationsTraining", [])
        if isinstance(c, str)
    }
    master_certs = {
        c.lower()
        for c in master.get("additional", {}).get("certificationsTraining", [])
        if isinstance(c, str)
    }

    for cert in tailored_certs - master_certs:
        violations.append(
            AlignmentViolation(
                field_path="additional.certificationsTraining",
                violation_type="fabricated_cert",
                value=cert,
                severity="critical",
            )
        )

    # Check work experience companies (should not add new companies)
    tailored_companies = {
        exp.get("company", "").lower()
        for exp in tailored.get("workExperience", [])
        if isinstance(exp, dict)
    }
    master_companies = {
        exp.get("company", "").lower()
        for exp in master.get("workExperience", [])
        if isinstance(exp, dict)
    }

    for company in tailored_companies - master_companies:
        if company:  # Skip empty strings
            violations.append(
                AlignmentViolation(
                    field_path="workExperience",
                    violation_type="fabricated_company",
                    value=company,
                    severity="critical",
                )
            )

    is_aligned = len([v for v in violations if v.severity == "critical"]) == 0
    confidence = 1.0 - (len(violations) * 0.1)  # Decrease confidence per violation

    return AlignmentReport(
        is_aligned=is_aligned,
        violations=violations,
        confidence_score=max(0.0, confidence),
    )


def fix_alignment_violations(
    tailored: dict[str, Any],
    violations: list[AlignmentViolation],
) -> dict[str, Any]:
    """Remove or correct alignment violations.

    This is a local operation that removes fabricated content. Only ``critical``
    violations are acted on; ``info`` skill variants are left in place.

    Args:
        tailored: Tailored resume data.
        violations: List of alignment violations to fix.

    Returns:
        Fixed resume data.
    """
    fixed = _deep_copy(tailored)

    for violation in violations:
        if violation.severity != "critical":
            continue

        if violation.violation_type == "fabricated_skill":
            skills = fixed.get("additional", {}).get("technicalSkills", [])
            fixed.setdefault("additional", {})["technicalSkills"] = [
                s for s in skills if s.lower() != violation.value.lower()
            ]

        elif violation.violation_type == "fabricated_cert":
            certs = fixed.get("additional", {}).get("certificationsTraining", [])
            fixed.setdefault("additional", {})["certificationsTraining"] = [
                c for c in certs if c.lower() != violation.value.lower()
            ]

        elif violation.violation_type == "fabricated_company":
            if "workExperience" in fixed:
                fixed["workExperience"] = [
                    exp
                    for exp in fixed["workExperience"]
                    if exp.get("company", "").lower() != violation.value.lower()
                ]

    return fixed
