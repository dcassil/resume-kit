"""Deterministic resume budget enforcement for the perfect stage."""

from __future__ import annotations

from resume_kit_policy import ResumeShapePolicy
from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.budget import BudgetViolation
from resume_kit_schemas.shape import ContentFate, ContentLedger

_PERFECT_LEDGER_OK_FATES = frozenset(
    {
        ContentFate.PRESENT_AFTER,
        ContentFate.MOVED,
        ContentFate.DEDUPED,
        ContentFate.DROPPED_BY_EXPLICIT_DECISION,
        ContentFate.DROPPED_BY_RANKED_BUDGET,
        ContentFate.COMPRESSED,
    }
)
_TARGET_REQUIRED_FATES = frozenset(
    {
        ContentFate.PRESENT_AFTER,
        ContentFate.MOVED,
        ContentFate.DEDUPED,
    }
)
_REASON_REQUIRED_FATES = frozenset(
    {
        ContentFate.DROPPED_BY_EXPLICIT_DECISION,
        ContentFate.DROPPED_BY_RANKED_BUDGET,
        ContentFate.COMPRESSED,
    }
)


def budget_enforce(
    resume: ResumeDocument, policy: ResumeShapePolicy
) -> list[BudgetViolation]:
    """Return quantified budget violations without modifying ``resume``."""

    budgets = policy.informational_budgets
    violations: list[BudgetViolation] = []

    if budgets.max_skills is not None:
        _append_violation(
            violations,
            dimension="skills",
            location=None,
            limit=budgets.max_skills,
            actual=len(resume.additional.technicalSkills),
        )

    if budgets.max_experience_entries is not None:
        _append_violation(
            violations,
            dimension="experience_entries",
            location=None,
            limit=budgets.max_experience_entries,
            actual=len(resume.workExperience),
        )

    if budgets.max_bullets_per_role is not None:
        for work_index, experience in enumerate(resume.workExperience):
            _append_violation(
                violations,
                dimension="bullets_per_role",
                location=f"workExperience[{work_index}]",
                limit=budgets.max_bullets_per_role,
                actual=len(experience.description),
            )

    if budgets.max_summary_words is not None:
        _append_violation(
            violations,
            dimension="summary_words",
            location=None,
            limit=budgets.max_summary_words,
            actual=_word_count(resume.summary),
        )

    if budgets.max_bullet_words is not None:
        for work_index, experience in enumerate(resume.workExperience):
            for achievement_index, bullet in enumerate(experience.description):
                _append_violation(
                    violations,
                    dimension="bullet_words",
                    location=(
                        f"workExperience[{work_index}]"
                        f".description[{achievement_index}]"
                    ),
                    limit=budgets.max_bullet_words,
                    actual=_word_count(bullet),
                )

    return violations


def content_ledger_ok_perfect(ledger: ContentLedger) -> bool:
    """Return True iff every entry is accounted for by perfect-stage rules."""

    for entry in ledger.entries:
        if not _has_text(entry.token):
            return False
        if entry.fate not in _PERFECT_LEDGER_OK_FATES:
            return False
        if entry.fate in _TARGET_REQUIRED_FATES and not _has_text(entry.target_path):
            return False
        if entry.fate in _REASON_REQUIRED_FATES and not _has_text(entry.reason):
            return False
    return True


def _append_violation(
    violations: list[BudgetViolation],
    *,
    dimension: str,
    location: str | None,
    limit: int,
    actual: int,
) -> None:
    overage = actual - limit
    if overage <= 0:
        return
    violations.append(
        BudgetViolation(
            dimension=dimension,
            location=location,
            limit=limit,
            actual=actual,
            overage=overage,
        )
    )


def _word_count(value: str | None) -> int:
    if value is None:
        return 0
    return len([token for token in value.split() if token])


def _has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""
