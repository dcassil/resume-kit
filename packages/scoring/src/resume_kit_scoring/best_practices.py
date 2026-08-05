"""Generic job-independent best-practices analyzer (RIT-T-0117).

Scores a resume for generic structure + wording quality — distinct from the
job-keyword-driven composite score — and emits a
:class:`~resume_kit_schemas.BestPracticesReport`. Deterministic and offline: the
rules here are pure string/heuristic checks with no LLM and no clock reads (any
LLM-assisted judgments would be a clearly-separated, later addition marked
``ProvenanceKind.ASSISTED``; this module emits only ``DETERMINISTIC`` findings).

It reads bullet-level text from the resume and uses the projected
:class:`~resume_kit_schemas.ScoreDoc` for section/zone identity, so segmentation
is not re-derived here.

Each finding is classified per :class:`~resume_kit_schemas.ResolutionKind`:
``auto_suggestible`` when a concrete truthful rewrite is available now (e.g.
dropping a buzzword or a weak opener), ``needs_user_input`` when the fix requires
facts the system does not have (e.g. a real metric to quantify an accomplishment).

Implemented rules (deterministic): WEAK_OPENER, FIRST_PERSON_OPENER, BUZZWORD,
MISSING_QUANTIFICATION, FOUNDATIONAL_SKILL, SUMMARY_TOO_LONG. Further rules
(duplicate-bullet, equal-detail-per-job, tense/punctuation consistency) are
deferred to follow-up increments and are intentionally not silently claimed here.
"""

from __future__ import annotations

import re

from resume_kit_schemas import (
    BestPracticesFinding,
    BestPracticesReport,
    FindingLocation,
    FindingSeverity,
    ProvenanceKind,
    ResolutionKind,
    ResumeDocument,
    ScoreDoc,
)

_WEAK_OPENERS = (
    "responsible for",
    "duties included",
    "duties include",
    "worked on",
    "helped with",
    "assisted with",
    "involved in",
)
_FIRST_PERSON_RE = re.compile(r"^\s*(i|my|me)\b", re.IGNORECASE)
_BUZZWORDS = (
    "hardworking",
    "hard-working",
    "results-driven",
    "team player",
    "detail-oriented",
    "go-getter",
    "rock star",
    "rockstar",
    "ninja",
    "guru",
    "synergy",
    "synergies",
    "world-class",
    "best-in-class",
    "seasoned professional",
)
#: Foundational tools that dilute a skills section unless a role requires them.
_FOUNDATIONAL_SKILLS = ("email", "internet", "microsoft word", "web browsing", "typing")
_NUMBER_RE = re.compile(r"\d")
_SUMMARY_WORD_LIMIT = 60


def _strip_prefix(text: str, prefix: str) -> str:
    """Drop a leading weak *prefix* from *text* and re-capitalize."""
    rest = text[len(prefix):].lstrip(" :,-")
    return rest[:1].upper() + rest[1:] if rest else text


def _weak_opener(text: str) -> str | None:
    low = text.lower()
    for opener in _WEAK_OPENERS:
        if low.startswith(opener):
            return opener
    return None


def _bullets(resume: ResumeDocument):
    """Yield (entity_id, bullet_index, text) for every experience bullet."""
    for exp in resume.workExperience:
        for idx, bullet in enumerate(exp.description):
            if bullet.strip():
                yield str(exp.id), idx, bullet.strip()


def analyze_best_practices(resume: ResumeDocument, scoredoc: ScoreDoc) -> BestPracticesReport:
    """Return generic best-practices findings for *resume*.

    ``scoredoc`` supplies section/zone identity (not re-derived here). The
    report is deterministic for a fixed input.
    """
    findings: list[BestPracticesFinding] = []

    for entity_id, idx, bullet in _bullets(resume):
        loc = FindingLocation(section="experience", zone="experience", entity_id=entity_id, bullet_index=idx)

        opener = _weak_opener(bullet)
        if opener:
            findings.append(
                BestPracticesFinding(
                    rule_code="WEAK_OPENER",
                    message=f"Bullet opens with the weak phrase '{opener}'; lead with a strong action verb.",
                    location=loc,
                    severity=FindingSeverity.WARNING,
                    resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
                    suggested_change=_strip_prefix(bullet, opener),
                )
            )
        elif _FIRST_PERSON_RE.match(bullet):
            stripped = _FIRST_PERSON_RE.sub("", bullet).lstrip()
            findings.append(
                BestPracticesFinding(
                    rule_code="FIRST_PERSON_OPENER",
                    message="Bullet starts with a first-person pronoun; use implied first person.",
                    location=loc,
                    severity=FindingSeverity.RECOMMENDATION,
                    resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
                    suggested_change=stripped[:1].upper() + stripped[1:] if stripped else bullet,
                )
            )

        for word in _BUZZWORDS:
            if word in bullet.lower():
                findings.append(
                    BestPracticesFinding(
                        rule_code="BUZZWORD",
                        message=f"Buzzword '{word}' adds no evidence; remove or replace with a concrete result.",
                        location=loc,
                        severity=FindingSeverity.WARNING,
                        resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
                        suggested_change=re.sub(re.escape(word), "", bullet, flags=re.IGNORECASE).strip(),
                    )
                )

        if not _NUMBER_RE.search(bullet):
            findings.append(
                BestPracticesFinding(
                    rule_code="MISSING_QUANTIFICATION",
                    message="Bullet has no quantified outcome; quantify the impact where a real number exists.",
                    location=loc,
                    severity=FindingSeverity.RECOMMENDATION,
                    resolution_kind=ResolutionKind.NEEDS_USER_INPUT,
                    elicitation_prompt=(
                        "What changed because of this work, and by roughly how much "
                        "(percent, time, money, scale)? Use a real or credibly-approximate number."
                    ),
                )
            )

    # Summary in the buzzword scan + length.
    if resume.summary.strip():
        loc = FindingLocation(section="summary", zone="summary")
        for word in _BUZZWORDS:
            if word in resume.summary.lower():
                findings.append(
                    BestPracticesFinding(
                        rule_code="BUZZWORD",
                        message=f"Summary contains the buzzword '{word}'; replace with concrete positioning.",
                        location=loc,
                        severity=FindingSeverity.WARNING,
                        resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
                        suggested_change=re.sub(
                            re.escape(word), "", resume.summary, flags=re.IGNORECASE
                        ).strip(),
                    )
                )
        if len(resume.summary.split()) > _SUMMARY_WORD_LIMIT:
            findings.append(
                BestPracticesFinding(
                    rule_code="SUMMARY_TOO_LONG",
                    message=(
                        f"Summary is longer than ~{_SUMMARY_WORD_LIMIT} words; tighten to 2-4 lines of "
                        "identity, specialization, scale, and value."
                    ),
                    location=loc,
                    severity=FindingSeverity.REVIEW_NOTE,
                    resolution_kind=ResolutionKind.NEEDS_USER_INPUT,
                    elicitation_prompt=(
                        "Which one specialization and what scale/level best define you? "
                        "We will tighten the summary around that."
                    ),
                )
            )

    # Foundational skills dilute the skills section.
    for skill in resume.additional.technicalSkills:
        if skill.strip().lower() in _FOUNDATIONAL_SKILLS:
            findings.append(
                BestPracticesFinding(
                    rule_code="FOUNDATIONAL_SKILL",
                    message=f"'{skill}' is a foundational tool that weakens the skills section; remove it.",
                    location=FindingLocation(section="skills", zone="skills_list"),
                    severity=FindingSeverity.RECOMMENDATION,
                    resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
                    suggested_change=f"Remove '{skill}' from the skills list.",
                )
            )

    return BestPracticesReport(
        report_provenance=ProvenanceKind.DETERMINISTIC,
        findings=findings,
    )
