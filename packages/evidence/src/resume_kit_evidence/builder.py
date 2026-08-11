"""Deterministic candidate-evidence extraction.

New resume-kit subsystem (no upstream port). ``build_candidate_evidence`` walks a
:class:`~resume_kit_schemas.ResumeDocument` and emits one
:class:`~resume_kit_schemas.evidence.CandidateEvidence` record per material fact
the candidate can attest to — summary, work history, projects, education, skills,
certifications, languages, awards, and custom/unmapped source sections — plus
any explicitly approved-claim inputs.

The extractor never invents content: every evidence record's ``content`` is copied
verbatim from a resume field or an approved-claim input. Evidence identifiers are
content-addressed (a hash of ``kind`` + normalized text), so identical inputs yield
identical ids regardless of call order, letting provenance records reference them
stably.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from resume_kit_schemas import CustomSection, ResumeDocument, SectionMeta, SectionType
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind, normalize_text

__all__ = [
    "build_candidate_evidence",
    "make_evidence_id",
    "normalize_text",
]

def make_evidence_id(kind: EvidenceKind, content: str) -> str:
    """Return a stable, content-addressed evidence id.

    The id depends only on ``kind`` and the normalized ``content`` — never on call
    order — so re-running the extractor over identical inputs reproduces the same
    ids, and provenance records can safely cross-reference them.
    """

    digest = hashlib.sha256(
        f"{kind.value}\x1f{normalize_text(content)}".encode()
    ).hexdigest()
    return f"ev-{digest[:16]}"


def _make(
    kind: EvidenceKind,
    content: str,
    *,
    source: str | None,
    tags: list[str],
    user_confirmed: bool = False,
) -> CandidateEvidence:
    return CandidateEvidence(
        id=make_evidence_id(kind, content),
        kind=kind,
        content=content,
        source=source,
        tags=tags,
        user_confirmed=user_confirmed,
    )


def _record(
    records: list[CandidateEvidence],
    kind: EvidenceKind,
    content: str | None,
    *,
    source: str,
    tags: Iterable[str] = (),
    user_confirmed: bool = False,
) -> None:
    if content is None:
        return
    text = content.strip()
    if not text:
        return
    records.append(
        _make(
            kind,
            text,
            source=source,
            tags=[tag for tag in tags if tag],
            user_confirmed=user_confirmed,
        )
    )


def build_candidate_evidence(
    resume: ResumeDocument,
    *,
    approved_claims: list[CandidateEvidence] | list[str] | None = None,
) -> list[CandidateEvidence]:
    """Extract candidate-evidence records from a resume and approved claims.

    Args:
        resume: The structured resume to mine for ground-truth facts.
        approved_claims: Optional user-attested claims. Either raw strings (each
            becomes a ``user_confirmed`` ``USER_STATEMENT`` record) or ready-made
            :class:`CandidateEvidence` records (re-id'd for stability and forced to
            ``user_confirmed``).

    Returns:
        A deterministically ordered, de-duplicated list of evidence records. No
        content is invented — every record's text comes from ``resume`` or
        ``approved_claims``.
    """

    records: list[CandidateEvidence] = []

    _record(
        records,
        EvidenceKind.MASTER_RESUME,
        resume.summary,
        source="summary",
        tags=["summary"],
    )

    for exp_index, exp in enumerate(resume.workExperience):
        employer = exp.company.strip()
        role = exp.title.strip()
        header = " — ".join(part for part in (role, employer) if part)
        _record(
            records,
            EvidenceKind.WORK_HISTORY,
            header,
            source=f"workExperience[{exp_index}]",
            tags=[employer, role],
        )
        for bullet_index, bullet in enumerate(exp.description):
            _record(
                records,
                EvidenceKind.WORK_HISTORY,
                bullet,
                source=f"workExperience[{exp_index}].description[{bullet_index}]",
                tags=[employer],
            )

    for proj_index, proj in enumerate(resume.personalProjects):
        name = proj.name.strip()
        _record(
            records,
            EvidenceKind.PROJECT,
            name,
            source=f"personalProjects[{proj_index}].name",
            tags=[name],
        )
        for bullet_index, bullet in enumerate(proj.description):
            _record(
                records,
                EvidenceKind.PROJECT,
                bullet,
                source=f"personalProjects[{proj_index}].description[{bullet_index}]",
                tags=[name],
            )

    for edu_index, edu in enumerate(resume.education):
        parts = [p for p in (edu.degree.strip(), edu.institution.strip()) if p]
        _record(
            records,
            EvidenceKind.EDUCATION,
            " — ".join(parts),
            source=f"education[{edu_index}]",
            tags=parts,
        )

    for skill_index, skill in enumerate(resume.additional.technicalSkills):
        _record(
            records,
            EvidenceKind.SKILL,
            skill,
            source=f"additional.technicalSkills[{skill_index}]",
            tags=[skill.strip()],
        )

    for cert_index, cert in enumerate(resume.additional.certificationsTraining):
        _record(
            records,
            EvidenceKind.CERTIFICATION,
            cert,
            source=f"additional.certificationsTraining[{cert_index}]",
            tags=[cert.strip()],
        )

    for language_index, language in enumerate(resume.additional.languages):
        _record(
            records,
            EvidenceKind.OTHER,
            language,
            source=f"additional.languages[{language_index}]",
            tags=["language", language.strip()],
        )

    for award_index, award in enumerate(resume.additional.awards):
        _record(
            records,
            EvidenceKind.OTHER,
            award,
            source=f"additional.awards[{award_index}]",
            tags=["award", award.strip()],
        )

    display_names = _custom_display_names(resume.sectionMeta)
    for key in sorted(resume.customSections):
        section = resume.customSections[key]
        display_name = display_names.get(key, key)
        source_base = f"customSections.{key}"
        for source, text in _custom_evidence_texts(section, source_base):
            _record(
                records,
                EvidenceKind.SOURCE_CUSTOM,
                text,
                source=source,
                tags=[f"custom:{display_name}", display_name],
            )

    for claim in approved_claims or []:
        if isinstance(claim, CandidateEvidence):
            text = claim.content.strip()
            if not text:
                continue
            records.append(
                CandidateEvidence(
                    id=make_evidence_id(claim.kind, text),
                    kind=claim.kind,
                    content=text,
                    source=claim.source,
                    tags=list(claim.tags),
                    user_confirmed=True,
                    recorded_at=claim.recorded_at,
                )
            )
        else:
            text = claim.strip()
            if text:
                records.append(
                    _make(
                        EvidenceKind.USER_STATEMENT,
                        text,
                        source="approved_claims",
                        tags=[],
                        user_confirmed=True,
                    )
                )

    # De-duplicate by id while preserving first-seen deterministic order.
    seen: set[str] = set()
    unique: list[CandidateEvidence] = []
    for record in records:
        if record.id in seen:
            continue
        seen.add(record.id)
        unique.append(record)
    return unique


def _custom_display_names(section_meta: Iterable[SectionMeta]) -> dict[str, str]:
    names: dict[str, str] = {}
    for meta in section_meta:
        if not meta.isDefault:
            names[meta.key] = meta.displayName or meta.key
    return names


def _custom_evidence_texts(
    section: CustomSection,
    source_path: str,
) -> list[tuple[str, str]]:
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
