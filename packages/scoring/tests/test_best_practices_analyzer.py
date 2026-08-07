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


def test_missing_quantification_capped_with_aggregate_note() -> None:
    # RIT-T-0130: >cap unquantified bullets → exactly 3 per-bullet findings plus
    # one MISSING_QUANTIFICATION_MORE advisory naming the remainder.
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf"]
    bullets = [f"Maintained the internal {w} service" for w in words]
    resume = ResumeDocument(
        workExperience=[
            Experience(id=1, title="E", company="X", years="2020-2022",
                       description=bullets)
        ]
    )
    report = _analyze(resume)
    per_bullet = [f for f in report.findings if f.rule_code == "MISSING_QUANTIFICATION"]
    more = [f for f in report.findings if f.rule_code == "MISSING_QUANTIFICATION_MORE"]
    assert len(per_bullet) == 3
    assert all(f.location.bullet_index is not None for f in per_bullet)
    assert len(more) == 1
    assert more[0].severity is FindingSeverity.REVIEW_NOTE
    assert more[0].location.bullet_index is None
    assert "4 more" in more[0].message  # 7 - 3


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
    per_bullet = [f for f in report.findings if f.rule_code == "MISSING_QUANTIFICATION"]
    # All 3 fit under the cap, but the impact-verb bullet (index 2) ranks first.
    assert per_bullet[0].location.bullet_index == 2


def test_missing_quantification_no_aggregate_when_within_cap() -> None:
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
