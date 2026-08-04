"""Characterization tests for fabrication.py — locking upstream refiner behavior.

Each test encodes an observable behavior from upstream
apps/backend/app/services/refiner.py (validate_master_alignment at :290 and
fix_alignment_violations at :591) so future divergence is caught immediately.
"""

from __future__ import annotations

from typing import Any

from resume_kit_evidence.fabrication import (
    fix_alignment_violations,
    validate_master_alignment,
)
from resume_kit_schemas import AlignmentViolation


def _master(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "Backend engineer using Kubernetes daily.",
        "workExperience": [{"company": "Acme", "title": "Dev", "description": []}],
        "additional": {
            "technicalSkills": ["Python", "Django"],
            "certificationsTraining": ["AWS Certified"],
        },
    }
    base.update(overrides)
    return base


# validate_master_alignment ---------------------------------------------------


def test_aligned_when_tailored_matches_master() -> None:
    report = validate_master_alignment(_master(), _master())
    assert report.is_aligned is True
    assert report.violations == []
    assert report.confidence_score == 1.0


def test_fabricated_skill_is_critical() -> None:
    tailored = _master(additional={"technicalSkills": ["Python", "Rust"]})
    report = validate_master_alignment(tailored, _master())
    assert report.is_aligned is False
    fabricated = [v for v in report.violations if v.violation_type == "fabricated_skill"]
    assert len(fabricated) == 1
    assert fabricated[0].value == "rust"
    assert fabricated[0].severity == "critical"


def test_allowed_jd_skill_is_not_a_violation() -> None:
    tailored = _master(additional={"technicalSkills": ["Python", "Rust"]})
    report = validate_master_alignment(tailored, _master(), allowed_new_skills={"Rust"})
    assert report.is_aligned is True
    assert report.violations == []


def test_allowed_jd_skill_normalized_with_punctuation_and_spacing() -> None:
    tailored = _master(additional={"technicalSkills": ["Python", "node.js"]})
    # allowed key given with different casing/spacing, same after normalization
    report = validate_master_alignment(
        tailored, _master(), allowed_new_skills={"Node.js"}
    )
    assert report.is_aligned is True
    assert report.violations == []


def test_skill_variant_via_substring_is_info() -> None:
    # "Python" (master) contains within "Python 3.x" (tailored) -> variant/info
    tailored = _master(additional={"technicalSkills": ["Python 3.x"]})
    report = validate_master_alignment(tailored, _master())
    variants = [v for v in report.violations if v.violation_type == "skill_variant"]
    assert len(variants) == 1
    assert variants[0].severity == "info"
    # info-only violations do not break alignment
    assert report.is_aligned is True


def test_skill_variant_via_master_text_is_info() -> None:
    # "Kubernetes" appears in the master summary text, not in skills -> info
    tailored = _master(additional={"technicalSkills": ["Kubernetes"]})
    report = validate_master_alignment(tailored, _master())
    variants = [v for v in report.violations if v.violation_type == "skill_variant"]
    assert len(variants) == 1
    assert variants[0].severity == "info"
    assert report.is_aligned is True


def test_fabricated_cert_is_critical() -> None:
    tailored = _master(
        additional={
            "technicalSkills": ["Python", "Django"],
            "certificationsTraining": ["AWS Certified", "GCP Pro"],
        }
    )
    report = validate_master_alignment(tailored, _master())
    certs = [v for v in report.violations if v.violation_type == "fabricated_cert"]
    assert len(certs) == 1
    assert certs[0].value == "gcp pro"
    assert certs[0].severity == "critical"
    assert report.is_aligned is False


def test_fabricated_company_is_critical_and_empty_skipped() -> None:
    tailored = _master(
        workExperience=[{"company": "Acme"}, {"company": "Globex"}, {"company": ""}]
    )
    report = validate_master_alignment(tailored, _master())
    companies = [v for v in report.violations if v.violation_type == "fabricated_company"]
    assert len(companies) == 1
    assert companies[0].value == "globex"
    assert companies[0].severity == "critical"


def test_confidence_decreases_per_violation() -> None:
    tailored = _master(additional={"technicalSkills": ["Python", "Rust", "Go"]})
    report = validate_master_alignment(tailored, _master())
    # two fabricated skills -> confidence 1.0 - 2*0.1
    assert len(report.violations) == 2
    assert report.confidence_score == 0.8


# fix_alignment_violations ----------------------------------------------------


def test_fix_removes_critical_fabricated_skill_only() -> None:
    tailored = _master(additional={"technicalSkills": ["Python", "Rust"]})
    violations = [
        AlignmentViolation(
            field_path="additional.technicalSkills",
            violation_type="fabricated_skill",
            value="rust",
            severity="critical",
        ),
        AlignmentViolation(
            field_path="additional.technicalSkills",
            violation_type="skill_variant",
            value="python",
            severity="info",
        ),
    ]
    fixed = fix_alignment_violations(tailored, violations)
    assert fixed["additional"]["technicalSkills"] == ["Python"]
    # original untouched (deep copy)
    assert tailored["additional"]["technicalSkills"] == ["Python", "Rust"]


def test_fix_removes_fabricated_cert() -> None:
    tailored = _master(
        additional={
            "technicalSkills": ["Python"],
            "certificationsTraining": ["AWS Certified", "GCP Pro"],
        }
    )
    violations = [
        AlignmentViolation(
            field_path="additional.certificationsTraining",
            violation_type="fabricated_cert",
            value="gcp pro",
            severity="critical",
        )
    ]
    fixed = fix_alignment_violations(tailored, violations)
    assert fixed["additional"]["certificationsTraining"] == ["AWS Certified"]


def test_fix_removes_fabricated_company_entry() -> None:
    tailored = _master(
        workExperience=[{"company": "Acme"}, {"company": "Globex"}]
    )
    violations = [
        AlignmentViolation(
            field_path="workExperience",
            violation_type="fabricated_company",
            value="globex",
            severity="critical",
        )
    ]
    fixed = fix_alignment_violations(tailored, violations)
    assert fixed["workExperience"] == [{"company": "Acme"}]


def test_fix_ignores_non_critical_violations() -> None:
    tailored = _master(additional={"technicalSkills": ["Python 3.x"]})
    violations = [
        AlignmentViolation(
            field_path="additional.technicalSkills",
            violation_type="skill_variant",
            value="python 3.x",
            severity="info",
        )
    ]
    fixed = fix_alignment_violations(tailored, violations)
    assert fixed["additional"]["technicalSkills"] == ["Python 3.x"]
