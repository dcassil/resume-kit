"""Render-only de-duplication helpers for resume export."""

from __future__ import annotations

import re
from collections.abc import Iterable

from resume_kit_schemas.resume import (
    CustomSection,
    ResumeDocument,
    SectionMeta,
    SectionType,
)

_SKILL_NAME_RE = re.compile(r"\bskills?\b", re.IGNORECASE)
_SKILL_SPLIT_RE = re.compile(r"[,;|\n]+")
_SPACE_RE = re.compile(r"\s+")


def dedupe_skill_custom_sections_for_render(resume: ResumeDocument) -> ResumeDocument:
    """Return a render copy with skills sourced from ``additional`` only.

    Historical parsed resumes could put the same skills into both
    ``additional.technicalSkills`` and a visible custom Skills section. Export
    should not materialize both, so skill-like custom sections are folded into
    the flat ATS-friendly skills list before rendering.
    """

    names = _custom_section_names(resume.sectionMeta)
    technical_skills = _clean_unique(resume.additional.technicalSkills)
    custom_sections: dict[str, CustomSection] = {}
    removed_keys: set[str] = set()

    for key, section in resume.customSections.items():
        display_name = names.get(key, key)
        if _is_skill_section(key, display_name):
            technical_skills = _clean_unique(
                [*technical_skills, *_skill_terms(section, display_name)]
            )
            removed_keys.add(key)
            continue
        custom_sections[key] = section

    if not removed_keys and technical_skills == resume.additional.technicalSkills:
        return resume

    additional = resume.additional.model_copy(
        update={"technicalSkills": technical_skills}
    )
    section_meta = [
        meta
        for meta in resume.sectionMeta
        if meta.key not in removed_keys and meta.id not in removed_keys
    ]
    return resume.model_copy(
        update={
            "additional": additional,
            "customSections": custom_sections,
            "sectionMeta": section_meta,
        }
    )


def _custom_section_names(section_meta: Iterable[SectionMeta]) -> dict[str, str]:
    names: dict[str, str] = {}
    for meta in section_meta:
        display_name = meta.displayName or meta.key or meta.id
        names[meta.key] = display_name
        names[meta.id] = display_name
    return names


def _is_skill_section(key: str, display_name: str) -> bool:
    return bool(_SKILL_NAME_RE.search(key) or _SKILL_NAME_RE.search(display_name))


def _skill_terms(section: CustomSection, display_name: str) -> list[str]:
    if section.sectionType == SectionType.STRING_LIST:
        return _split_skill_lines(section.strings or [], display_name)
    if section.sectionType == SectionType.TEXT:
        return _split_skill_lines([section.text or ""], display_name)
    return []


def _split_skill_lines(values: Iterable[str], display_name: str) -> list[str]:
    terms: list[str] = []
    display_key = _normalize(display_name)
    for value in values:
        line = value.strip()
        if not line or _normalize(line) == display_key:
            continue
        if ":" in line:
            line = line.split(":", 1)[1]
        terms.extend(part.strip() for part in _SKILL_SPLIT_RE.split(line) if part.strip())
    return terms


def _clean_unique(values: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        cleaned = value.strip()
        key = _normalize(cleaned)
        if not cleaned or key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


def _normalize(value: str) -> str:
    return _SPACE_RE.sub(" ", value.strip().casefold())
