"""Deterministic ``BuildDoc -> ScoreDoc`` projection (RIT-T-0106).

Produces the canonical ATS view (:class:`~resume_kit_schemas.ScoreDoc`) from a
:class:`~resume_kit_schemas.ResumeDocument` in code — no rendering, no text
extraction, no clock reads. All date-derived values come from a caller-supplied
``reference_date`` so the projection is pure: identical ``(resume,
reference_date)`` yields a byte-identical ScoreDoc.

See RIT-T-0104 (design) and RIT-A-0002 for the contract.
"""

from __future__ import annotations

import re
from datetime import date

from resume_kit_schemas import (
    CustomSection,
    KeywordZone,
    ResumeDocument,
    ScoreDegree,
    ScoreDoc,
    ScoreEntities,
    ScoreRole,
    ScoreSection,
    ZonedKeywordIndex,
)
from resume_kit_schemas.resume import SectionType
from resume_kit_terms import normalize

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
_YEAR_RE = re.compile(r"(19|20)\d{2}")
_OPEN_END_RE = re.compile(r"present|current|now|ongoing", re.IGNORECASE)
_TOKEN_RE = re.compile(r"[A-Za-z0-9+#.]+")
#: Split a "years" string into its two endpoints on common range separators.
_RANGE_SPLIT_RE = re.compile(r"\s*(?:-|–|—|to)\s*", re.IGNORECASE)


def _custom_zone(name: str) -> KeywordZone:
    """Map a custom-section *name* to a keyword zone by keyword heuristic."""
    low = name.lower()
    if "skill" in low:
        return KeywordZone.SKILLS_LIST
    if "experience" in low or "employment" in low or "work" in low:
        return KeywordZone.EXPERIENCE
    if "education" in low or "degree" in low:
        return KeywordZone.EDUCATION
    if "project" in low:
        return KeywordZone.PROJECTS
    if "summary" in low or "objective" in low or "profile" in low:
        return KeywordZone.SUMMARY
    return KeywordZone.OTHER


def _parse_endpoint(text: str) -> int | None:
    """Return an absolute month index (year*12 + month-1) for a date token."""
    year_match = _YEAR_RE.search(text)
    if not year_match:
        return None
    year = int(year_match.group(0))
    month = 1
    low = text.lower()
    for name, num in _MONTHS.items():
        if name in low:
            month = num
            break
    return year * 12 + (month - 1)


def _reference_month(reference_date: date) -> int:
    return reference_date.year * 12 + (reference_date.month - 1)


def _parse_range(years: str, reference_date: date) -> tuple[str | None, str | None, int | None]:
    """Parse a "years" range into (start_raw, end_raw, duration_months).

    ``duration_months`` is ``None`` when the start cannot be parsed. Open-ended
    ends ("Present"/empty) resolve to ``reference_date``.
    """
    if not years or not years.strip():
        return None, None, None
    parts = _RANGE_SPLIT_RE.split(years.strip(), maxsplit=1)
    start_raw = parts[0].strip() or None
    end_raw = parts[1].strip() if len(parts) > 1 else None

    start_month = _parse_endpoint(start_raw) if start_raw else None
    if start_month is None:
        return start_raw, end_raw, None

    if end_raw is None or _OPEN_END_RE.search(end_raw or ""):
        end_month = _reference_month(reference_date)
    else:
        parsed_end = _parse_endpoint(end_raw)
        end_month = parsed_end if parsed_end is not None else _reference_month(reference_date)

    duration = max(0, end_month - start_month)
    return start_raw, end_raw, duration


def _union_years(intervals: list[tuple[int, int]]) -> float:
    """Total distinct months across (start_month, end_month) intervals / 12."""
    if not intervals:
        return 0.0
    ordered = sorted(intervals)
    total = 0
    cur_start, cur_end = ordered[0]
    for start, end in ordered[1:]:
        if start <= cur_end:  # overlap or adjacency -> merge
            cur_end = max(cur_end, end)
        else:
            total += cur_end - cur_start
            cur_start, cur_end = start, end
    total += cur_end - cur_start
    return round(total / 12, 1)


def _tokens(text: str) -> list[str]:
    """Deterministic, normalized, de-duplicated token list from *text*."""
    seen: dict[str, None] = {}
    for raw in _TOKEN_RE.findall(text):
        norm = normalize(raw)
        if norm:
            seen.setdefault(norm, None)
    return list(seen)


def _sections(resume: ResumeDocument) -> list[ScoreSection]:
    sections: list[ScoreSection] = []
    if resume.summary.strip():
        sections.append(
            ScoreSection(name="Summary", zone=KeywordZone.SUMMARY, text=resume.summary)
        )
    for exp in resume.workExperience:
        text = " ".join([exp.title, exp.company, *exp.description]).strip()
        sections.append(
            ScoreSection(name="Experience", zone=KeywordZone.EXPERIENCE, text=text)
        )
    skills = list(resume.additional.technicalSkills) + list(resume.additional.languages)
    if skills:
        sections.append(
            ScoreSection(name="Skills", zone=KeywordZone.SKILLS_LIST, text=", ".join(skills))
        )
    for edu in resume.education:
        text = " ".join([edu.degree, edu.institution, edu.description or ""]).strip()
        sections.append(
            ScoreSection(name="Education", zone=KeywordZone.EDUCATION, text=text)
        )
    for proj in resume.personalProjects:
        text = " ".join([proj.name, proj.role, *proj.description]).strip()
        sections.append(
            ScoreSection(name="Projects", zone=KeywordZone.PROJECTS, text=text)
        )
    for name, custom in resume.customSections.items():
        sections.append(
            ScoreSection(
                name=name,
                zone=_custom_zone(name),
                text=_custom_text(custom),
                source_section_type=str(custom.sectionType),
            )
        )
    return sections


def _custom_text(custom: CustomSection) -> str:
    if custom.sectionType is SectionType.TEXT:
        return custom.text or ""
    if custom.sectionType is SectionType.STRING_LIST:
        return ", ".join(custom.strings or [])
    parts: list[str] = []
    for item in custom.items or []:
        parts.extend([item.title, *(item.description or [])])
    return " ".join(p for p in parts if p)


def _entities(resume: ResumeDocument, reference_date: date) -> ScoreEntities:
    info = resume.personalInfo
    links = [
        link
        for link in (info.website, info.linkedin, info.github)
        if link and link.strip()
    ]
    roles: list[ScoreRole] = []
    intervals: list[tuple[int, int]] = []
    for exp in resume.workExperience:
        start_raw, end_raw, duration = _parse_range(exp.years, reference_date)
        roles.append(
            ScoreRole(
                title=exp.title,
                company=exp.company,
                start_date=start_raw,
                end_date=end_raw,
                duration_months=duration,
            )
        )
        if duration is not None and start_raw is not None:
            start_month = _parse_endpoint(start_raw)
            if start_month is not None:
                intervals.append((start_month, start_month + duration))
    degrees = [
        ScoreDegree(degree=edu.degree, institution=edu.institution)
        for edu in resume.education
    ]
    return ScoreEntities(
        name=info.name,
        email=info.email,
        phone=info.phone,
        links=links,
        roles=roles,
        total_years_experience=_union_years(intervals),
        education=degrees,
    )


def _zoned_index(sections: list[ScoreSection]) -> ZonedKeywordIndex:
    zone_tokens: dict[KeywordZone, list[str]] = {}
    token_zones: dict[str, list[KeywordZone]] = {}
    for section in sections:
        tokens = _tokens(section.text)
        # Skills entries also contribute their full normalized phrase so a
        # multi-word categorized skill counts as one canonical skill token.
        if section.zone is KeywordZone.SKILLS_LIST:
            for entry in section.text.split(","):
                phrase = normalize(entry)
                if phrase and phrase not in tokens:
                    tokens.append(phrase)
        bucket = zone_tokens.setdefault(section.zone, [])
        for token in tokens:
            if token not in bucket:
                bucket.append(token)
            zones = token_zones.setdefault(token, [])
            if section.zone not in zones:
                zones.append(section.zone)
    return ZonedKeywordIndex(token_zones=token_zones, zone_tokens=zone_tokens)


def project_scoredoc(resume: ResumeDocument, *, reference_date: date) -> ScoreDoc:
    """Project a resume (BuildDoc) into its canonical ATS view (ScoreDoc).

    Pure and deterministic: no clock reads; ``reference_date`` drives all
    open-ended date computations. Identical inputs produce identical output.
    """
    sections = _sections(resume)
    return ScoreDoc(
        sections=sections,
        entities=_entities(resume, reference_date),
        zoned_index=_zoned_index(sections),
    )
