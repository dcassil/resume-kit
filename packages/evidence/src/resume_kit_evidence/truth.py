"""Deterministic resume truth-validation and provenance classification.

New resume-kit subsystem (no upstream port). ``validate_resume_truth`` classifies
every material claim in a resume against a set of
:class:`~resume_kit_schemas.evidence.CandidateEvidence` records into one of the
seven :class:`~resume_kit_schemas.provenance.ProvenanceStatus` values, and rolls
the per-claim results up into a :class:`~resume_kit_schemas.results.TruthReport`.

Classification is deterministic and conservative:

* **VERIFIED** — the claim text matches (casefold, whitespace-normalized) an
  evidence record that the candidate has explicitly confirmed.
* **SUPPORTED** — the claim text matches an evidence record that is not
  user-confirmed.
* **USER_CONFIRMED** — no exact match, but a user-confirmed evidence record has
  strong (but not identical) token overlap with the claim.
* **PARTIALLY_SUPPORTED** — substantial token overlap with some evidence record.
* **AMBIGUOUS** — weak, non-zero token overlap; support is uncertain.
* **UNSUPPORTED** — no evidence record shares any content tokens with the claim.
* **CONTRADICTED** — the claim is structurally impossible or fabricated: a
  fabricated skill/certification/company (via the fabrication checks) or a
  dropped/altered structural invariant (via the structural predicates).

Composes ``predicates`` (structural invariants) and ``fabrication`` (fabricated
content detection) from this package rather than reimplementing them.
"""

from __future__ import annotations

import re

from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.provenance import ClaimProvenance, ProvenanceStatus
from resume_kit_schemas.results import TruthReport

from .builder import normalize_text
from .fabrication import validate_master_alignment
from .predicates import (
    no_fabricated_employers,
    personal_info_unchanged,
    sections_preserved,
)

__all__ = ["validate_resume_truth"]

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Fraction of a claim's tokens that must appear in an evidence record's tokens.
_PARTIAL_THRESHOLD = 0.6
_USER_CONFIRMED_THRESHOLD = 0.8


def _tokens(text: str) -> frozenset[str]:
    return frozenset(_TOKEN_RE.findall(normalize_text(text)))


class _Claim:
    __slots__ = ("text", "field_path")

    def __init__(self, text: str, field_path: str) -> None:
        self.text = text
        self.field_path = field_path


def _collect_claims(resume: ResumeDocument) -> list[_Claim]:
    """Collect material, human-authored claims with their field paths."""

    claims: list[_Claim] = []

    summary = resume.summary.strip()
    if summary:
        claims.append(_Claim(summary, "summary"))

    for i, exp in enumerate(resume.workExperience):
        for j, bullet in enumerate(exp.description):
            text = bullet.strip()
            if text:
                claims.append(_Claim(text, f"workExperience[{i}].description[{j}]"))

    for i, proj in enumerate(resume.personalProjects):
        for j, bullet in enumerate(proj.description):
            text = bullet.strip()
            if text:
                claims.append(_Claim(text, f"personalProjects[{i}].description[{j}]"))

    for i, skill in enumerate(resume.additional.technicalSkills):
        text = skill.strip()
        if text:
            claims.append(_Claim(text, f"additional.technicalSkills[{i}]"))

    for i, cert in enumerate(resume.additional.certificationsTraining):
        text = cert.strip()
        if text:
            claims.append(_Claim(text, f"additional.certificationsTraining[{i}]"))

    return claims


def _fabricated_values(resume: ResumeDocument, evidence: list[CandidateEvidence]) -> set[str]:
    """Normalized claim texts that the fabrication checks flag as invented.

    Reconstructs a "master" resume from the evidence set (the ground truth the
    candidate can attest to) and compares the resume against it. Fabricated skills,
    certifications and companies come back as ``critical`` alignment violations;
    fabricated employers also surface via the structural employer check.
    """

    master = _evidence_to_master(evidence)
    tailored = resume.model_dump(by_alias=True)

    fabricated: set[str] = set()

    report = validate_master_alignment(tailored, master)
    for violation in report.violations:
        if violation.severity == "critical":
            fabricated.add(normalize_text(violation.value))

    for company in no_fabricated_employers(master, tailored):
        fabricated.add(normalize_text(company))

    return fabricated


def _evidence_to_master(evidence: list[CandidateEvidence]) -> dict[str, object]:
    """Project evidence content back into a resume-shaped dict of ground truth."""

    skills: list[str] = []
    certs: list[str] = []
    companies: list[str] = []
    summary_parts: list[str] = []
    for ev in evidence:
        content = ev.content.strip()
        if not content:
            continue
        if ev.kind is EvidenceKind.SKILL:
            skills.append(content)
        elif ev.kind is EvidenceKind.CERTIFICATION:
            certs.append(content)
        elif ev.kind is EvidenceKind.WORK_HISTORY:
            for tag in ev.tags:
                companies.append(tag)
        elif ev.kind is EvidenceKind.MASTER_RESUME:
            summary_parts.append(content)

    work = [{"company": c, "title": "", "description": []} for c in dict.fromkeys(companies)]
    return {
        "summary": " ".join(summary_parts),
        "workExperience": work,
        "education": [],
        "personalProjects": [],
        "additional": {
            "technicalSkills": skills,
            "certificationsTraining": certs,
            "languages": [],
            "awards": [],
        },
    }


def _classify(
    claim: _Claim,
    evidence: list[CandidateEvidence],
    fabricated: set[str],
) -> ClaimProvenance:
    normalized = normalize_text(claim.text)

    if normalized in fabricated:
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.CONTRADICTED,
            field_path=claim.field_path,
            evidence_ids=[],
            rationale="Claim is fabricated or contradicts the candidate's evidence.",
            confidence=1.0,
        )

    claim_tokens = _tokens(claim.text)

    exact_ids: list[str] = []
    exact_confirmed = False
    best_overlap = 0.0
    best_confirmed_overlap = 0.0
    overlap_ids: list[str] = []

    for ev in evidence:
        ev_norm = normalize_text(ev.content)
        if ev_norm == normalized:
            exact_ids.append(ev.id)
            exact_confirmed = exact_confirmed or ev.user_confirmed
            continue
        ev_tokens = _tokens(ev.content)
        if not claim_tokens or not ev_tokens:
            continue
        overlap = len(claim_tokens & ev_tokens) / len(claim_tokens)
        if overlap > 0:
            overlap_ids.append(ev.id)
        if overlap > best_overlap:
            best_overlap = overlap
        if ev.user_confirmed and overlap > best_confirmed_overlap:
            best_confirmed_overlap = overlap

    if exact_ids:
        if exact_confirmed:
            return ClaimProvenance(
                claim=claim.text,
                status=ProvenanceStatus.VERIFIED,
                field_path=claim.field_path,
                evidence_ids=exact_ids,
                rationale="Exact match to user-confirmed evidence.",
                confidence=1.0,
            )
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.SUPPORTED,
            field_path=claim.field_path,
            evidence_ids=exact_ids,
            rationale="Exact match to candidate evidence.",
            confidence=0.95,
        )

    if best_confirmed_overlap >= _USER_CONFIRMED_THRESHOLD:
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.USER_CONFIRMED,
            field_path=claim.field_path,
            evidence_ids=overlap_ids,
            rationale="Strong overlap with user-confirmed evidence.",
            confidence=best_confirmed_overlap,
        )

    if best_overlap >= _PARTIAL_THRESHOLD:
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.PARTIALLY_SUPPORTED,
            field_path=claim.field_path,
            evidence_ids=overlap_ids,
            rationale="Substantial token overlap with candidate evidence.",
            confidence=best_overlap,
        )

    if best_overlap > 0:
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.AMBIGUOUS,
            field_path=claim.field_path,
            evidence_ids=overlap_ids,
            rationale="Weak, uncertain overlap with candidate evidence.",
            confidence=best_overlap,
        )

    return ClaimProvenance(
        claim=claim.text,
        status=ProvenanceStatus.UNSUPPORTED,
        field_path=claim.field_path,
        evidence_ids=[],
        rationale="No candidate evidence supports this claim.",
        confidence=1.0,
    )


def validate_resume_truth(
    resume: ResumeDocument,
    evidence: list[CandidateEvidence],
) -> TruthReport:
    """Classify each material claim in ``resume`` against ``evidence``.

    Args:
        resume: The resume whose claims are being validated.
        evidence: Ground-truth candidate-evidence records (e.g. from
            :func:`~resume_kit_evidence.builder.build_candidate_evidence`).

    Returns:
        A :class:`TruthReport` with one :class:`ClaimProvenance` per material
        claim across all seven provenance statuses. Its summary
        (``has_unsupported_or_contradicted`` / ``passed`` / ``status_counts``) is
        computed by the schema and indicates whether any unsupported or
        contradicted claim exists.
    """

    fabricated = _fabricated_values(resume, evidence)

    # A dropped structural section makes the whole resume structurally suspect:
    # treat all its claims as contradicted so the report cannot silently pass.
    master = _evidence_to_master(evidence)
    tailored = resume.model_dump(by_alias=True)
    structural_failure = not sections_preserved(master, tailored) or not (
        personal_info_unchanged(master, tailored)
        if master.get("personalInfo")
        else True
    )

    claims = _collect_claims(resume)
    provenances: list[ClaimProvenance] = []
    for claim in claims:
        provenance = _classify(claim, evidence, fabricated)
        if structural_failure and provenance.status not in (
            ProvenanceStatus.CONTRADICTED,
            ProvenanceStatus.UNSUPPORTED,
        ):
            provenance = ClaimProvenance(
                claim=provenance.claim,
                status=ProvenanceStatus.CONTRADICTED,
                field_path=provenance.field_path,
                evidence_ids=provenance.evidence_ids,
                rationale="Structural invariant violated (section dropped or identity changed).",
                confidence=1.0,
            )
        provenances.append(provenance)

    return TruthReport(claims=provenances)
