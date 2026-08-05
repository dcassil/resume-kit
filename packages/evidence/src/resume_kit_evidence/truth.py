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
* **UNSUPPORTED** — no evidence record supports the claim.
* **CONTRADICTED** — the claim is structurally impossible or actively refuted
  by an evidence record.

Composes ``predicates`` (structural invariants) from this package rather than
reimplementing them.
"""

from __future__ import annotations

import re
from pathlib import Path

from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.provenance import (
    ClaimProvenance,
    ProvenanceReasonCode,
    ProvenanceStatus,
)
from resume_kit_schemas.results import TruthReport
from resume_kit_terms import AliasIndex, load_effective_alias_index, match

from .builder import normalize_text
from .predicates import personal_info_unchanged, sections_preserved

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
        company = exp.company.strip()
        if company:
            claims.append(_Claim(company, f"workExperience[{i}].company"))
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


def _term_match(a: str, b: str, alias_index: AliasIndex) -> bool:
    # allow_stem=True folds inflectional variants such as singular/plural and
    # tense ("code review" / "code reviews") through resume-kit-terms; semantic
    # equivalence still requires the curated alias index passed to match().
    return match(a, b, alias_index=alias_index, allow_stem=True).matched


def _evidence_terms(ev: CandidateEvidence) -> list[str]:
    return [term for term in (ev.content, *ev.tags) if term.strip()]


def _is_refutation_tag(tag: str) -> bool:
    return normalize_text(tag) in {"refuted", "refutes", "contradicted", "contradicts"}


def _refuted_by_evidence(
    claim_text: str,
    evidence: list[CandidateEvidence],
    alias_index: AliasIndex,
) -> list[str]:
    refuting_ids: list[str] = []
    for ev in evidence:
        for tag in ev.tags:
            if _is_refutation_tag(tag) and any(
                _term_match(claim_text, term, alias_index) for term in _evidence_terms(ev)
            ):
                refuting_ids.append(ev.id)
                break
            marker, _sep, refuted_value = tag.partition(":")
            if (
                _is_refutation_tag(marker)
                and refuted_value.strip()
                and _term_match(claim_text, refuted_value, alias_index)
            ):
                refuting_ids.append(ev.id)
                break
    return refuting_ids


def _classify(
    claim: _Claim,
    evidence: list[CandidateEvidence],
    alias_index: AliasIndex,
) -> ClaimProvenance:
    normalized = normalize_text(claim.text)

    refuting_ids = _refuted_by_evidence(claim.text, evidence, alias_index)
    if refuting_ids:
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.CONTRADICTED,
            field_path=claim.field_path,
            evidence_ids=refuting_ids,
            rationale="Claim is actively refuted by candidate evidence.",
            reason_code=ProvenanceReasonCode.REFUTED_BY_EVIDENCE,
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
        if ev_norm == normalized or any(
            _term_match(claim.text, term, alias_index) for term in _evidence_terms(ev)
        ):
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
                reason_code=ProvenanceReasonCode.EXACT_EVIDENCE,
                confidence=1.0,
            )
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.SUPPORTED,
            field_path=claim.field_path,
            evidence_ids=exact_ids,
            rationale="Exact match to candidate evidence.",
            reason_code=ProvenanceReasonCode.EXACT_EVIDENCE,
            confidence=0.95,
        )

    if best_confirmed_overlap >= _USER_CONFIRMED_THRESHOLD:
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.USER_CONFIRMED,
            field_path=claim.field_path,
            evidence_ids=overlap_ids,
            rationale="Strong overlap with user-confirmed evidence.",
            reason_code=ProvenanceReasonCode.STRONG_EVIDENCE_OVERLAP,
            confidence=best_confirmed_overlap,
        )

    if best_overlap >= _PARTIAL_THRESHOLD:
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.PARTIALLY_SUPPORTED,
            field_path=claim.field_path,
            evidence_ids=overlap_ids,
            rationale="Substantial token overlap with candidate evidence.",
            reason_code=ProvenanceReasonCode.PARTIAL_EVIDENCE_OVERLAP,
            confidence=best_overlap,
        )

    if best_overlap > 0:
        return ClaimProvenance(
            claim=claim.text,
            status=ProvenanceStatus.AMBIGUOUS,
            field_path=claim.field_path,
            evidence_ids=overlap_ids,
            rationale="Weak, uncertain overlap with candidate evidence.",
            reason_code=ProvenanceReasonCode.AMBIGUOUS_EVIDENCE_OVERLAP,
            confidence=best_overlap,
        )

    return ClaimProvenance(
        claim=claim.text,
        status=ProvenanceStatus.UNSUPPORTED,
        field_path=claim.field_path,
        evidence_ids=[],
        rationale="No candidate evidence supports this claim.",
        reason_code=ProvenanceReasonCode.MISSING_EVIDENCE,
        confidence=1.0,
    )


def validate_resume_truth(
    resume: ResumeDocument,
    evidence: list[CandidateEvidence],
    *,
    alias_file: str | None = None,
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

    alias_index = load_effective_alias_index(None if alias_file is None else Path(alias_file))

    # A dropped structural section makes the whole resume structurally suspect:
    # treat all its claims as contradicted so the report cannot silently pass.
    master = _evidence_to_master(evidence)
    tailored = resume.model_dump(by_alias=True)
    structural_failure = not sections_preserved(master, tailored) or not (
        personal_info_unchanged(master, tailored) if master.get("personalInfo") else True
    )

    claims = _collect_claims(resume)
    provenances: list[ClaimProvenance] = []
    for claim in claims:
        provenance = _classify(claim, evidence, alias_index)
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
                reason_code=ProvenanceReasonCode.STRUCTURAL_CONFLICT,
                confidence=1.0,
            )
        provenances.append(provenance)

    return TruthReport(claims=provenances)
