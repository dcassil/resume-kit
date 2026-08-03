"""Unit tests for New (no-upstream-equivalent) canonical domain models."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import (
    AnalysisReport,
    Artifact,
    ArtifactKind,
    CandidateEvidence,
    ChangeSet,
    ClaimProvenance,
    EvidenceKind,
    JobDescription,
    ProvenanceStatus,
    Requirement,
    RequirementKind,
    Severity,
    Warning,
)


def test_job_description_construction_and_defaults() -> None:
    jd = JobDescription(
        title="Engineer",
        requirements=[Requirement(text="5y Python", keywords=["python"])],
    )
    assert jd.requirements[0].kind is RequirementKind.REQUIRED
    assert jd.qualifications == []
    assert JobDescription().model_dump() == JobDescription.model_validate({}).model_dump()


def test_job_description_json_roundtrip() -> None:
    jd = JobDescription(
        title="Data Scientist",
        qualifications=[Requirement(text="PhD", kind=RequirementKind.PREFERRED)],
        keywords=["ml", "python"],
    )
    again = JobDescription.model_validate_json(jd.model_dump_json())
    assert again == jd


def test_candidate_evidence_defaults() -> None:
    ev = CandidateEvidence(id="e1", kind=EvidenceKind.PROJECT, content="Built X")
    assert ev.user_confirmed is False
    assert ev.tags == []


def test_provenance_status_enum_values() -> None:
    assert {s.value for s in ProvenanceStatus} == {
        "verified",
        "supported",
        "partially-supported",
        "user-confirmed",
        "ambiguous",
        "unsupported",
        "contradicted",
    }


def test_claim_provenance_confidence_bounds() -> None:
    cp = ClaimProvenance(claim="Led team", status=ProvenanceStatus.SUPPORTED, evidence_ids=["e1"])
    assert cp.confidence == 1.0
    with pytest.raises(ValidationError):
        ClaimProvenance(claim="x", status=ProvenanceStatus.AMBIGUOUS, confidence=2.0)


def test_warning_is_frozen_and_defaults_to_warning_severity() -> None:
    w = Warning(message="dropped a role")
    assert w.severity is Severity.WARNING
    with pytest.raises(ValidationError):
        w.message = "mutated"


def test_artifact_roundtrip() -> None:
    art = Artifact(
        kind=ArtifactKind.COVER_LETTER,
        content="Dear hiring manager",
        warnings=[Warning(message="tone check", severity=Severity.INFO)],
    )
    again = Artifact.model_validate_json(art.model_dump_json())
    assert again == art


def test_analysis_report_composes_and_roundtrips() -> None:
    report = AnalysisReport(warnings=[Warning(message="low keyword match")])
    assert report.ats_score is None
    again = AnalysisReport.model_validate_json(report.model_dump_json())
    assert again == report


def test_change_set_defaults() -> None:
    cs = ChangeSet()
    assert cs.changes == []
    assert cs.diffs == []
    assert cs.summary is None
