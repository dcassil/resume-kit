"""Tests for deterministic resume truth validation across all seven statuses."""

from __future__ import annotations

from resume_kit_evidence.builder import build_candidate_evidence
from resume_kit_evidence.truth import validate_resume_truth
from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.provenance import (
    ClaimProvenance,
    ProvenanceReasonCode,
    ProvenanceStatus,
)
from resume_kit_schemas.results import TruthReport


def _evidence(*records: CandidateEvidence) -> list[CandidateEvidence]:
    return list(records)


def _skill(name: str, *, confirmed: bool = False) -> CandidateEvidence:
    return CandidateEvidence(
        id=f"s-{name.lower()}",
        kind=EvidenceKind.SKILL,
        content=name,
        tags=[name],
        user_confirmed=confirmed,
    )


def _bullet(text: str, *, confirmed: bool = False) -> CandidateEvidence:
    return CandidateEvidence(
        id=f"b-{abs(hash(text))}",
        kind=EvidenceKind.WORK_HISTORY,
        content=text,
        user_confirmed=confirmed,
    )


def _status_for(report: TruthReport, field_path: str) -> ProvenanceStatus:
    return _claim_for(report, field_path).status


def _claim_for(report: TruthReport, field_path: str) -> ClaimProvenance:
    for claim in report.claims:
        if claim.field_path == field_path:
            return claim
    raise AssertionError(f"no claim for {field_path}")


def _resume(**kw: object) -> ResumeDocument:
    data: dict[str, object] = {
        "additional": {"technicalSkills": []},
        "workExperience": [],
    }
    data.update(kw)
    return ResumeDocument.model_validate(data)


def test_verified_from_exact_user_confirmed_match() -> None:
    resume = _resume(additional={"technicalSkills": ["Python"]})
    report = validate_resume_truth(resume, _evidence(_skill("Python", confirmed=True)))
    assert _status_for(report, "additional.technicalSkills[0]") is ProvenanceStatus.VERIFIED


def test_supported_from_exact_unconfirmed_match() -> None:
    resume = _resume(additional={"technicalSkills": ["Python"]})
    report = validate_resume_truth(resume, _evidence(_skill("Python", confirmed=False)))
    assert _status_for(report, "additional.technicalSkills[0]") is ProvenanceStatus.SUPPORTED


def test_user_confirmed_from_strong_confirmed_overlap() -> None:
    resume = _resume(
        workExperience=[{"company": "Acme", "description": ["Led a team of four engineers daily"]}]
    )
    evidence = _evidence(_bullet("Led a team of four engineers", confirmed=True))
    report = validate_resume_truth(resume, evidence)
    assert (
        _status_for(report, "workExperience[0].description[0]") is ProvenanceStatus.USER_CONFIRMED
    )


def test_partially_supported_from_substantial_overlap() -> None:
    resume = _resume(
        workExperience=[
            {"company": "Acme", "description": ["Built a scalable payments API service"]}
        ]
    )
    evidence = _evidence(_bullet("Built a payments API", confirmed=False))
    report = validate_resume_truth(resume, evidence)
    assert (
        _status_for(report, "workExperience[0].description[0]")
        is ProvenanceStatus.PARTIALLY_SUPPORTED
    )


def test_ambiguous_from_weak_overlap() -> None:
    resume = _resume(
        workExperience=[
            {
                "company": "Acme",
                "description": ["Improved payments latency across regions worldwide"],
            }
        ]
    )
    evidence = _evidence(_bullet("Reviewed unrelated documentation payments", confirmed=False))
    report = validate_resume_truth(resume, evidence)
    assert _status_for(report, "workExperience[0].description[0]") is ProvenanceStatus.AMBIGUOUS


def test_unsupported_when_no_overlap() -> None:
    resume = _resume(
        workExperience=[{"company": "Acme", "description": ["Orchestrated kubernetes clusters"]}]
    )
    evidence = _evidence(_bullet("Wrote quarterly financial summaries", confirmed=False))
    report = validate_resume_truth(resume, evidence)
    assert _status_for(report, "workExperience[0].description[0]") is ProvenanceStatus.UNSUPPORTED
    assert report.has_unsupported_or_contradicted is True
    assert report.passed is False


def test_unsupported_from_absent_skill() -> None:
    resume = _resume(additional={"technicalSkills": ["Haskell"]})
    # Evidence knows only Python; absent-but-not-refuted Haskell needs evidence.
    report = validate_resume_truth(resume, _evidence(_skill("Python")))
    claim = _claim_for(report, "additional.technicalSkills[0]")
    assert claim.status is ProvenanceStatus.UNSUPPORTED
    assert claim.reason_code is ProvenanceReasonCode.MISSING_EVIDENCE
    assert report.has_unsupported_or_contradicted is True


def test_contradicted_from_refuted_skill() -> None:
    resume = _resume(additional={"technicalSkills": ["Haskell"]})
    report = validate_resume_truth(
        resume,
        _evidence(
            _skill("Python"),
            CandidateEvidence(
                id="refute-haskell",
                kind=EvidenceKind.USER_STATEMENT,
                content="Haskell",
                tags=["refuted"],
                user_confirmed=True,
            ),
        ),
    )
    claim = _claim_for(report, "additional.technicalSkills[0]")
    assert claim.status is ProvenanceStatus.CONTRADICTED
    assert claim.reason_code is ProvenanceReasonCode.REFUTED_BY_EVIDENCE


def test_unsupported_from_absent_certification() -> None:
    resume = _resume(
        additional={
            "technicalSkills": [],
            "certificationsTraining": ["Invented Cert"],
        }
    )
    report = validate_resume_truth(resume, _evidence(_skill("Python")))
    claim = _claim_for(report, "additional.certificationsTraining[0]")
    assert claim.status is ProvenanceStatus.UNSUPPORTED
    assert claim.reason_code is ProvenanceReasonCode.MISSING_EVIDENCE


def test_unsupported_from_absent_company() -> None:
    resume = _resume(workExperience=[{"company": "Globex", "description": []}])
    report = validate_resume_truth(resume, _evidence(_skill("Python")))
    claim = _claim_for(report, "workExperience[0].company")
    assert claim.status is ProvenanceStatus.UNSUPPORTED
    assert claim.reason_code is ProvenanceReasonCode.MISSING_EVIDENCE


def test_all_seven_statuses_reachable_in_one_report() -> None:
    resume = _resume(
        additional={
            "technicalSkills": ["Python", "Go", "Haskell"],
        },
        workExperience=[
            {
                "company": "Acme",
                "description": [
                    "Led a team of four engineers daily",  # user_confirmed
                    "Built a scalable payments API service",  # partially_supported
                    "Improved payments latency across regions worldwide",  # ambiguous
                    "Orchestrated kubernetes clusters end to end",  # unsupported
                ],
            }
        ],
    )
    evidence = _evidence(
        _skill("Python", confirmed=True),  # verified
        _skill("Go", confirmed=False),  # supported
        _bullet("Led a team of four engineers", confirmed=True),
        _bullet("Built a payments API", confirmed=False),
        _bullet("Reviewed unrelated documentation payments", confirmed=False),
        _bullet("Wrote quarterly financial summaries", confirmed=False),
        CandidateEvidence(
            id="refute-haskell",
            kind=EvidenceKind.USER_STATEMENT,
            content="Haskell",
            tags=["refuted"],
        ),
    )
    report = validate_resume_truth(resume, evidence)
    statuses = {claim.status for claim in report.claims}
    assert statuses == set(ProvenanceStatus)


def test_summary_flags_clean_report_as_passed() -> None:
    resume = _resume(additional={"technicalSkills": ["Python"]})
    report = validate_resume_truth(resume, _evidence(_skill("Python", confirmed=True)))
    assert report.passed is True
    assert report.has_unsupported_or_contradicted is False


def test_user_confirmed_claims_support_without_store() -> None:
    # Approved claims are function inputs only — no persistence anywhere.
    approved = build_candidate_evidence(
        ResumeDocument(), approved_claims=["Shipped a realtime analytics pipeline"]
    )
    resume = _resume(
        workExperience=[
            {"company": "Acme", "description": ["Shipped a realtime analytics pipeline"]}
        ]
    )
    report = validate_resume_truth(resume, approved)
    assert _status_for(report, "workExperience[0].description[0]") is ProvenanceStatus.VERIFIED


def test_structural_section_drop_contradicts_claims() -> None:
    # Evidence carries a summary (populated section) but the resume drops it,
    # and the surviving skill claim is otherwise supportable.
    resume = _resume(additional={"technicalSkills": ["Python"]})
    evidence = _evidence(
        CandidateEvidence(
            id="sum",
            kind=EvidenceKind.MASTER_RESUME,
            content="A long-standing engineer summary line",
        ),
        _skill("Python", confirmed=True),
    )
    # sections_preserved compares master (summary populated) vs resume (summary "").
    report = validate_resume_truth(resume, evidence)
    assert report.has_unsupported_or_contradicted is True
    assert _status_for(report, "additional.technicalSkills[0]") is ProvenanceStatus.CONTRADICTED
    assert (
        _claim_for(report, "additional.technicalSkills[0]").reason_code
        is ProvenanceReasonCode.STRUCTURAL_CONFLICT
    )


def test_alias_file_supports_truth_validation(tmp_path) -> None:
    alias_file = tmp_path / "aliases.json"
    alias_file.write_text('{"version": 1, "aliases": {"quibblewidget": ["zorbulator"]}}')
    resume = _resume(additional={"technicalSkills": ["zorbulator"]})
    report = validate_resume_truth(
        resume,
        _evidence(_skill("quibblewidget")),
        alias_file=str(alias_file),
    )
    assert _status_for(report, "additional.technicalSkills[0]") is ProvenanceStatus.SUPPORTED


def test_inflectional_variant_supports_truth_validation() -> None:
    resume = _resume(additional={"technicalSkills": ["code reviews"]})
    report = validate_resume_truth(resume, _evidence(_skill("code review")))
    assert _status_for(report, "additional.technicalSkills[0]") is ProvenanceStatus.SUPPORTED
