"""Non-destructive canonical resume shape transforms (RIT-T-0136)."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from enum import StrEnum

from resume_kit_matching.keywords import _TOKEN_RE
from resume_kit_policy import normalize_section_heading
from resume_kit_schemas.canonical import (
    Achievement,
    Award,
    Basics,
    CanonicalSection,
    Certification,
    CustomContentSection,
    Education,
    Experience,
    Language,
    Link,
    LinkType,
    Location,
    Project,
    Resume,
    SkillGroup,
)
from resume_kit_schemas.resume import (
    CustomSection,
    CustomSectionItem,
    ResumeDocument,
    SectionMeta,
    SectionType,
)
from resume_kit_schemas.resume import (
    Education as BuildEducation,
)
from resume_kit_schemas.resume import (
    Experience as BuildExperience,
)
from resume_kit_schemas.resume import (
    Project as BuildProject,
)
from resume_kit_schemas.shape import (
    ContentFate,
    ContentLedger,
    ContentLedgerEntry,
    SectionMapping,
    ShapeFinding,
    ShapeFindingFamily,
    ShapeFixResult,
    ShapeReport,
)

_RANGE_SPLIT_RE = re.compile(r"\s*(?:-|–|—|to)\s*", re.IGNORECASE)
_YEAR_RE = re.compile(r"^(?:19|20)\d{2}$")
_OPEN_END_RE = re.compile(r"^(?:present|current|now|ongoing)$", re.IGNORECASE)
_PARSER_ARTIFACTS = frozenset({"added_tokens", "dropped_tokens"})

_AUTO_CUSTOM_TARGETS = frozenset(
    {
        CanonicalSection.SKILLS,
        CanonicalSection.CERTIFICATIONS,
        CanonicalSection.AWARDS,
        CanonicalSection.LANGUAGES,
    }
)
_LEDGER_OK_FATES = frozenset(
    {
        ContentFate.PRESENT_AFTER,
        ContentFate.MOVED,
        ContentFate.DEDUPED,
        ContentFate.PRESERVED_AS_OTHER,
        ContentFate.PRESERVED_IN_EVIDENCE,
        ContentFate.DROPPED_AS_HEADING,
        ContentFate.DROPPED_AS_PARSER_ARTIFACT,
        ContentFate.DROPPED_BY_EXPLICIT_DECISION,
    }
)
_TARGET_REQUIRED_FATES = frozenset(
    {
        ContentFate.PRESENT_AFTER,
        ContentFate.MOVED,
        ContentFate.DEDUPED,
        ContentFate.PRESERVED_AS_OTHER,
    }
)

type ShapeDecision = CanonicalSection | SectionMapping | str


class CustomHandoffPolicy(StrEnum):
    """How ambiguous/custom source sections are handled during shape projection."""

    PRESERVE_IN_CANONICAL_CUSTOM = "preserve_in_canonical_custom"
    OMIT_AND_LEDGER_TO_EVIDENCE = "omit_and_ledger_to_evidence"


def apply_shape_transforms(
    resume: ResumeDocument,
    report: ShapeReport,
    decisions: Mapping[str, ShapeDecision] | None = None,
    *,
    custom_handoff_policy: CustomHandoffPolicy = (
        CustomHandoffPolicy.PRESERVE_IN_CANONICAL_CUSTOM
    ),
) -> ShapeFixResult:
    """Return a canonical ``Resume`` plus per-token ledger accounting.

    The transform is intentionally narrow. It moves already-structured
    BuildDoc fields and auto-safe, report-justified custom string-list sections
    into the canonical schema. Unsupported or ambiguous custom content follows
    ``custom_handoff_policy``: the legacy/default path preserves it in
    ``Resume.custom``; Flow 1 can omit that holding slot and ledger the source
    text as retained in durable evidence instead.
    """

    builder = _CanonicalBuilder()
    display_names = _custom_display_names(resume.sectionMeta)
    report_targets = _report_targets(report)
    decision_targets = _decision_targets(decisions or {})

    basics = builder.basics(resume)
    work = builder.work(resume.workExperience)
    education = builder.education(resume.education)
    projects = builder.projects(resume.personalProjects)
    builder.add_skill_group(
        "Technical Skills",
        resume.additional.technicalSkills,
        "additional.technicalSkills",
    )
    builder.add_named_items(
        target=CanonicalSection.CERTIFICATIONS,
        values=resume.additional.certificationsTraining,
        source_path="additional.certificationsTraining",
    )
    builder.add_named_items(
        target=CanonicalSection.AWARDS,
        values=resume.additional.awards,
        source_path="additional.awards",
    )
    builder.add_named_items(
        target=CanonicalSection.LANGUAGES,
        values=resume.additional.languages,
        source_path="additional.languages",
    )

    applied_sections: set[str] = set()
    deferred_sections: set[str] = set()
    for key in sorted(resume.customSections):
        section = resume.customSections[key]
        display_name = display_names.get(key, key)
        source_path = f"customSections.{key}"
        target = decision_targets.get(display_name) or report_targets.get(display_name)
        explicit = display_name in decision_targets
        if target is None or target is CanonicalSection.OTHER:
            # No first-class canonical home: account for the content through
            # the selected no-custom handoff policy rather than guessing a
            # canonical section or marking it unresolved.
            if (
                custom_handoff_policy
                is CustomHandoffPolicy.OMIT_AND_LEDGER_TO_EVIDENCE
            ):
                builder.handoff_custom_section_to_evidence(
                    section,
                    display_name,
                    source_path,
                )
            else:
                builder.preserve_custom_section(section, display_name, source_path)
            applied_sections.add(display_name)
            continue
        if not explicit and target not in _AUTO_CUSTOM_TARGETS:
            builder.unresolved_custom_section(section, display_name, source_path)
            deferred_sections.add(display_name)
            continue
        if not builder.add_custom_section(section, display_name, target, source_path):
            builder.unresolved_custom_section(section, display_name, source_path)
            deferred_sections.add(display_name)
            continue
        applied_sections.add(display_name)

    canonical = Resume(
        basics=basics,
        work=work,
        education=education,
        skills=builder.skill_groups(),
        projects=projects,
        certifications=builder.certifications,
        awards=builder.awards,
        languages=builder.languages,
        custom=builder.custom_sections,
    )
    return ShapeFixResult(
        resume=canonical,
        ledger=ContentLedger(entries=builder.ledger_entries),
        applied_findings=[
            finding
            for finding in report.findings
            if _finding_was_applied(finding, applied_sections)
        ],
        deferred_findings=[
            finding
            for finding in report.findings
            if _finding_was_deferred(finding, deferred_sections)
        ],
    )


def content_ledger_ok(ledger: ContentLedger) -> bool:
    """Return True iff every ledgered token has an allowed accounted fate."""

    for entry in ledger.entries:
        if not entry.token.strip():
            return False
        if entry.fate not in _LEDGER_OK_FATES:
            return False
        if entry.fate in _TARGET_REQUIRED_FATES and not _has_text(entry.target_path):
            return False
        if entry.fate is ContentFate.DROPPED_BY_EXPLICIT_DECISION and not _has_text(
            entry.reason
        ):
            return False
    return True


def claims_preserved_across_sections(
    before: ResumeDocument | Resume,
    after: ResumeDocument | Resume,
    ledger: ContentLedger | None = None,
) -> bool:
    """True iff global employer/title/degree/skill claims are unchanged."""

    before_claims = _global_claim_set(before)
    if ledger is not None:
        before_claims = _without_evidence_preserved_claims(before, before_claims, ledger)
    return before_claims == _global_claim_set(after)


class _CanonicalBuilder:
    def __init__(self) -> None:
        self.ledger_entries: list[ContentLedgerEntry] = []
        self._skill_keywords: dict[str, str] = {}
        self._skill_sources: dict[str, str] = {}
        self.certifications: list[Certification] = []
        self.awards: list[Award] = []
        self.languages: list[Language] = []
        self.custom_sections: list[CustomContentSection] = []
        self._certification_keys: dict[str, str] = {}
        self._award_keys: dict[str, str] = {}
        self._language_keys: dict[str, str] = {}

    def basics(self, resume: ResumeDocument) -> Basics:
        info = resume.personalInfo
        links: list[Link] = []
        for link_type, value, label, source_path in (
            (LinkType.WEBSITE, info.website, "Website", "personalInfo.website"),
            (LinkType.LINKEDIN, info.linkedin, "LinkedIn", "personalInfo.linkedin"),
            (LinkType.GITHUB, info.github, "GitHub", "personalInfo.github"),
        ):
            link_value = _optional_text(value)
            if link_value is None:
                continue
            target_path = f"basics.links[{len(links)}].url"
            links.append(Link(type=link_type, url=link_value, label=label))
            self._record_text(link_value, ContentFate.MOVED, source_path, target_path)

        location = None
        location_text = _optional_text(info.location)
        if location_text is not None:
            location = Location(address=location_text)
            self._record_text(
                location_text,
                ContentFate.MOVED,
                "personalInfo.location",
                "basics.location.address",
            )

        self._record_text(info.name, ContentFate.MOVED, "personalInfo.name", "basics.name")
        self._record_text(
            info.title,
            ContentFate.MOVED,
            "personalInfo.title",
            "basics.headline",
        )
        self._record_text(info.email, ContentFate.MOVED, "personalInfo.email", "basics.email")
        self._record_text(info.phone, ContentFate.MOVED, "personalInfo.phone", "basics.phone")
        self._record_text(resume.summary, ContentFate.MOVED, "summary", "basics.summary")
        return Basics(
            name=info.name,
            headline=_optional_text(info.title),
            summary=_optional_text(resume.summary),
            email=_optional_text(info.email),
            phone=_optional_text(info.phone),
            location=location,
            links=links,
        )

    def work(self, experiences: Iterable[BuildExperience]) -> list[Experience]:
        work: list[Experience] = []
        for index, raw in enumerate(experiences):
            source_base = f"workExperience[{index}]"
            achievements: list[Achievement] = []
            for bullet_index, bullet in enumerate(raw.description):
                if not _has_text(bullet):
                    continue
                target_path = (
                    f"work[{len(work)}].achievements[{len(achievements)}].text"
                )
                achievements.append(Achievement(text=bullet))
                self._record_text(
                    bullet,
                    ContentFate.MOVED,
                    f"{source_base}.description[{bullet_index}]",
                    target_path,
                )

            start_date, end_date, dates_are_lossless = _parse_canonical_range(raw.years)
            summary = None if dates_are_lossless else _optional_text(raw.years)
            if summary is not None:
                self._record_text(
                    raw.years,
                    ContentFate.MOVED,
                    f"{source_base}.years",
                    f"work[{len(work)}].summary",
                )
            else:
                self._record_text(
                    raw.years,
                    ContentFate.MOVED,
                    f"{source_base}.years",
                    f"work[{len(work)}].startDate",
                )

            self._record_text(
                raw.title,
                ContentFate.MOVED,
                f"{source_base}.title",
                f"work[{len(work)}].title",
            )
            self._record_text(
                raw.company,
                ContentFate.MOVED,
                f"{source_base}.company",
                f"work[{len(work)}].organization",
            )
            self._record_text(
                raw.location,
                ContentFate.MOVED,
                f"{source_base}.location",
                f"work[{len(work)}].location",
            )
            work.append(
                Experience(
                    organization=raw.company,
                    title=raw.title,
                    location=_optional_text(raw.location),
                    startDate=start_date,
                    endDate=end_date,
                    summary=summary,
                    achievements=achievements,
                )
            )
        return work

    def education(self, educations: Iterable[BuildEducation]) -> list[Education]:
        result: list[Education] = []
        for index, edu in enumerate(educations):
            source_base = f"education[{index}]"
            highlights: list[str] = []
            edu_description = edu.description
            if edu_description is not None and _has_text(edu_description):
                highlights.append(edu_description)
                self._record_text(
                    edu_description,
                    ContentFate.MOVED,
                    f"{source_base}.description",
                    f"education[{len(result)}].highlights[0]",
                )
            end_date = edu.years.strip() if _YEAR_RE.fullmatch(edu.years.strip()) else None
            if end_date is None:
                if _has_text(edu.years):
                    highlights.append(edu.years)
                    self._record_text(
                        edu.years,
                        ContentFate.MOVED,
                        f"{source_base}.years",
                        f"education[{len(result)}].highlights[{len(highlights) - 1}]",
                    )
            else:
                self._record_text(
                    edu.years,
                    ContentFate.MOVED,
                    f"{source_base}.years",
                    f"education[{len(result)}].endDate",
                )
            self._record_text(
                edu.institution,
                ContentFate.MOVED,
                f"{source_base}.institution",
                f"education[{len(result)}].institution",
            )
            self._record_text(
                edu.degree,
                ContentFate.MOVED,
                f"{source_base}.degree",
                f"education[{len(result)}].degree",
            )
            result.append(
                Education(
                    institution=edu.institution,
                    degree=_optional_text(edu.degree),
                    endDate=end_date,
                    highlights=highlights,
                )
            )
        return result

    def projects(self, projects: Iterable[BuildProject]) -> list[Project]:
        result: list[Project] = []
        for index, project in enumerate(projects):
            source_base = f"personalProjects[{index}]"
            achievements: list[Achievement] = []
            for bullet_index, bullet in enumerate(project.description):
                if not _has_text(bullet):
                    continue
                target_path = (
                    f"projects[{len(result)}].achievements[{len(achievements)}].text"
                )
                achievements.append(Achievement(text=bullet))
                self._record_text(
                    bullet,
                    ContentFate.MOVED,
                    f"{source_base}.description[{bullet_index}]",
                    target_path,
                )
            links: list[Link] = []
            for link_type, value, label, field_name in (
                (LinkType.GITHUB, project.github, "GitHub", "github"),
                (LinkType.WEBSITE, project.website, "Website", "website"),
            ):
                link_value = _optional_text(value)
                if link_value is None:
                    continue
                target_path = f"projects[{len(result)}].links[{len(links)}].url"
                links.append(Link(type=link_type, url=link_value, label=label))
                self._record_text(
                    link_value,
                    ContentFate.MOVED,
                    f"{source_base}.{field_name}",
                    target_path,
                )
            start_date, end_date, dates_are_lossless = _parse_canonical_range(project.years)
            description = None if dates_are_lossless else _optional_text(project.years)
            if description is not None:
                self._record_text(
                    project.years,
                    ContentFate.MOVED,
                    f"{source_base}.years",
                    f"projects[{len(result)}].description",
                )
            else:
                self._record_text(
                    project.years,
                    ContentFate.MOVED,
                    f"{source_base}.years",
                    f"projects[{len(result)}].startDate",
                )
            self._record_text(
                project.name,
                ContentFate.MOVED,
                f"{source_base}.name",
                f"projects[{len(result)}].name",
            )
            self._record_text(
                project.role,
                ContentFate.MOVED,
                f"{source_base}.role",
                f"projects[{len(result)}].roles[0]",
            )
            result.append(
                Project(
                    name=project.name,
                    description=description,
                    achievements=achievements,
                    roles=[project.role] if _has_text(project.role) else [],
                    links=links,
                    startDate=start_date,
                    endDate=end_date,
                )
            )
        return result

    def add_custom_section(
        self,
        section: CustomSection,
        display_name: str,
        target: CanonicalSection,
        source_path: str,
    ) -> bool:
        if target is CanonicalSection.SKILLS and section.sectionType is SectionType.STRING_LIST:
            self.add_skill_group(
                display_name,
                section.strings or [],
                f"{source_path}.strings",
                display_name,
            )
            return True
        if target in {
            CanonicalSection.CERTIFICATIONS,
            CanonicalSection.AWARDS,
            CanonicalSection.LANGUAGES,
        }:
            return self._add_custom_named_section(section, display_name, target, source_path)
        return False

    def _add_custom_named_section(
        self,
        section: CustomSection,
        display_name: str,
        target: CanonicalSection,
        source_path: str,
    ) -> bool:
        if section.sectionType is SectionType.STRING_LIST:
            self.add_named_items(
                target=target,
                values=section.strings or [],
                source_path=f"{source_path}.strings",
                heading=display_name,
            )
            return True
        if section.sectionType is not SectionType.ITEM_LIST:
            return False
        values: list[str] = []
        for item in section.items or []:
            if _item_has_only_title(item):
                values.append(item.title)
            else:
                return False
        self.add_named_items(
            target=target,
            values=values,
            source_path=f"{source_path}.items",
            heading=display_name,
        )
        return True

    def add_skill_group(
        self,
        name: str,
        values: Iterable[str],
        source_path: str,
        heading: str | None = None,
    ) -> None:
        for index, value in enumerate(values):
            source = f"{source_path}[{index}]"
            if _is_heading_artifact(value, heading or name):
                self._record_text(value, ContentFate.DROPPED_AS_HEADING, source, None)
                continue
            if _is_parser_artifact(value):
                self._record_text(value, ContentFate.DROPPED_AS_PARSER_ARTIFACT, source, None)
                continue
            if not _has_text(value):
                continue
            # A single string may carry a delimited list of skills
            # ("Python, CI/CD, A/B testing"). Split into discrete skills so the
            # canonical keyword surface matches the scored keyword surface, while
            # preserving slash-bearing skills ("CI/CD") intact (RIT-T-0162 B2).
            for skill in _split_skill_line(value):
                key = _claim_key(skill)
                existing = self._skill_sources.get(key)
                if existing is not None:
                    self._record_text(
                        skill,
                        ContentFate.DEDUPED,
                        source,
                        existing,
                        reason="exact duplicate skill",
                    )
                    continue
                target_path = f"skills[0].keywords[{len(self._skill_keywords)}]"
                self._skill_keywords[key] = skill
                self._skill_sources[key] = target_path
                self._record_text(skill, ContentFate.MOVED, source, target_path)

    def add_named_items(
        self,
        *,
        target: CanonicalSection,
        values: Iterable[str],
        source_path: str,
        heading: str | None = None,
    ) -> None:
        for index, value in enumerate(values):
            source = f"{source_path}[{index}]"
            if heading is not None and _is_heading_artifact(value, heading):
                self._record_text(value, ContentFate.DROPPED_AS_HEADING, source, None)
                continue
            if _is_parser_artifact(value):
                self._record_text(
                    value,
                    ContentFate.DROPPED_AS_PARSER_ARTIFACT,
                    source,
                    None,
                )
                continue
            if not _has_text(value):
                continue
            if target is CanonicalSection.CERTIFICATIONS:
                self._add_certification(value, source)
            elif target is CanonicalSection.AWARDS:
                self._add_award(value, source)
            elif target is CanonicalSection.LANGUAGES:
                self._add_language(value, source)

    def _add_certification(self, value: str, source_path: str) -> None:
        key = _claim_key(value)
        existing = self._certification_keys.get(key)
        if existing is not None:
            self._record_text(
                value,
                ContentFate.DEDUPED,
                source_path,
                existing,
                reason="exact duplicate certification",
            )
            return
        target_path = f"certifications[{len(self.certifications)}].name"
        self.certifications.append(Certification(name=value))
        self._certification_keys[key] = target_path
        self._record_text(value, ContentFate.MOVED, source_path, target_path)

    def _add_award(self, value: str, source_path: str) -> None:
        key = _claim_key(value)
        existing = self._award_keys.get(key)
        if existing is not None:
            self._record_text(
                value,
                ContentFate.DEDUPED,
                source_path,
                existing,
                reason="exact duplicate award",
            )
            return
        target_path = f"awards[{len(self.awards)}].name"
        self.awards.append(Award(name=value))
        self._award_keys[key] = target_path
        self._record_text(value, ContentFate.MOVED, source_path, target_path)

    def _add_language(self, value: str, source_path: str) -> None:
        key = _claim_key(value)
        existing = self._language_keys.get(key)
        if existing is not None:
            self._record_text(
                value,
                ContentFate.DEDUPED,
                source_path,
                existing,
                reason="exact duplicate language",
            )
            return
        target_path = f"languages[{len(self.languages)}].name"
        self.languages.append(Language(name=value))
        self._language_keys[key] = target_path
        self._record_text(value, ContentFate.MOVED, source_path, target_path)

    def preserve_custom_section(
        self,
        section: CustomSection,
        display_name: str,
        source_path: str,
    ) -> None:
        """Preserve an untargeted custom section in the canonical ``custom`` slot.

        Content that has no first-class canonical home is kept verbatim so the
        ledger can account for it (fate ``PRESERVED_AS_OTHER``) instead of
        reporting it as dropped/unresolved (RIT-T-0161).
        """
        custom_index = len(self.custom_sections)
        lines: list[str] = []
        for path, text in _custom_texts(section, source_path):
            if _is_heading_artifact(text, display_name):
                self._record_text(text, ContentFate.DROPPED_AS_HEADING, path, None)
                continue
            if _is_parser_artifact(text):
                self._record_text(text, ContentFate.DROPPED_AS_PARSER_ARTIFACT, path, None)
                continue
            if not _has_text(text):
                continue
            target_path = f"custom[{custom_index}].lines[{len(lines)}]"
            lines.append(text)
            self._record_text(text, ContentFate.PRESERVED_AS_OTHER, path, target_path)
        if lines:
            self.custom_sections.append(
                CustomContentSection(heading=display_name, lines=lines)
            )

    def unresolved_custom_section(
        self,
        section: CustomSection,
        display_name: str,
        source_path: str,
    ) -> None:
        for path, text in _custom_texts(section, source_path):
            if _is_heading_artifact(text, display_name):
                self._record_text(text, ContentFate.DROPPED_AS_HEADING, path, None)
            elif _is_parser_artifact(text):
                self._record_text(text, ContentFate.DROPPED_AS_PARSER_ARTIFACT, path, None)
            else:
                self._record_text(
                    text,
                    ContentFate.UNRESOLVED,
                    path,
                    None,
                    reason=f"custom section '{display_name}' needs a mapping decision",
                )

    def handoff_custom_section_to_evidence(
        self,
        section: CustomSection,
        display_name: str,
        source_path: str,
    ) -> None:
        """Account for custom source content intentionally retained in evidence.

        Flow 1 prepared resumes do not keep a canonical ``custom`` holding
        section. The source text is still extracted into ``CandidateEvidence``
        by the full-resume evidence builder; these ledger rows make that
        movement explicit so the shape pass never silently drops content.
        """
        for path, text in _custom_texts(section, source_path):
            if _is_heading_artifact(text, display_name):
                self._record_text(text, ContentFate.DROPPED_AS_HEADING, path, None)
            elif _is_parser_artifact(text):
                self._record_text(text, ContentFate.DROPPED_AS_PARSER_ARTIFACT, path, None)
            elif _has_text(text):
                self._record_text(
                    text,
                    ContentFate.PRESERVED_IN_EVIDENCE,
                    path,
                    None,
                    reason=f"custom section '{display_name}' preserved in evidence",
                )

    def skill_groups(self) -> list[SkillGroup]:
        keywords = list(self._skill_keywords.values())
        if not keywords:
            return []
        return [SkillGroup(name="Technical Skills", keywords=keywords)]

    def _record_text(
        self,
        text: str | None,
        fate: ContentFate,
        source_path: str,
        target_path: str | None,
        reason: str | None = None,
    ) -> None:
        if text is None:
            return
        for token in _tokens(text):
            self.ledger_entries.append(
                ContentLedgerEntry(
                    token=token,
                    fate=fate,
                    source_path=source_path,
                    target_path=target_path,
                    reason=reason,
                )
            )


def _report_targets(report: ShapeReport) -> dict[str, CanonicalSection]:
    targets: dict[str, CanonicalSection] = {}
    for finding in report.findings:
        if finding.family is not ShapeFindingFamily.CUSTOM_SECTION_MAPPED:
            continue
        if finding.proposed_target is None:
            continue
        targets[finding.section] = finding.proposed_target
    return targets


def _decision_targets(decisions: Mapping[str, ShapeDecision]) -> dict[str, CanonicalSection]:
    targets: dict[str, CanonicalSection] = {}
    for section, decision in decisions.items():
        if isinstance(decision, SectionMapping):
            targets[section] = decision.target
        else:
            targets[section] = _coerce_section(decision)
    return targets


def _coerce_section(value: CanonicalSection | str) -> CanonicalSection:
    if isinstance(value, CanonicalSection):
        return value
    return CanonicalSection(value)


def _finding_was_applied(finding: ShapeFinding, applied_sections: set[str]) -> bool:
    if finding.family in {
        ShapeFindingFamily.SECTION_ORDER_VIOLATION,
        ShapeFindingFamily.CANONICAL_FIELD_DUPLICATE,
        ShapeFindingFamily.DUPLICATE_SECTION_CONTENT,
        ShapeFindingFamily.REDUNDANT_SECTION,
        ShapeFindingFamily.EMBEDDED_HEADING_LINE,
    }:
        return True
    return finding.section in applied_sections


def _finding_was_deferred(finding: ShapeFinding, deferred_sections: set[str]) -> bool:
    if finding.family is ShapeFindingFamily.BUDGET_INFO:
        return True
    return finding.section in deferred_sections


def _parse_canonical_range(years: str) -> tuple[str | None, str | None, bool]:
    raw = years.strip()
    if not raw:
        return None, None, True
    parts = _RANGE_SPLIT_RE.split(raw, maxsplit=1)
    start_raw = parts[0].strip()
    end_raw = parts[1].strip() if len(parts) > 1 else ""
    start = start_raw if _YEAR_RE.fullmatch(start_raw) else None
    if end_raw == "":
        end = None
    elif _YEAR_RE.fullmatch(end_raw):
        end = end_raw
    elif _OPEN_END_RE.fullmatch(end_raw):
        end = "present"
    else:
        end = None
    return start, end, start is not None and (end_raw == "" or end is not None)


def _custom_texts(section: CustomSection, source_path: str) -> list[tuple[str, str]]:
    if section.sectionType is SectionType.TEXT:
        return [(f"{source_path}.text", section.text or "")]
    if section.sectionType is SectionType.STRING_LIST:
        return [
            (f"{source_path}.strings[{index}]", value)
            for index, value in enumerate(section.strings or [])
        ]
    texts: list[tuple[str, str]] = []
    for index, item in enumerate(section.items or []):
        base = f"{source_path}.items[{index}]"
        texts.extend(
            [
                (f"{base}.title", item.title),
                (f"{base}.subtitle", item.subtitle or ""),
                (f"{base}.location", item.location or ""),
                (f"{base}.years", item.years),
            ]
        )
        texts.extend(
            (f"{base}.description[{bullet_index}]", bullet)
            for bullet_index, bullet in enumerate(item.description)
        )
    return texts


def _item_has_only_title(item: CustomSectionItem) -> bool:
    return (
        _has_text(item.title)
        and not _has_text(item.subtitle)
        and not _has_text(item.location)
        and not _has_text(item.years)
        and not any(_has_text(bullet) for bullet in item.description)
    )


def _custom_display_names(section_meta: Iterable[SectionMeta]) -> dict[str, str]:
    names: dict[str, str] = {}
    for meta in section_meta:
        if not meta.isDefault:
            names[meta.key] = meta.displayName or meta.key
    return names


def _without_evidence_preserved_claims(
    resume: ResumeDocument | Resume,
    claims: dict[str, frozenset[str]],
    ledger: ContentLedger,
) -> dict[str, frozenset[str]]:
    if not isinstance(resume, ResumeDocument):
        return claims
    source_paths = {
        entry.source_path
        for entry in ledger.entries
        if entry.fate is ContentFate.PRESERVED_IN_EVIDENCE
    }
    if not source_paths:
        return claims

    remaining_skills: set[str] = set()
    for value in resume.additional.technicalSkills:
        remaining_skills.update(_skill_claims_from_value(value))
    display_names = _custom_display_names(resume.sectionMeta)
    for key, section in resume.customSections.items():
        if section.sectionType is not SectionType.STRING_LIST:
            continue
        display_name = display_names.get(key, key)
        for path, text in _custom_texts(section, f"customSections.{key}"):
            if path in source_paths:
                continue
            if _is_heading_artifact(text, display_name) or _is_parser_artifact(text):
                continue
            remaining_skills.update(_skill_claims_from_value(text))

    updated = dict(claims)
    updated["skills_and_custom"] = frozenset(remaining_skills)
    return updated


def _global_claim_set(resume: ResumeDocument | Resume) -> dict[str, frozenset[str]]:
    if isinstance(resume, ResumeDocument):
        return _builddoc_claim_set(resume)
    return _canonical_claim_set(resume)


def _builddoc_claim_set(resume: ResumeDocument) -> dict[str, frozenset[str]]:
    # "skills_and_custom" is ONE combined claim universe covering both the skills
    # surface and any custom-section string content. Folding them together keeps
    # the gate symmetric across an explicit custom->skills remapping: content that
    # moves from a custom section into skills stays in the same universe rather
    # than appearing lost on one side and added on the other (RIT-T-0162 B1). Both
    # sides derive tokens through the identical ``_split_skill_line`` tokenization.
    skills: set[str] = set()
    for value in resume.additional.technicalSkills:
        skills.update(_skill_claims_from_value(value))
    display_names = _custom_display_names(resume.sectionMeta)
    for key, section in resume.customSections.items():
        display_name = display_names.get(key, key)
        skills.update(_custom_skill_claims(section, display_name))
    return {
        "employers": frozenset(_clean_claims(exp.company for exp in resume.workExperience)),
        "titles": frozenset(_clean_claims(exp.title for exp in resume.workExperience)),
        "degrees": frozenset(_clean_claims(edu.degree for edu in resume.education)),
        "skills_and_custom": frozenset(skills),
    }


def _canonical_claim_set(resume: Resume) -> dict[str, frozenset[str]]:
    skills: set[str] = set()
    for group in resume.skills:
        for keyword in group.keywords:
            skills.update(_skill_claims_from_value(keyword))
    for exp in resume.work:
        skills.update(_clean_claims(exp.skills))
        skills.update(_clean_claims(exp.technologies))
    for project in resume.projects:
        skills.update(_clean_claims(project.skills))
        skills.update(_clean_claims(project.technologies))
    for custom in resume.custom:
        for line in custom.lines:
            skills.update(_skill_claims_from_value(line))
    return {
        "employers": frozenset(_clean_claims(exp.organization for exp in resume.work)),
        "titles": frozenset(_clean_claims(exp.title for exp in resume.work)),
        "degrees": frozenset(_clean_claims(edu.degree for edu in resume.education)),
        "skills_and_custom": frozenset(skills),
    }


def _skill_claims_from_value(value: str | None) -> set[str]:
    if not _has_text(value):
        return set()
    assert value is not None
    return {_normalize_claim(skill) for skill in _split_skill_line(value)}


def _custom_skill_claims(section: CustomSection, display_name: str) -> set[str]:
    # Include every custom string-list section's content in the combined
    # skills+custom universe, tokenized through the shared splitter, so both the
    # skills-mapped and preserved-as-other outcomes stay symmetric (RIT-T-0162 B1).
    if section.sectionType is not SectionType.STRING_LIST:
        return set()
    claims: set[str] = set()
    for value in section.strings or []:
        if not _has_text(value) or _is_heading_artifact(value, display_name):
            continue
        if _is_parser_artifact(value):
            continue
        claims.update(_skill_claims_from_value(value))
    return claims


def _clean_claims(values: Iterable[str | None]) -> list[str]:
    return [_normalize_claim(value) for value in values if _has_text(value)]


def _normalize_claim(value: str | None) -> str:
    return re.sub(r"\s+", " ", value.strip()) if value is not None else ""


def _claim_key(value: str) -> str:
    return _normalize_claim(value).casefold()


def _optional_text(value: str | None) -> str | None:
    if not _has_text(value):
        return None
    return value


def _has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _tokens(text: str) -> list[str]:
    return [token.casefold() for token in _TOKEN_RE.findall(text)]


# Skill-list delimiters: commas, semicolons, pipes, bullets, and newlines split
# a line into discrete skills. Slashes are deliberately NOT delimiters so that
# established skills ("CI/CD", "A/B testing") survive intact (RIT-T-0162 B2).
_SKILL_SPLIT_RE = re.compile(r"[,;|•·\n]+")


def _split_skill_line(value: str) -> list[str]:
    """Split one skills entry into discrete, trimmed skill tokens.

    Delimiter/list-aware and slash-preserving. Never invents content: it only
    splits what is genuinely present and drops empty fragments.
    """
    return [part.strip() for part in _SKILL_SPLIT_RE.split(value) if part.strip()]


def _is_heading_artifact(value: str, heading: str) -> bool:
    return normalize_section_heading(value) == normalize_section_heading(heading)


def _is_parser_artifact(value: str) -> bool:
    normalized = normalize_section_heading(value).replace(" ", "_")
    return normalized in _PARSER_ARTIFACTS


__all__ = [
    "CustomHandoffPolicy",
    "apply_shape_transforms",
    "claims_preserved_across_sections",
    "content_ledger_ok",
]
