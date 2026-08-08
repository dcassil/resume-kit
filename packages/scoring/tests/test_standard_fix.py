"""base -> standard best-practices apply engine (RIT-T-0118)."""

from __future__ import annotations

from datetime import date

from resume_kit_schemas import ResumeDocument
from resume_kit_scoring import (
    RefineFixResult,
    StandardFixResult,
    analyze_best_practices,
    apply_best_practices_edits,
    finding_key,
    project_scoredoc,
)

_REF = date(2025, 1, 1)


def _report(resume: ResumeDocument):
    return analyze_best_practices(resume, project_scoredoc(resume, reference_date=_REF))


def _base() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "Jane", "email": "j@x.com", "phone": "5"},
            "summary": "A results-driven team player who ships.",
            "workExperience": [
                {"id": 1, "title": "Eng", "company": "Acme", "years": "2020-2022",
                 "description": ["Responsible for maintaining the billing service."]}
            ],
            "additional": {"technicalSkills": ["Python"]},
        }
    )


def test_auto_suggestible_buzzword_and_weak_opener_applied() -> None:
    base = _base()
    result = apply_best_practices_edits(base, _report(base))
    # buzzword removed from summary
    assert "results-driven" not in result.resume.summary.lower()
    # weak opener rewritten in the bullet
    assert not result.resume.workExperience[0].description[0].lower().startswith("responsible for")
    assert "WEAK_OPENER" in result.applied
    assert "BUZZWORD" in result.applied


def test_needs_input_deferred_without_answer_then_applied_with_answer() -> None:
    base = _base()
    report = _report(base)
    # find the MISSING_QUANTIFICATION finding on the bullet
    mq = next(f for f in report.findings if f.rule_code == "MISSING_QUANTIFICATION")

    # without an answer -> deferred
    r1 = apply_best_practices_edits(base, report)
    assert "MISSING_QUANTIFICATION" in r1.deferred

    # with a user-supplied rewrite -> applied
    answer = "Cut billing incidents 40% over two quarters."
    r2 = apply_best_practices_edits(base, report, {finding_key(mq): answer})
    assert "MISSING_QUANTIFICATION" in r2.applied
    assert any("40%" in b for b in r2.resume.workExperience[0].description)


def test_claims_unchanged_by_wording_edits() -> None:
    base = _base()
    result = apply_best_practices_edits(base, _report(base))
    assert result.resume.workExperience[0].company == "Acme"
    assert result.resume.workExperience[0].title == "Eng"
    assert result.resume.additional.technicalSkills == ["Python"]


def test_deterministic() -> None:
    base = _base()
    report = _report(base)
    a = apply_best_practices_edits(base, report).resume.model_dump_json()
    b = apply_best_practices_edits(base, report).resume.model_dump_json()
    assert a == b


def test_standard_fix_result_is_refine_fix_result_alias() -> None:
    assert StandardFixResult is RefineFixResult
