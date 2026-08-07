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
MISSING_QUANTIFICATION, MISSING_QUANTIFICATION_MORE, FOUNDATIONAL_SKILL,
SUMMARY_TOO_LONG. Further rules (duplicate-bullet, equal-detail-per-job,
tense/punctuation consistency) are deferred to follow-up increments and are
intentionally not silently claimed here.

``MISSING_QUANTIFICATION`` is capped and prioritized (RIT-T-0130): rather than
one prompt per unquantified bullet (a low-density "wall"), at most
:data:`_MISSING_QUANT_CAP` per-bullet findings are surfaced, chosen where a
metric adds the most (bullets with an impact/achievement verb first, then resume
order). When more bullets lack a number, a single ``MISSING_QUANTIFICATION_MORE``
advisory names the remaining count so the cap is never a silent truncation.
"""

from __future__ import annotations

import re
from collections.abc import Iterator

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

#: Impact / achievement verbs. A bullet that claims an outcome with one of these
#: but carries no number is the highest-value place to ask for a metric, so such
#: bullets are prioritized when the MISSING_QUANTIFICATION list is capped.
_IMPACT_VERBS = frozenset(
    {
        "improved", "reduced", "increased", "grew", "cut", "accelerated", "drove",
        "delivered", "launched", "scaled", "saved", "boosted", "optimized",
        "expanded", "shipped", "raised", "lowered", "decreased", "doubled",
        "tripled", "eliminated", "generated", "achieved", "won", "led",
    }
)
#: Maximum per-bullet MISSING_QUANTIFICATION findings surfaced per report. Extra
#: unquantified bullets are summarized by a single MISSING_QUANTIFICATION_MORE
#: advisory. Tunable UX knob (see RIT-T-0130).
_MISSING_QUANT_CAP = 3


def _has_impact_verb(bullet: str) -> bool:
    """Return True when *bullet* opens an outcome claim with an impact verb."""
    return any(word in _IMPACT_VERBS for word in re.findall(r"[a-z]+", bullet.lower()))


def _strip_prefix(text: str, prefix: str) -> str:
    """Drop a leading weak *prefix* from *text* and re-capitalize."""
    rest = text[len(prefix):].lstrip(" :,-")
    return rest[:1].upper() + rest[1:] if rest else text


def _strip_words(text: str, words: list[str]) -> str:
    """Remove each of ``words`` (case-insensitive) from ``text`` and tidy spacing."""
    cleaned = text
    for word in words:
        cleaned = re.sub(re.escape(word), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip(" ,.;")
    # Fall back to the original if stripping emptied the text (validator needs a value).
    return cleaned or text


def _weak_opener(text: str) -> str | None:
    low = text.lower()
    for opener in _WEAK_OPENERS:
        if low.startswith(opener):
            return opener
    return None


def _bullets(resume: ResumeDocument) -> Iterator[tuple[str, int, str]]:
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
    # (order_index, has_impact_verb, location) for each unquantified bullet, so
    # the MISSING_QUANTIFICATION list can be prioritized and capped after the
    # scan rather than emitting one prompt per bullet (RIT-T-0130).
    quant_candidates: list[tuple[int, bool, FindingLocation]] = []

    for order_index, (entity_id, idx, bullet) in enumerate(_bullets(resume)):
        loc = FindingLocation(
            section="experience", zone="experience", entity_id=entity_id, bullet_index=idx
        )

        opener = _weak_opener(bullet)
        if opener:
            findings.append(
                BestPracticesFinding(
                    rule_code="WEAK_OPENER",
                    message=(
                        f"Bullet opens with the weak phrase '{opener}';"
                        " lead with a strong action verb."
                    ),
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

        matched_bw = [w for w in _BUZZWORDS if w in bullet.lower()]
        if matched_bw:
            findings.append(
                BestPracticesFinding(
                    rule_code="BUZZWORD",
                    message=(
                        "Buzzword(s) "
                        + ", ".join(f"'{w}'" for w in matched_bw)
                        + " add no evidence; remove or replace with a concrete result."
                    ),
                    location=loc,
                    severity=FindingSeverity.WARNING,
                    resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
                    suggested_change=_strip_words(bullet, matched_bw),
                )
            )

        if not _NUMBER_RE.search(bullet):
            quant_candidates.append((order_index, _has_impact_verb(bullet), loc))

    # Prioritize where a metric adds the most (impact-verb bullets first), then
    # by resume order (recency); surface only the top few, and summarize the rest
    # so the cap is never a silent truncation (RIT-T-0130).
    quant_candidates.sort(key=lambda c: (not c[1], c[0]))
    for _order_index, _has_impact, loc in quant_candidates[:_MISSING_QUANT_CAP]:
        findings.append(
            BestPracticesFinding(
                rule_code="MISSING_QUANTIFICATION",
                message=(
                    "Bullet has no quantified outcome;"
                    " quantify the impact where a real number exists."
                ),
                location=loc,
                severity=FindingSeverity.RECOMMENDATION,
                resolution_kind=ResolutionKind.NEEDS_USER_INPUT,
                elicitation_prompt=(
                    "What changed because of this work, and by roughly how much "
                    "(percent, time, money, scale)? Use a real or credibly-approximate number."
                ),
            )
        )
    remaining = len(quant_candidates) - _MISSING_QUANT_CAP
    if remaining > 0:
        findings.append(
            BestPracticesFinding(
                rule_code="MISSING_QUANTIFICATION_MORE",
                message=(
                    f"{remaining} more experience bullet(s) also lack a quantified"
                    " outcome. Add real numbers where they exist; re-run to surface"
                    " the next batch as targeted prompts."
                ),
                location=FindingLocation(section="experience", zone="experience"),
                severity=FindingSeverity.REVIEW_NOTE,
                resolution_kind=ResolutionKind.NEEDS_USER_INPUT,
                elicitation_prompt=(
                    "Across your remaining bullets, which achievements had a"
                    " measurable result (percent, time, money, scale)? Add a real"
                    " number to each where one exists."
                ),
            )
        )

    # Summary in the buzzword scan + length.
    if resume.summary.strip():
        loc = FindingLocation(section="summary", zone="summary")
        matched_bw = [w for w in _BUZZWORDS if w in resume.summary.lower()]
        if matched_bw:
            findings.append(
                BestPracticesFinding(
                    rule_code="BUZZWORD",
                    message=(
                        "Summary contains buzzword(s) "
                        + ", ".join(f"'{w}'" for w in matched_bw)
                        + "; replace with concrete positioning."
                    ),
                    location=loc,
                    severity=FindingSeverity.WARNING,
                    resolution_kind=ResolutionKind.AUTO_SUGGESTIBLE,
                    suggested_change=_strip_words(resume.summary, matched_bw),
                )
            )
        if len(resume.summary.split()) > _SUMMARY_WORD_LIMIT:
            findings.append(
                BestPracticesFinding(
                    rule_code="SUMMARY_TOO_LONG",
                    message=(
                        f"Summary is longer than ~{_SUMMARY_WORD_LIMIT} words; tighten to 2-4 "
                        "lines of identity, specialization, scale, and value."
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
                    message=(
                        f"'{skill}' is a foundational tool that weakens the skills section;"
                        " remove it."
                    ),
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
