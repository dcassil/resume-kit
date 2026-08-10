"""Deterministic resume projections (RIT-T-0106 / RIT-T-0137).

Produces the canonical ATS view (:class:`~resume_kit_schemas.ScoreDoc`) from a
:class:`~resume_kit_schemas.ResumeDocument` in code — no rendering, no text
extraction, no clock reads. All date-derived values come from a caller-supplied
``reference_date`` so the projection is pure: identical ``(resume,
reference_date)`` yields a byte-identical ScoreDoc.

See RIT-T-0104 (design) and RIT-A-0002 for the contract.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Protocol

from resume_kit_schemas import (
    AdditionalInfo,
    CustomSection,
    CustomSectionItem,
    KeywordZone,
    PersonalInfo,
    ResumeDocument,
    ScoreDegree,
    ScoreDoc,
    ScoreEntities,
    ScoreRole,
    ScoreSection,
    SectionMeta,
    ZonedKeywordIndex,
)
from resume_kit_schemas import (
    Education as BuildEducation,
)
from resume_kit_schemas import (
    Experience as BuildExperience,
)
from resume_kit_schemas import (
    Project as BuildProject,
)
from resume_kit_schemas.canonical import (
    Award,
    Certification,
    CustomContentSection,
    Link,
    LinkType,
    Location,
)
from resume_kit_schemas.canonical import (
    Education as CanonicalEducation,
)
from resume_kit_schemas.canonical import (
    Experience as CanonicalExperience,
)
from resume_kit_schemas.canonical import (
    Project as CanonicalProject,
)
from resume_kit_schemas.canonical import (
    Resume as CanonicalResume,
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


class _NamedItem(Protocol):
    name: str


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


def _first_link(links: list[Link], link_type: LinkType) -> str | None:
    for link in links:
        if link.type is link_type and link.url.strip():
            return link.url
    return None


def _location_text(location: Location | str | None) -> str | None:
    if location is None:
        return None
    if isinstance(location, str):
        return location if location.strip() else None
    if location.address and location.address.strip():
        return location.address
    parts = [
        part
        for part in (
            location.city,
            location.region,
            location.countryCode,
            location.postalCode,
        )
        if part is not None and part.strip()
    ]
    return ", ".join(parts) if parts else None


def _format_range(
    start: str | None,
    end: str | None,
    *,
    fallback: str | None = None,
) -> str:
    if start and end:
        return f"{start} - {end}"
    if start:
        return start
    if end:
        return end
    return fallback or ""


def _unique_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        normalized = " ".join(value.split())
        if not normalized:
            continue
        key = normalized.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def _build_experience(entry: CanonicalExperience, index: int) -> BuildExperience:
    return BuildExperience(
        id=index + 1,
        title=entry.title,
        company=entry.organization,
        location=_location_text(entry.location),
        years=_format_range(entry.startDate, entry.endDate, fallback=entry.summary),
        description=[achievement.text for achievement in entry.achievements],
    )


def _build_education(
    entry: CanonicalEducation,
    index: int,
) -> BuildEducation:
    degree = entry.degree or entry.field or ""
    years = _format_range(entry.startDate, entry.endDate)
    highlights = list(entry.highlights)
    courses = list(entry.courses)
    score = entry.score
    description = "\n".join(_unique_text([*highlights, *courses, score or ""])) or None
    return BuildEducation(
        id=index + 1,
        institution=entry.institution,
        degree=degree,
        years=years,
        description=description,
    )


def _build_project(entry: CanonicalProject, index: int) -> BuildProject:
    descriptions = _unique_text(
        [
            entry.description or "",
            *(achievement.text for achievement in entry.achievements),
        ]
    )
    return BuildProject(
        id=index + 1,
        name=entry.name,
        role=", ".join(entry.roles),
        years=_format_range(entry.startDate, entry.endDate),
        github=_first_link(entry.links, LinkType.GITHUB),
        website=_first_link(entry.links, LinkType.WEBSITE)
        or _first_link(entry.links, LinkType.PROJECT),
        description=descriptions,
    )


def _custom_named_section(
    *,
    values: Sequence[_NamedItem],
    key: str,
    display_name: str,
    order: int,
) -> tuple[SectionMeta, CustomSection] | None:
    names = _unique_text([value.name for value in values])
    if not names:
        return None
    return (
        SectionMeta(
            id=key,
            key=key,
            displayName=display_name,
            sectionType=SectionType.STRING_LIST,
            isDefault=False,
            isVisible=True,
            order=order,
        ),
        CustomSection(sectionType=SectionType.STRING_LIST, strings=names),
    )


def _custom_item_section(
    *,
    values: Sequence[_NamedItem],
    key: str,
    display_name: str,
    order: int,
) -> tuple[SectionMeta, CustomSection] | None:
    items: list[CustomSectionItem] = []
    for index, value in enumerate(values):
        if not value.name.strip():
            continue
        items.append(CustomSectionItem(id=index + 1, title=value.name))
    if not items:
        return None
    return (
        SectionMeta(
            id=key,
            key=key,
            displayName=display_name,
            sectionType=SectionType.ITEM_LIST,
            isDefault=False,
            isVisible=True,
            order=order,
        ),
        CustomSection(sectionType=SectionType.ITEM_LIST, items=items),
    )


def _preserved_custom_section(
    preserved: CustomContentSection,
    *,
    order: int,
) -> tuple[SectionMeta, CustomSection] | None:
    lines = _unique_text(preserved.lines)
    if not lines:
        return None
    key = re.sub(r"[^a-z0-9]+", "-", preserved.heading.strip().casefold()).strip("-")
    key = key or f"custom-{order}"
    return (
        SectionMeta(
            id=key,
            key=key,
            displayName=preserved.heading,
            sectionType=SectionType.STRING_LIST,
            isDefault=False,
            isVisible=True,
            order=order,
        ),
        CustomSection(sectionType=SectionType.STRING_LIST, strings=lines),
    )


def _certification_names(values: list[Certification]) -> list[str]:
    names: list[str] = []
    for value in values:
        parts = [value.name]
        if value.issuer:
            parts.append(value.issuer)
        if value.date:
            parts.append(value.date)
        names.append(" - ".join(parts))
    return _unique_text(names)


def _award_names(values: list[Award]) -> list[str]:
    return _unique_text([value.name for value in values])


def _technical_skills(resume: CanonicalResume) -> list[str]:
    values: list[str] = []
    for group in resume.skills:
        values.extend(group.keywords)
    for entry in resume.work:
        values.extend(entry.skills)
        values.extend(entry.technologies)
    for project in resume.projects:
        values.extend(project.skills)
        values.extend(project.technologies)
    return _unique_text(values)


def project_builddoc_from_canonical(resume: CanonicalResume) -> ResumeDocument:
    """Project canonical ``Resume`` data back to the BuildDoc read model.

    This is the inverse-direction bridge used by the structure pass before the
    unchanged standardize wording logic runs. It is pure and deterministic:
    canonical achievement text stays verbatim, canonical skill keywords become
    ``additional.technicalSkills``, and optional collections without native
    BuildDoc fields are preserved as custom sections.
    """

    info = resume.basics
    additional = AdditionalInfo(
        technicalSkills=_technical_skills(resume),
        languages=_unique_text([language.name for language in resume.languages]),
        certificationsTraining=_certification_names(resume.certifications),
        awards=_award_names(resume.awards),
    )
    custom_sections: dict[str, CustomSection] = {}
    section_meta: list[SectionMeta] = []
    custom_specs = [
        _custom_named_section(
            values=resume.publications,
            key="publications",
            display_name="Publications",
            order=6,
        ),
        _custom_item_section(
            values=resume.volunteer,
            key="volunteer",
            display_name="Volunteer",
            order=7,
        ),
        _custom_named_section(
            values=resume.interests,
            key="interests",
            display_name="Interests",
            order=8,
        ),
        _custom_named_section(
            values=resume.references,
            key="references",
            display_name="References",
            order=9,
        ),
    ]
    for spec in custom_specs:
        if spec is None:
            continue
        meta, section = spec
        section_meta.append(meta)
        custom_sections[meta.key] = section

    # Round-trip the canonical "other" holding slot (RIT-T-0161) back to BuildDoc
    # custom sections so preserved content survives the projection unchanged.
    for offset, preserved in enumerate(resume.custom):
        spec = _preserved_custom_section(preserved, order=10 + offset)
        if spec is None:
            continue
        meta, section = spec
        section_meta.append(meta)
        custom_sections[meta.key] = section

    return ResumeDocument(
        personalInfo=PersonalInfo(
            name=info.name,
            title=info.headline or "",
            email=info.email or "",
            phone=info.phone or "",
            location=_location_text(info.location) or "",
            website=_first_link(info.links, LinkType.WEBSITE)
            or _first_link(info.links, LinkType.PORTFOLIO),
            linkedin=_first_link(info.links, LinkType.LINKEDIN),
            github=_first_link(info.links, LinkType.GITHUB),
        ),
        summary=info.summary or "",
        workExperience=[
            _build_experience(entry, index) for index, entry in enumerate(resume.work)
        ],
        education=[_build_education(entry, index) for index, entry in enumerate(resume.education)],
        personalProjects=[
            _build_project(entry, index) for index, entry in enumerate(resume.projects)
        ],
        additional=additional,
        sectionMeta=section_meta,
        customSections=custom_sections,
    )


def is_canonical_resume_payload(raw: object) -> bool:
    """Return ``True`` when ``raw`` is a canonical :class:`Resume` JSON payload.

    The canonical ``Resume`` form (the ``structure`` version's on-disk shape)
    carries a ``basics`` block and does not use ``ResumeDocument``'s
    ``personalInfo`` key. ``ResumeDocument.model_validate`` would accept such a
    payload leniently and silently drop the experience bullets (they live under
    canonical ``work[].achievements``, not ``workExperience[].description``),
    which is exactly the read-only best-practices misread this guards against.
    """
    if not isinstance(raw, Mapping):
        return False
    return "basics" in raw and "personalInfo" not in raw


def normalize_resume_input(raw: object) -> ResumeDocument:
    """Coerce a raw resume JSON payload into the BuildDoc read model.

    A canonical ``Resume`` payload (the ``structure`` version) is projected via
    :func:`project_builddoc_from_canonical` — the same bridge ``build_refine``
    uses — so its experience bullets survive into the analyzable read model.
    Any other payload is validated directly as a :class:`ResumeDocument`.

    This is the single normalization seam every read-only surface routes raw
    resume input through, guaranteeing the read-only best-practices path and the
    ``build_refine`` internal analyzer read canonical structure identically.
    """
    if is_canonical_resume_payload(raw):
        return project_builddoc_from_canonical(CanonicalResume.model_validate(raw))
    return ResumeDocument.model_validate(raw)


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
