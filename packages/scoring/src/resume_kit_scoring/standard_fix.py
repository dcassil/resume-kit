"""Deterministic ``base -> standard`` walkthrough apply engine (RIT-T-0118).

Applies accepted :class:`~resume_kit_schemas.BestPracticesReport` findings to the
``base`` resume to produce ``standard``. ``auto_suggestible`` findings apply their
``suggested_change`` (a ready replacement string); ``needs_user_input`` findings
apply a user-supplied rewrite passed in ``answers`` (keyed by
:func:`finding_key`), and are otherwise deferred — the walkthrough never
fabricates a value the user did not provide.

Scope: findings located at the ``summary`` or an ``experience`` bullet (the core
wording pass — weak openers, first-person, buzzwords, quantification, summary
length). Skills-section findings (e.g. foundational-tool removal) are deferred to
a later increment. Pure/deterministic; the write path + claim-preservation gate
live in the facade ``build_standard`` capability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from resume_kit_schemas import (
    BestPracticesFinding,
    BestPracticesReport,
    ResolutionKind,
    ResumeDocument,
)


@dataclass
class StandardFixResult:
    """Outcome of applying accepted best-practices edits."""

    resume: ResumeDocument
    applied: list[str] = field(default_factory=list)
    deferred: list[str] = field(default_factory=list)


def finding_key(finding: BestPracticesFinding) -> str:
    """Stable key a caller uses to map a user answer to a needs-input finding."""
    loc = finding.location
    return f"{finding.rule_code}|{loc.section}|{loc.entity_id}|{loc.bullet_index}"


def _apply_to_location(data: dict[str, Any], finding: BestPracticesFinding, value: str) -> bool:
    section = finding.location.section
    if section == "summary":
        data["summary"] = value
        return True
    if section == "experience":
        entity_id = finding.location.entity_id
        idx = finding.location.bullet_index
        if entity_id is None or idx is None:
            return False
        for exp in data.get("workExperience", []) or []:
            if isinstance(exp, dict) and str(exp.get("id")) == entity_id:
                desc = exp.get("description") or []
                if 0 <= idx < len(desc):
                    desc[idx] = value
                    return True
    return False


def apply_best_practices_edits(
    resume: ResumeDocument,
    report: BestPracticesReport,
    answers: dict[str, str] | None = None,
) -> StandardFixResult:
    """Apply accepted best-practices findings to ``resume`` -> ``standard`` draft.

    ``answers`` maps :func:`finding_key` -> the user's rewrite for
    ``needs_user_input`` findings. auto_suggestible findings apply their
    ``suggested_change``. Any finding outside the summary/experience-bullet scope,
    or a needs-input finding with no answer, is deferred (not applied).
    """
    answers = answers or {}
    data: dict[str, Any] = resume.model_dump(by_alias=True)
    applied: list[str] = []
    deferred: list[str] = []

    def _loc_key(finding: BestPracticesFinding) -> tuple[str | None, str | None, int | None]:
        loc = finding.location
        return (loc.section, loc.entity_id, loc.bullet_index)

    # Group findings by target location. Multiple findings can target the same
    # bullet/summary; since each ``suggested_change`` is a full replacement
    # computed from the original text, applying more than one would clobber — so
    # per location we pick a single winner: an answered needs-input rewrite
    # (supersedes everything) else the first auto-suggestible edit; the rest are
    # deferred (a re-run after this edit surfaces them again).
    groups: dict[tuple[str | None, str | None, int | None], list[BestPracticesFinding]] = {}
    order: list[tuple[str | None, str | None, int | None]] = []
    for finding in report.findings:
        if finding.location.section not in ("summary", "experience"):
            deferred.append(finding.rule_code)
            continue
        key = _loc_key(finding)
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(finding)

    for key in order:
        group = groups[key]
        answered = next(
            (
                f
                for f in group
                if f.resolution_kind is ResolutionKind.NEEDS_USER_INPUT
                and answers.get(finding_key(f))
            ),
            None,
        )
        auto = next(
            (f for f in group if f.resolution_kind is ResolutionKind.AUTO_SUGGESTIBLE),
            None,
        )
        if answered is not None:
            winner, value = answered, answers[finding_key(answered)]
        elif auto is not None:
            winner, value = auto, (auto.suggested_change or "")
        else:
            winner, value = None, ""
        for f in group:
            if f is winner and _apply_to_location(data, f, value):
                applied.append(f.rule_code)
            else:
                deferred.append(f.rule_code)

    return StandardFixResult(
        resume=ResumeDocument.model_validate(data),
        applied=applied,
        deferred=deferred,
    )


__all__ = ["StandardFixResult", "apply_best_practices_edits", "finding_key"]
