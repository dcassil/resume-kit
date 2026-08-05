"""Tests for the generic best-practices report schema (RIT-T-0116).

Covers: the shared severity taxonomy, the exactly-one-of
suggested_change/elicitation_prompt invariant paired with resolution_kind,
the reserved hard-gate justification rule, additive/backward-compat, a
serialize→deserialize round-trip, and a full-matrix fixture exercising every
severity and both resolution kinds.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import (
    BestPracticesFinding,
    BestPracticesReport,
    FindingLocation,
    FindingSeverity,
    ProvenanceKind,
    ResolutionKind,
)


def _auto(rule: str = "BUZZWORD", severity: FindingSeverity = FindingSeverity.WARNING):
    return BestPracticesFinding(
        rule_code=rule,
        message="msg",
        location=FindingLocation(section="summary"),
        severity=severity,
        resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
        suggested_change="Rewrite without the buzzword.",
    )


def _needs(rule: str = "MISSING_QUANTIFICATION", severity: FindingSeverity = FindingSeverity.RECOMMENDATION):
    return BestPracticesFinding(
        rule_code=rule,
        message="msg",
        location=FindingLocation(section="experience", entity_id="exp-1", bullet_index=0),
        severity=severity,
        resolution_kind=ResolutionKind.NEEDS_USER_INPUT,
        elicitation_prompt="What changed and by roughly how much?",
    )


def test_severity_taxonomy_has_exactly_five_members() -> None:
    assert [s.value for s in FindingSeverity] == [
        "hard-gate",
        "warning",
        "recommendation",
        "review-note",
        "out-of-scope-future",
    ]


def test_auto_suggestible_requires_suggested_change_and_no_prompt() -> None:
    with pytest.raises(ValidationError):
        BestPracticesFinding(
            rule_code="X",
            message="m",
            severity=FindingSeverity.WARNING,
            resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
        )  # missing suggested_change
    with pytest.raises(ValidationError):
        BestPracticesFinding(
            rule_code="X",
            message="m",
            severity=FindingSeverity.WARNING,
            resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
            suggested_change="ok",
            elicitation_prompt="should not be here",
        )


def test_needs_user_input_requires_prompt_and_no_suggested_change() -> None:
    with pytest.raises(ValidationError):
        BestPracticesFinding(
            rule_code="X",
            message="m",
            severity=FindingSeverity.RECOMMENDATION,
            resolution_kind=ResolutionKind.NEEDS_USER_INPUT,
        )  # missing elicitation_prompt
    with pytest.raises(ValidationError):
        BestPracticesFinding(
            rule_code="X",
            message="m",
            severity=FindingSeverity.RECOMMENDATION,
            resolution_kind=ResolutionKind.NEEDS_USER_INPUT,
            elicitation_prompt="ok",
            suggested_change="should not be here",
        )


def test_hard_gate_requires_justification() -> None:
    with pytest.raises(ValidationError):
        BestPracticesFinding(
            rule_code="TRUTH_FAIL",
            message="m",
            severity=FindingSeverity.HARD_GATE,
            resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
            suggested_change="fix",
        )  # no severity_justification
    ok = BestPracticesFinding(
        rule_code="TRUTH_FAIL",
        message="m",
        severity=FindingSeverity.HARD_GATE,
        resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
        suggested_change="fix",
        severity_justification="Fabricated metric contradicted by evidence.",
    )
    assert ok.severity is FindingSeverity.HARD_GATE


def test_unknown_severity_rejected() -> None:
    with pytest.raises(ValidationError):
        BestPracticesFinding.model_validate(
            {
                "rule_code": "X",
                "message": "m",
                "severity": "catastrophic",
                "resolution_kind": "auto_suggestible",
                "suggested_change": "y",
            }
        )


def test_report_round_trip() -> None:
    report = BestPracticesReport(
        resume_version="resumes/x-base.json",
        report_provenance=ProvenanceKind.DETERMINISTIC,
        findings=[_auto(), _needs()],
    )
    dumped = report.model_dump_json()
    restored = BestPracticesReport.model_validate_json(dumped)
    assert restored == report
    assert restored.findings[0].suggested_change is not None
    assert restored.findings[1].elicitation_prompt is not None


def test_full_matrix_fixture_valid_and_round_trips() -> None:
    """AC-7: at least one item per severity AND both resolution kinds."""
    findings = [
        BestPracticesFinding(
            rule_code="TRUTH_FAIL",
            message="Contradicted claim",
            severity=FindingSeverity.HARD_GATE,
            resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
            suggested_change="Remove the unsupported claim.",
            severity_justification="Contradicted by candidate evidence.",
        ),
        _auto("BUZZWORD", FindingSeverity.WARNING),
        _needs("MISSING_QUANTIFICATION", FindingSeverity.RECOMMENDATION),
        BestPracticesFinding(
            rule_code="SOFT_JUDGMENT",
            message="Is this really an accomplishment?",
            severity=FindingSeverity.REVIEW_NOTE,
            resolution_kind=ResolutionKind.NEEDS_USER_INPUT,
            elicitation_prompt="Can you describe the outcome?",
            provenance=ProvenanceKind.ASSISTED,
        ),
        BestPracticesFinding(
            rule_code="LAYOUT_MULTICOLUMN",
            message="Source file appears multi-column (needs REQ-011 inspection).",
            severity=FindingSeverity.OUT_OF_SCOPE_FUTURE,
            resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
            suggested_change="Flag for source-file layout review.",
        ),
    ]
    report = BestPracticesReport(
        resume_version="resumes/x-base.json",
        report_provenance=ProvenanceKind.ASSISTED,
        findings=findings,
    )
    severities = {f.severity for f in report.findings}
    assert severities == set(FindingSeverity)
    kinds = {f.resolution_kind for f in report.findings}
    assert kinds == set(ResolutionKind)
    assert BestPracticesReport.model_validate_json(report.model_dump_json()) == report
