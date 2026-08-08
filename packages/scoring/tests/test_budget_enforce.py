"""Budget enforcer and perfect-stage content ledger tests."""

from __future__ import annotations

import pytest
from resume_kit_policy import (
    InformationalShapeBudgets,
    ResumeShapePolicy,
    default_shape_policy,
)
from resume_kit_schemas import (
    AdditionalInfo,
    Experience,
    PersonalInfo,
    ResumeDocument,
)
from resume_kit_schemas.shape import ContentFate, ContentLedger, ContentLedgerEntry
from resume_kit_scoring import budget_enforce, content_ledger_ok_perfect


def _policy(budgets: InformationalShapeBudgets) -> ResumeShapePolicy:
    return default_shape_policy().model_copy(update={"informational_budgets": budgets})


def _resume(
    *,
    summary: str = "Builds reliable systems.",
    skills: int = 1,
    bullet_sets: list[list[str]] | None = None,
) -> ResumeDocument:
    work = [
        Experience(
            company=f"Company {work_index}",
            title="Engineer",
            description=list(bullets),
        )
        for work_index, bullets in enumerate(bullet_sets or [["Built APIs."]])
    ]
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Jane Engineer",
            email="jane@example.com",
        ),
        summary=summary,
        workExperience=work,
        additional=AdditionalInfo(
            technicalSkills=[f"Skill {index}" for index in range(skills)]
        ),
    )


@pytest.mark.parametrize(
    ("dimension", "resume", "budgets", "expected_location", "expected_actual"),
    [
        (
            "skills",
            _resume(skills=3),
            InformationalShapeBudgets(max_skills=2),
            None,
            3,
        ),
        (
            "experience_entries",
            _resume(
                bullet_sets=[
                    ["Built APIs."],
                    ["Shipped jobs."],
                    ["Led migrations."],
                ]
            ),
            InformationalShapeBudgets(max_experience_entries=2),
            None,
            3,
        ),
        (
            "bullets_per_role",
            _resume(bullet_sets=[["Built APIs.", "Shipped jobs.", "Led migrations."]]),
            InformationalShapeBudgets(max_bullets_per_role=2),
            "workExperience[0]",
            3,
        ),
        (
            "summary_words",
            _resume(summary="one two three four"),
            InformationalShapeBudgets(max_summary_words=3),
            None,
            4,
        ),
        (
            "bullet_words",
            _resume(bullet_sets=[["one two three four"]]),
            InformationalShapeBudgets(max_bullet_words=3),
            "workExperience[0].description[0]",
            4,
        ),
    ],
)
def test_budget_enforce_reports_each_over_budget_dimension(
    dimension: str,
    resume: ResumeDocument,
    budgets: InformationalShapeBudgets,
    expected_location: str | None,
    expected_actual: int,
) -> None:
    violations = [
        violation
        for violation in budget_enforce(resume, _policy(budgets))
        if violation.dimension == dimension
    ]

    assert len(violations) == 1
    assert violations[0].location == expected_location
    assert violations[0].actual == expected_actual
    assert violations[0].overage == violations[0].actual - violations[0].limit


@pytest.mark.parametrize(
    ("resume", "budgets"),
    [
        (_resume(skills=2), InformationalShapeBudgets(max_skills=2)),
        (
            _resume(bullet_sets=[["Built APIs."], ["Shipped jobs."]]),
            InformationalShapeBudgets(max_experience_entries=2),
        ),
        (
            _resume(bullet_sets=[["Built APIs.", "Shipped jobs."]]),
            InformationalShapeBudgets(max_bullets_per_role=2),
        ),
        (
            _resume(summary="one two three"),
            InformationalShapeBudgets(max_summary_words=3),
        ),
        (
            _resume(bullet_sets=[["one two three"]]),
            InformationalShapeBudgets(max_bullet_words=3),
        ),
    ],
)
def test_budget_enforce_skips_clean_dimensions(
    resume: ResumeDocument,
    budgets: InformationalShapeBudgets,
) -> None:
    assert budget_enforce(resume, _policy(budgets)) == []


def test_budget_enforce_skips_none_budgets() -> None:
    resume = _resume(
        skills=3,
        bullet_sets=[
            ["one two three four", "five six seven eight"],
            ["nine ten eleven twelve"],
        ],
    )
    budgets = InformationalShapeBudgets(
        max_skills=None,
        max_experience_entries=None,
        max_bullets_per_role=None,
        max_summary_words=None,
        max_bullet_words=None,
    )

    assert budget_enforce(resume, _policy(budgets)) == []


def test_budget_enforce_emits_deterministic_order_and_locations() -> None:
    resume = _resume(
        summary="one two three four",
        skills=2,
        bullet_sets=[
            ["one two three", "four five six"],
            ["seven eight nine", "ten eleven twelve"],
        ],
    )
    budgets = InformationalShapeBudgets(
        max_skills=1,
        max_experience_entries=1,
        max_bullets_per_role=1,
        max_summary_words=3,
        max_bullet_words=2,
    )

    violations = budget_enforce(resume, _policy(budgets))

    assert [(violation.dimension, violation.location) for violation in violations] == [
        ("skills", None),
        ("experience_entries", None),
        ("bullets_per_role", "workExperience[0]"),
        ("bullets_per_role", "workExperience[1]"),
        ("summary_words", None),
        ("bullet_words", "workExperience[0].description[0]"),
        ("bullet_words", "workExperience[0].description[1]"),
        ("bullet_words", "workExperience[1].description[0]"),
        ("bullet_words", "workExperience[1].description[1]"),
    ]


@pytest.mark.parametrize(
    "fate",
    [
        ContentFate.DROPPED_BY_EXPLICIT_DECISION,
        ContentFate.DROPPED_BY_RANKED_BUDGET,
        ContentFate.COMPRESSED,
    ],
)
def test_content_ledger_ok_perfect_accepts_accounted_drops_and_compressions(
    fate: ContentFate,
) -> None:
    ledger = ContentLedger(
        entries=[
            ContentLedgerEntry(
                token="Python",
                fate=fate,
                source_path="additional.technicalSkills[0]",
                reason="ranked below stronger evidence",
            )
        ]
    )

    assert content_ledger_ok_perfect(ledger)


@pytest.mark.parametrize(
    "entry",
    [
        ContentLedgerEntry(
            token="Rust",
            fate=ContentFate.UNRESOLVED,
            source_path="additional.technicalSkills[0]",
        ),
        ContentLedgerEntry(
            token="Skills",
            fate=ContentFate.DROPPED_AS_HEADING,
            source_path="customSections.skills",
            reason="heading",
        ),
        ContentLedgerEntry(
            token="added_tokens",
            fate=ContentFate.DROPPED_AS_PARSER_ARTIFACT,
            source_path="metadata.added_tokens",
            reason="parser artifact",
        ),
        ContentLedgerEntry(
            token=" ",
            fate=ContentFate.MOVED,
            target_path="additional.technicalSkills[0]",
        ),
    ],
)
def test_content_ledger_ok_perfect_rejects_unaccounted_losses(
    entry: ContentLedgerEntry,
) -> None:
    assert not content_ledger_ok_perfect(ContentLedger(entries=[entry]))


@pytest.mark.parametrize(
    "fate",
    [
        ContentFate.DROPPED_BY_EXPLICIT_DECISION,
        ContentFate.DROPPED_BY_RANKED_BUDGET,
        ContentFate.COMPRESSED,
    ],
)
def test_content_ledger_ok_perfect_requires_reason_for_drop_or_compression(
    fate: ContentFate,
) -> None:
    ledger = ContentLedger(
        entries=[
            ContentLedgerEntry(
                token="Python",
                fate=fate,
                source_path="additional.technicalSkills[0]",
            )
        ]
    )

    assert not content_ledger_ok_perfect(ledger)


@pytest.mark.parametrize(
    "fate",
    [ContentFate.PRESENT_AFTER, ContentFate.MOVED, ContentFate.DEDUPED],
)
def test_content_ledger_ok_perfect_requires_target_for_present_moved_or_deduped(
    fate: ContentFate,
) -> None:
    ledger = ContentLedger(
        entries=[
            ContentLedgerEntry(
                token="Python",
                fate=fate,
                source_path="additional.technicalSkills[0]",
            )
        ]
    )

    assert not content_ledger_ok_perfect(ledger)
