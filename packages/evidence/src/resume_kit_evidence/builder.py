"""Deterministic candidate-evidence extraction.

New resume-kit subsystem (no upstream port). ``build_candidate_evidence`` walks a
:class:`~resume_kit_schemas.ResumeDocument` and emits one
:class:`~resume_kit_schemas.evidence.CandidateEvidence` record per material fact
the candidate can attest to — summary, work history, projects, education, skills
and certifications — plus any explicitly approved-claim inputs.

The extractor never invents content: every evidence record's ``content`` is copied
verbatim from a resume field or an approved-claim input. Evidence identifiers are
content-addressed (a hash of ``kind`` + normalized text), so identical inputs yield
identical ids regardless of call order, letting provenance records reference them
stably.
"""

from __future__ import annotations

import hashlib
import re

from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind

__all__ = [
    "build_candidate_evidence",
    "make_evidence_id",
    "normalize_text",
]

_WS_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    """Collapse whitespace and casefold ``text`` for stable matching/hashing."""

    return _WS_RE.sub(" ", text.strip()).casefold()


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

    summary = resume.summary.strip()
    if summary:
        records.append(
            _make(
                EvidenceKind.MASTER_RESUME,
                summary,
                source="summary",
                tags=["summary"],
            )
        )

    for exp in resume.workExperience:
        employer = exp.company.strip()
        role = exp.title.strip()
        header = " — ".join(part for part in (role, employer) if part)
        if header:
            records.append(
                _make(
                    EvidenceKind.WORK_HISTORY,
                    header,
                    source="workExperience",
                    tags=[t for t in (employer, role) if t],
                )
            )
        for bullet in exp.description:
            text = bullet.strip()
            if text:
                records.append(
                    _make(
                        EvidenceKind.WORK_HISTORY,
                        text,
                        source="workExperience",
                        tags=[t for t in (employer,) if t],
                    )
                )

    for proj in resume.personalProjects:
        name = proj.name.strip()
        if name:
            records.append(
                _make(
                    EvidenceKind.PROJECT,
                    name,
                    source="personalProjects",
                    tags=[name],
                )
            )
        for bullet in proj.description:
            text = bullet.strip()
            if text:
                records.append(
                    _make(
                        EvidenceKind.PROJECT,
                        text,
                        source="personalProjects",
                        tags=[t for t in (name,) if t],
                    )
                )

    for edu in resume.education:
        parts = [p for p in (edu.degree.strip(), edu.institution.strip()) if p]
        if parts:
            records.append(
                _make(
                    EvidenceKind.EDUCATION,
                    " — ".join(parts),
                    source="education",
                    tags=parts,
                )
            )

    for skill in resume.additional.technicalSkills:
        text = skill.strip()
        if text:
            records.append(
                _make(
                    EvidenceKind.SKILL,
                    text,
                    source="additional.technicalSkills",
                    tags=[text],
                )
            )

    for cert in resume.additional.certificationsTraining:
        text = cert.strip()
        if text:
            records.append(
                _make(
                    EvidenceKind.CERTIFICATION,
                    text,
                    source="additional.certificationsTraining",
                    tags=[text],
                )
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
