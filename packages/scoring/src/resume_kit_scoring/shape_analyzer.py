"""Read-only deterministic resume shape analyzer (RIT-T-0135)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from resume_kit_matching.keywords import _TOKEN_RE
from resume_kit_policy import ResumeShapePolicy, normalize_section_heading
from resume_kit_schemas.canonical import CanonicalSection
from resume_kit_schemas.resume import (
    AdditionalInfo,
    CustomSection,
    CustomSectionItem,
    ResumeDocument,
    SectionMeta,
    SectionType,
)
from resume_kit_schemas.shape import ShapeFinding, ShapeFindingFamily, ShapeReport

_MAPPING_CONFIDENCE = 1.0
_UNMAPPED_CONFIDENCE = 0.0
_MIN_OVERLAP_TOKENS = 2
_DUPLICATE_JACCARD_THRESHOLD = 0.92
_REDUNDANT_CONTAINMENT_THRESHOLD = 0.80
_CANONICAL_DUPLICATE_JACCARD_THRESHOLD = 0.80


@dataclass(frozen=True)
class _SectionContent:
    """Normalized section text used for shape analysis only."""

    name: str
    target: CanonicalSection
    text_parts: tuple[str, ...]
    first_item: str | None = None

    @property
    def tokens(self) -> frozenset[str]:
        return _token_set(self.text_parts)


def analyze_resume_shape(resume: ResumeDocument, policy: ResumeShapePolicy) -> ShapeReport:
    """Return read-only findings describing resume shape divergence.

    The analyzer is deterministic, side-effect-free, and never mutates ``resume``.
    It reports only structural facts; any later transform decides what to apply.
    """

    custom_sections = _custom_sections(resume, policy)
    canonical_sections = _canonical_sections(resume)
    all_sections = [*canonical_sections, *custom_sections]

    findings: list[ShapeFinding] = []
    findings.extend(_custom_section_mapping_findings(custom_sections))
    findings.extend(_embedded_heading_findings(all_sections))
    findings.extend(_custom_overlap_findings(custom_sections))
    findings.extend(_canonical_duplicate_findings(custom_sections, canonical_sections))
    findings.extend(_section_order_findings(resume, policy, custom_sections))
    findings.extend(_budget_findings(resume, policy))

    findings = sorted(findings, key=_finding_sort_key)
    count = len(findings)
    return ShapeReport(
        findings=findings,
        summary=f"{count} shape finding{'s' if count != 1 else ''}",
    )


def _custom_section_mapping_findings(
    custom_sections: list[_SectionContent],
) -> list[ShapeFinding]:
    findings: list[ShapeFinding] = []
    for section in custom_sections:
        if section.target is CanonicalSection.OTHER:
            findings.append(
                ShapeFinding(
                    family=ShapeFindingFamily.CUSTOM_SECTION_UNMAPPED,
                    code="custom_section_unmapped",
                    section=section.name,
                    message=(
                        f"Custom section '{section.name}' does not confidently map to a "
                        "canonical section; preserve as other unless a user decides otherwise."
                    ),
                    proposed_target=CanonicalSection.OTHER,
                    confidence=_UNMAPPED_CONFIDENCE,
                )
            )
            continue

        findings.append(
            ShapeFinding(
                family=ShapeFindingFamily.CUSTOM_SECTION_MAPPED,
                code="custom_section_mapped",
                section=section.name,
                message=(
                    f"Custom section '{section.name}' maps to canonical "
                    f"'{section.target.value}' by policy alias."
                ),
                proposed_target=section.target,
                confidence=_MAPPING_CONFIDENCE,
            )
        )
    return findings


def _embedded_heading_findings(sections: list[_SectionContent]) -> list[ShapeFinding]:
    findings: list[ShapeFinding] = []
    for section in sections:
        first_item = section.first_item
        if first_item is None:
            continue
        if normalize_section_heading(first_item) != normalize_section_heading(section.name):
            continue
        findings.append(
            ShapeFinding(
                family=ShapeFindingFamily.EMBEDDED_HEADING_LINE,
                code="embedded_heading_line",
                section=section.name,
                message=(
                    f"First list item in '{section.name}' repeats the section heading."
                ),
                proposed_target=section.target,
            )
        )
    return findings


def _custom_overlap_findings(custom_sections: list[_SectionContent]) -> list[ShapeFinding]:
    findings: list[ShapeFinding] = []
    ordered = sorted(custom_sections, key=lambda section: _section_sort_name(section.name))
    for left_index, left in enumerate(ordered):
        for right in ordered[left_index + 1 :]:
            overlap = _overlap(left.tokens, right.tokens)
            if overlap.intersection_size < _MIN_OVERLAP_TOKENS:
                continue
            section_name = _pair_name(left.name, right.name)
            if overlap.jaccard >= _DUPLICATE_JACCARD_THRESHOLD:
                findings.append(
                    ShapeFinding(
                        family=ShapeFindingFamily.DUPLICATE_SECTION_CONTENT,
                        code="duplicate_section_content",
                        section=section_name,
                        message=(
                            f"Sections '{left.name}' and '{right.name}' have near-identical "
                            "token-set content."
                        ),
                        proposed_target=left.target if left.target == right.target else None,
                        confidence=overlap.jaccard,
                    )
                )
            elif overlap.containment >= _REDUNDANT_CONTAINMENT_THRESHOLD:
                findings.append(
                    ShapeFinding(
                        family=ShapeFindingFamily.REDUNDANT_SECTION,
                        code="redundant_section",
                        section=section_name,
                        message=(
                            f"Sections '{left.name}' and '{right.name}' substantially overlap "
                            "by token-set containment."
                        ),
                        proposed_target=left.target if left.target == right.target else None,
                        confidence=overlap.containment,
                    )
                )
    return findings


def _canonical_duplicate_findings(
    custom_sections: list[_SectionContent],
    canonical_sections: list[_SectionContent],
) -> list[ShapeFinding]:
    findings: list[ShapeFinding] = []
    sorted_custom = sorted(custom_sections, key=lambda section: _section_sort_name(section.name))
    sorted_canonical = sorted(
        canonical_sections,
        key=lambda section: _section_sort_name(section.name),
    )
    for custom in sorted_custom:
        for canonical in sorted_canonical:
            if custom.target is CanonicalSection.OTHER or custom.target != canonical.target:
                continue
            overlap = _overlap(custom.tokens, canonical.tokens)
            if overlap.intersection_size < _MIN_OVERLAP_TOKENS:
                continue
            if overlap.jaccard < _CANONICAL_DUPLICATE_JACCARD_THRESHOLD:
                continue
            findings.append(
                ShapeFinding(
                    family=ShapeFindingFamily.CANONICAL_FIELD_DUPLICATE,
                    code="canonical_field_duplicate",
                    section=f"{custom.name} <-> {canonical.name}",
                    message=(
                        f"Custom section '{custom.name}' duplicates canonical field "
                        f"'{canonical.name}'."
                    ),
                    proposed_target=custom.target,
                    confidence=overlap.jaccard,
                )
            )
    return findings


def _section_order_findings(
    resume: ResumeDocument,
    policy: ResumeShapePolicy,
    custom_sections: list[_SectionContent],
) -> list[ShapeFinding]:
    observed = _observed_order(resume, policy, custom_sections)
    policy_index = {section: index for index, section in enumerate(policy.section_order)}
    fallback_index = len(policy.section_order)
    findings: list[ShapeFinding] = []
    highest_seen = -1

    for name, target in observed:
        current = policy_index.get(target, fallback_index)
        if current < highest_seen:
            findings.append(
                ShapeFinding(
                    family=ShapeFindingFamily.SECTION_ORDER_VIOLATION,
                    code="section_order_violation",
                    section=name,
                    message=(
                        f"Section '{name}' appears out of canonical order for "
                        f"'{target.value}'."
                    ),
                    proposed_target=target,
                )
            )
            continue
        highest_seen = current
    return findings


def _budget_findings(resume: ResumeDocument, policy: ResumeShapePolicy) -> list[ShapeFinding]:
    budgets = policy.informational_budgets
    findings: list[ShapeFinding] = []

    skills_count = len([skill for skill in resume.additional.technicalSkills if skill.strip()])
    if budgets.max_skills is not None and skills_count > budgets.max_skills:
        findings.append(
            ShapeFinding(
                family=ShapeFindingFamily.BUDGET_INFO,
                code="skills_count_budget",
                section="additional.technicalSkills",
                message=(
                    f"Skills count is {skills_count}; informational budget is "
                    f"{budgets.max_skills}."
                ),
                proposed_target=CanonicalSection.SKILLS,
            )
        )

    summary = resume.summary.strip()
    if summary:
        summary_words = len(summary.split())
        if budgets.max_summary_words is not None and summary_words > budgets.max_summary_words:
            findings.append(
                ShapeFinding(
                    family=ShapeFindingFamily.BUDGET_INFO,
                    code="summary_word_budget",
                    section="summary",
                    message=(
                        f"Summary is {summary_words} words; informational budget is "
                        f"{budgets.max_summary_words}."
                    ),
                    proposed_target=CanonicalSection.BASICS,
                )
            )
        summary_chars = len(summary)
        if budgets.max_summary_chars is not None and summary_chars > budgets.max_summary_chars:
            findings.append(
                ShapeFinding(
                    family=ShapeFindingFamily.BUDGET_INFO,
                    code="summary_char_budget",
                    section="summary",
                    message=(
                        f"Summary is {summary_chars} characters; informational budget is "
                        f"{budgets.max_summary_chars}."
                    ),
                    proposed_target=CanonicalSection.BASICS,
                )
            )

    if budgets.max_bullets_per_role is not None:
        for index, experience in enumerate(resume.workExperience):
            bullet_count = len([bullet for bullet in experience.description if bullet.strip()])
            if bullet_count <= budgets.max_bullets_per_role:
                continue
            section = f"workExperience[{experience.id or index}]"
            findings.append(
                ShapeFinding(
                    family=ShapeFindingFamily.BUDGET_INFO,
                    code="role_bullet_budget",
                    section=section,
                    message=(
                        f"Role has {bullet_count} bullets; informational budget is "
                        f"{budgets.max_bullets_per_role}."
                    ),
                    proposed_target=CanonicalSection.WORK,
                )
            )

    return findings


@dataclass(frozen=True)
class _Overlap:
    intersection_size: int
    jaccard: float
    containment: float


def _overlap(left: frozenset[str], right: frozenset[str]) -> _Overlap:
    if not left or not right:
        return _Overlap(intersection_size=0, jaccard=0.0, containment=0.0)
    intersection = left & right
    union = left | right
    smaller_size = min(len(left), len(right))
    return _Overlap(
        intersection_size=len(intersection),
        jaccard=len(intersection) / len(union),
        containment=len(intersection) / smaller_size if smaller_size else 0.0,
    )


def _token_set(parts: tuple[str, ...]) -> frozenset[str]:
    tokens: set[str] = set()
    for part in parts:
        tokens.update(token.casefold() for token in _TOKEN_RE.findall(part))
    return frozenset(tokens)


def _canonical_sections(resume: ResumeDocument) -> list[_SectionContent]:
    sections: list[_SectionContent] = []
    basics_parts = _nonempty(
        (
            resume.personalInfo.name,
            resume.personalInfo.title,
            resume.personalInfo.email,
            resume.personalInfo.phone,
            resume.personalInfo.location,
            resume.personalInfo.website,
            resume.personalInfo.linkedin,
            resume.personalInfo.github,
            resume.summary,
        )
    )
    if basics_parts:
        sections.append(
            _SectionContent(
                name="basics",
                target=CanonicalSection.BASICS,
                text_parts=basics_parts,
            )
        )

    work_parts: list[str] = []
    for experience in resume.workExperience:
        work_parts.extend(
            _nonempty(
                (
                    experience.title,
                    experience.company,
                    experience.location,
                    experience.years,
                    *experience.description,
                )
            )
        )
    if work_parts:
        sections.append(
            _SectionContent(
                name="workExperience",
                target=CanonicalSection.WORK,
                text_parts=tuple(work_parts),
            )
        )

    education_parts: list[str] = []
    for education in resume.education:
        education_parts.extend(
            _nonempty(
                (
                    education.institution,
                    education.degree,
                    education.years,
                    education.description,
                )
            )
        )
    if education_parts:
        sections.append(
            _SectionContent(
                name="education",
                target=CanonicalSection.EDUCATION,
                text_parts=tuple(education_parts),
            )
        )

    project_parts: list[str] = []
    for project in resume.personalProjects:
        project_parts.extend(
            _nonempty(
                (
                    project.name,
                    project.role,
                    project.years,
                    project.github,
                    project.website,
                    *project.description,
                )
            )
        )
    if project_parts:
        sections.append(
            _SectionContent(
                name="personalProjects",
                target=CanonicalSection.PROJECTS,
                text_parts=tuple(project_parts),
            )
        )

    sections.extend(_additional_sections(resume.additional))
    return sections


def _additional_sections(additional: AdditionalInfo) -> list[_SectionContent]:
    sections: list[_SectionContent] = []
    field_specs = (
        (
            "additional.technicalSkills",
            CanonicalSection.SKILLS,
            tuple(additional.technicalSkills),
        ),
        (
            "additional.certificationsTraining",
            CanonicalSection.CERTIFICATIONS,
            tuple(additional.certificationsTraining),
        ),
        ("additional.awards", CanonicalSection.AWARDS, tuple(additional.awards)),
        ("additional.languages", CanonicalSection.LANGUAGES, tuple(additional.languages)),
    )
    for name, target, parts in field_specs:
        clean_parts = _nonempty(parts)
        if not clean_parts:
            continue
        sections.append(
            _SectionContent(
                name=name,
                target=target,
                text_parts=clean_parts,
                first_item=clean_parts[0],
            )
        )
    return sections


def _custom_sections(
    resume: ResumeDocument,
    policy: ResumeShapePolicy,
) -> list[_SectionContent]:
    display_names = _custom_display_names(resume.sectionMeta)
    sections: list[_SectionContent] = []
    for key in sorted(resume.customSections):
        section = resume.customSections[key]
        name = display_names.get(key, key)
        text_parts = _custom_text_parts(section)
        sections.append(
            _SectionContent(
                name=name,
                target=policy.canonical_section_for_heading(name),
                text_parts=text_parts,
                first_item=_custom_first_item(section),
            )
        )
    return sections


def _custom_display_names(section_meta: list[SectionMeta]) -> dict[str, str]:
    display_names: dict[str, str] = {}
    for meta in section_meta:
        if meta.isDefault:
            continue
        display_names[meta.key] = meta.displayName or meta.key
    return display_names


def _custom_text_parts(section: CustomSection) -> tuple[str, ...]:
    if section.sectionType is SectionType.TEXT:
        return _nonempty((section.text,))
    if section.sectionType is SectionType.STRING_LIST:
        return _nonempty(tuple(section.strings or ()))
    if section.sectionType is SectionType.ITEM_LIST:
        parts: list[str] = []
        for item in section.items or ():
            parts.extend(_item_text_parts(item))
        return tuple(parts)
    return ()


def _custom_first_item(section: CustomSection) -> str | None:
    if section.sectionType is SectionType.STRING_LIST and section.strings:
        first = section.strings[0].strip()
        return first or None
    if section.sectionType is SectionType.ITEM_LIST and section.items:
        first = section.items[0].title.strip()
        return first or None
    return None


def _item_text_parts(item: CustomSectionItem) -> tuple[str, ...]:
    return _nonempty(
        (
            item.title,
            item.subtitle,
            item.location,
            item.years,
            *item.description,
        )
    )


def _observed_order(
    resume: ResumeDocument,
    policy: ResumeShapePolicy,
    custom_sections: list[_SectionContent],
) -> list[tuple[str, CanonicalSection]]:
    if not resume.sectionMeta:
        return _derived_canonical_order(resume, policy, custom_sections)

    by_key = {meta.key: meta for meta in resume.sectionMeta if meta.isVisible}
    ordered_meta = sorted(
        by_key.values(),
        key=lambda meta: (meta.order, _section_sort_name(meta.displayName or meta.key)),
    )
    display_names = _custom_display_names(resume.sectionMeta)
    custom_by_name = {section.name: section for section in custom_sections}
    custom_by_key = {
        key: section
        for key in resume.customSections
        for section in custom_sections
        if section.name == display_names.get(key, key)
    }

    observed: list[tuple[str, CanonicalSection]] = []
    for meta in ordered_meta:
        target = _target_for_meta(meta, resume, custom_by_key, policy)
        if target is None:
            continue
        observed.append((meta.displayName or meta.key, target))

    meta_keys = {meta.key for meta in ordered_meta}
    for key in sorted(resume.customSections):
        if key in meta_keys:
            continue
        section_name = display_names.get(key, key)
        section = custom_by_name.get(section_name)
        if section is not None:
            observed.append((section.name, section.target))
    return observed


def _derived_canonical_order(
    resume: ResumeDocument,
    policy: ResumeShapePolicy,
    custom_sections: list[_SectionContent],
) -> list[tuple[str, CanonicalSection]]:
    policy_index = {section: index for index, section in enumerate(policy.section_order)}
    fallback_index = len(policy.section_order)
    all_sections = [*_canonical_sections(resume), *custom_sections]
    ordered = sorted(
        all_sections,
        key=lambda section: (
            policy_index.get(section.target, fallback_index),
            _section_sort_name(section.name),
        ),
    )
    return [(section.name, section.target) for section in ordered]


def _target_for_meta(
    meta: SectionMeta,
    resume: ResumeDocument,
    custom_by_key: dict[str, _SectionContent],
    policy: ResumeShapePolicy,
) -> CanonicalSection | None:
    if meta.key == "personalInfo" and _has_basics(resume):
        return CanonicalSection.BASICS
    if meta.key == "summary" and resume.summary.strip():
        return CanonicalSection.BASICS
    if meta.key == "workExperience" and resume.workExperience:
        return CanonicalSection.WORK
    if meta.key == "education" and resume.education:
        return CanonicalSection.EDUCATION
    if meta.key == "personalProjects" and resume.personalProjects:
        return CanonicalSection.PROJECTS
    if meta.key == "additional":
        return _first_additional_target(resume.additional, policy)
    custom = custom_by_key.get(meta.key)
    if custom is not None:
        return custom.target
    if meta.isDefault:
        return None
    return policy.canonical_section_for_heading(meta.displayName or meta.key)


def _first_additional_target(
    additional: AdditionalInfo,
    policy: ResumeShapePolicy,
) -> CanonicalSection | None:
    present = {
        CanonicalSection.SKILLS: bool(_nonempty(tuple(additional.technicalSkills))),
        CanonicalSection.CERTIFICATIONS: bool(_nonempty(tuple(additional.certificationsTraining))),
        CanonicalSection.AWARDS: bool(_nonempty(tuple(additional.awards))),
        CanonicalSection.LANGUAGES: bool(_nonempty(tuple(additional.languages))),
    }
    for target in policy.section_order:
        if present.get(target, False):
            return target
    return None


def _has_basics(resume: ResumeDocument) -> bool:
    return bool(
        _nonempty(
            (
                resume.personalInfo.name,
                resume.personalInfo.title,
                resume.personalInfo.email,
                resume.personalInfo.phone,
                resume.personalInfo.location,
                resume.personalInfo.website,
                resume.personalInfo.linkedin,
                resume.personalInfo.github,
                resume.summary,
            )
        )
    )


def _nonempty(parts: Iterable[str | None]) -> tuple[str, ...]:
    return tuple(part.strip() for part in parts if part is not None and part.strip())


def _pair_name(left: str, right: str) -> str:
    ordered = sorted((left, right), key=_section_sort_name)
    return f"{ordered[0]} <-> {ordered[1]}"


def _section_sort_name(name: str) -> str:
    return normalize_section_heading(name) or name.casefold()


def _finding_sort_key(
    finding: ShapeFinding,
) -> tuple[str, str, str, str, str]:
    return (
        finding.family.value,
        _section_sort_name(finding.section),
        finding.code,
        finding.proposed_target.value if finding.proposed_target is not None else "",
        finding.message,
    )


__all__ = ["analyze_resume_shape"]
