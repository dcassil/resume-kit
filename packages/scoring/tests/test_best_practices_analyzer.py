"""Rule + classification tests for the best-practices analyzer (RIT-T-0117)."""

from __future__ import annotations

from datetime import date

from resume_kit_schemas import (
    AdditionalInfo,
    Experience,
    FindingSeverity,
    ResolutionKind,
    ResumeDocument,
)
from resume_kit_scoring import analyze_best_practices, project_scoredoc

_REF = date(2025, 1, 1)


def _analyze(resume: ResumeDocument):
    return analyze_best_practices(resume, project_scoredoc(resume, reference_date=_REF))


def _codes(report):
    return [f.rule_code for f in report.findings]


def test_weak_opener_is_auto_suggestible_with_rewrite() -> None:
    resume = ResumeDocument(
        workExperience=[
            Experience(
                id=1,
                title="Eng",
                company="X",
                years="2020-2022",
                description=["Responsible for maintaining the billing service in 2021."],
            )
        ]
    )
    report = _analyze(resume)
    weak = next(f for f in report.findings if f.rule_code == "WEAK_OPENER")
    assert weak.resolution_kind is ResolutionKind.AUTO_SUGGESTIBLE
    assert weak.suggested_change and not weak.suggested_change.lower().startswith("responsible")
    assert weak.location.bullet_index == 0


def test_first_person_opener_flagged_and_stripped() -> None:
    resume = ResumeDocument(
        workExperience=[
            Experience(id=1, title="E", company="X", years="2020-2022",
                       description=["I led a team of 5 engineers."])
        ]
    )
    report = _analyze(resume)
    fp = next(f for f in report.findings if f.rule_code == "FIRST_PERSON_OPENER")
    assert fp.suggested_change and not fp.suggested_change.lower().startswith("i ")


def test_missing_quantification_needs_user_input() -> None:
    resume = ResumeDocument(
        workExperience=[
            Experience(id=1, title="E", company="X", years="2020-2022",
                       description=["Improved the onboarding flow significantly."])
        ]
    )
    report = _analyze(resume)
    mq = next(f for f in report.findings if f.rule_code == "MISSING_QUANTIFICATION")
    assert mq.resolution_kind is ResolutionKind.NEEDS_USER_INPUT
    assert mq.elicitation_prompt


def test_quantified_bullet_not_flagged_missing() -> None:
    resume = ResumeDocument(
        workExperience=[
            Experience(id=1, title="E", company="X", years="2020-2022",
                       description=["Cut latency 40% across the fleet."])
        ]
    )
    assert "MISSING_QUANTIFICATION" not in _codes(_analyze(resume))


def test_buzzword_in_summary_auto_suggestible() -> None:
    resume = ResumeDocument(summary="A results-driven team player who ships.")
    report = _analyze(resume)
    bw = [f for f in report.findings if f.rule_code == "BUZZWORD"]
    assert bw and all(f.resolution_kind is ResolutionKind.AUTO_SUGGESTIBLE for f in bw)


def test_foundational_skill_flagged() -> None:
    resume = ResumeDocument(additional=AdditionalInfo(technicalSkills=["Python", "Email"]))
    report = _analyze(resume)
    fs = next(f for f in report.findings if f.rule_code == "FOUNDATIONAL_SKILL")
    assert fs.severity is FindingSeverity.RECOMMENDATION


def test_clean_bullet_produces_no_wording_findings() -> None:
    resume = ResumeDocument(
        workExperience=[
            Experience(id=1, title="E", company="X", years="2020-2022",
                       description=["Reduced billing incidents 40% over two quarters."])
        ]
    )
    codes = _codes(_analyze(resume))
    assert "WEAK_OPENER" not in codes
    assert "FIRST_PERSON_OPENER" not in codes
    assert "BUZZWORD" not in codes
    assert "MISSING_QUANTIFICATION" not in codes


def test_deterministic() -> None:
    resume = ResumeDocument(summary="A results-driven leader.")
    a = _analyze(resume).model_dump_json()
    b = _analyze(resume).model_dump_json()
    assert a == b
