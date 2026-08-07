"""Rule + classification tests for the best-practices analyzer (RIT-T-0117)."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

import pytest
from resume_kit_schemas import (
    AdditionalInfo,
    Experience,
    ResolutionKind,
    ResumeDocument,
)
from resume_kit_scoring import (
    analyze_best_practices,
    foundational_skills,
    project_scoredoc,
    summary_too_long,
)

_REF = date(2025, 1, 1)


def _analyze(resume: ResumeDocument):
    return analyze_best_practices(resume, project_scoredoc(resume, reference_date=_REF))


def _codes(report):
    return [f.rule_code for f in report.findings]


def _quantification_findings(report):
    return [f for f in report.findings if f.rule_code == "MISSING_QUANTIFICATION"]


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


def test_missing_quantification_emits_one_finding_per_unquantified_bullet() -> None:
    # RIT-T-0143: whole-resume quantification emits every targeted prompt, not a
    # capped batch plus an aggregate advisory.
    resume = ResumeDocument(
        workExperience=[
            Experience(
                id=1,
                title="E",
                company="X",
                years="2020-2022",
                description=[
                    "Maintained the internal wiki",
                    "Reduced onboarding friction for new hires",
                ],
            ),
            Experience(
                id=2,
                title="Senior E",
                company="Y",
                years="2022-2024",
                description=[
                    "Owned the release checklist",
                    "Improved incident response workflows",
                    "Coordinated roadmap planning",
                ],
            ),
        ]
    )
    report = _analyze(resume)
    per_bullet = _quantification_findings(report)
    locations = [(f.location.entity_id, f.location.bullet_index) for f in per_bullet]

    assert len(per_bullet) == 5
    assert locations == [("1", 1), ("2", 1), ("1", 0), ("2", 0), ("2", 2)]
    assert all(f.elicitation_prompt for f in per_bullet)
    assert "MISSING_QUANTIFICATION_MORE" not in _codes(report)


def test_missing_quantification_prioritizes_impact_verb_bullets() -> None:
    # RIT-T-0130: bullets with an impact verb are surfaced ahead of plain ones.
    resume = ResumeDocument(
        workExperience=[
            Experience(id=1, title="E", company="X", years="2020-2022",
                       description=[
                           "Maintained the internal wiki",          # plain
                           "Attended weekly planning meetings",      # plain
                           "Reduced onboarding friction for new hires",  # impact
                       ])
        ]
    )
    report = _analyze(resume)
    per_bullet = _quantification_findings(report)
    # The impact-verb bullet (index 2) ranks first.
    assert per_bullet[0].location.bullet_index == 2


def test_missing_quantification_has_no_aggregate_advisory() -> None:
    resume = ResumeDocument(
        workExperience=[
            Experience(id=1, title="E", company="X", years="2020-2022",
                       description=["Maintained the billing service", "Ran the standup"])
        ]
    )
    codes = _codes(_analyze(resume))
    assert codes.count("MISSING_QUANTIFICATION") == 2
    assert "MISSING_QUANTIFICATION_MORE" not in codes


def test_buzzword_in_summary_auto_suggestible() -> None:
    resume = ResumeDocument(summary="A results-driven team player who ships.")
    report = _analyze(resume)
    bw = [f for f in report.findings if f.rule_code == "BUZZWORD"]
    assert bw and all(f.resolution_kind is ResolutionKind.AUTO_SUGGESTIBLE for f in bw)


@pytest.mark.parametrize(
    ("rule_code", "resume", "detector_hit"),
    [
        (
            "SUMMARY_TOO_LONG",
            ResumeDocument(summary=" ".join(f"word{i}" for i in range(61))),
            lambda: summary_too_long(" ".join(f"word{i}" for i in range(61))),
        ),
        (
            "FOUNDATIONAL_SKILL",
            ResumeDocument(additional=AdditionalInfo(technicalSkills=["Python", "Email"])),
            lambda: foundational_skills(["Python", "Email"]) == ["Email"],
        ),
    ],
)
def test_non_wording_rules_are_detectors_not_best_practice_findings(
    rule_code: str,
    resume: ResumeDocument,
    detector_hit: Callable[[], bool],
) -> None:
    report = _analyze(resume)
    assert detector_hit()
    assert rule_code not in _codes(report)


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
