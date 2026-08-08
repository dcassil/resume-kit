"""Job-aware deterministic ranking for achievement-bullet budget trims."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from resume_kit_schemas import JobDescription, ResumeDocument, TrimCandidate, TrimKind
from resume_kit_terms import AliasIndex, load_effective_alias_index, surface_form

from .rank_skills import _job_terms, _term_in_text

_NUMBER_RE = re.compile(r"\d")
_TOOL_ONLY_RE = re.compile(
    r"^\s*(?:used|utilized|worked with|tools?:|technologies?:|tech stack:)\b",
    re.IGNORECASE,
)
_WEAK_OPENER_RE = re.compile(
    r"^\s*(?:responsible for|duties included|helped with|assisted with|worked on)\b",
    re.IGNORECASE,
)
_IMPACT_TERMS = frozenset(
    {
        "accelerated",
        "achieved",
        "boosted",
        "cut",
        "decreased",
        "delivered",
        "drove",
        "eliminated",
        "generated",
        "grew",
        "improved",
        "increased",
        "launched",
        "lowered",
        "optimized",
        "reduced",
        "saved",
        "scaled",
        "shipped",
    }
)
_SCOPE_TERMS = frozenset(
    {
        "architecture",
        "architected",
        "cross-functional",
        "distributed",
        "enterprise",
        "led",
        "mentored",
        "migration",
        "multi-region",
        "platform",
        "roadmap",
        "stakeholders",
        "strategy",
        "team",
    }
)


@dataclass(frozen=True)
class _BulletScore:
    work_index: int
    achievement_index: int
    achievement: str
    score: float
    rationale: str


def rank_bullets(
    resume: ResumeDocument,
    job: JobDescription,
    *,
    count: int,
    alias_index: AliasIndex | None = None,
) -> list[TrimCandidate]:
    """Return the lowest-value achievement bullets as trim candidates."""

    if count <= 0:
        return []

    index = alias_index if alias_index is not None else load_effective_alias_index(None)
    job_terms = _job_terms(job)
    all_bullets = [
        bullet
        for experience in resume.workExperience
        for bullet in experience.description
    ]
    duplicate_surfaces = {
        surface
        for surface, occurrences in Counter(
            surface_form(bullet) for bullet in all_bullets
        ).items()
        if surface and occurrences > 1
    }

    scores: list[_BulletScore] = []
    for work_index, experience in enumerate(resume.workExperience):
        for achievement_index, achievement in enumerate(experience.description):
            score, rationale = _score_bullet(
                achievement,
                job_terms,
                index,
                surface_form(achievement) in duplicate_surfaces,
            )
            scores.append(
                _BulletScore(
                    work_index=work_index,
                    achievement_index=achievement_index,
                    achievement=achievement,
                    score=score,
                    rationale=rationale,
                )
            )

    selected = _select_lowest_with_boundary_ties(scores, count)
    deferred_scores = _deferred_scores(selected)
    candidates: list[TrimCandidate] = []
    for item in selected:
        deferred = item.score in deferred_scores
        rationale = item.rationale
        if deferred:
            rationale = f"{rationale}; equal score tie requires human decision"
        candidates.append(
            TrimCandidate(
                kind=TrimKind.DEFER if deferred else TrimKind.TRIM,
                dimension="bullets_per_role",
                path=(
                    f"workExperience[{item.work_index}]"
                    f".description[{item.achievement_index}]"
                ),
                score=item.score,
                rationale=rationale,
                deferred=deferred,
            )
        )
    return candidates


def _score_bullet(
    achievement: str,
    job_terms: list[str],
    alias_index: AliasIndex,
    duplicate: bool,
) -> tuple[float, str]:
    text = achievement
    tokens = _tokens(text)
    quantified = _NUMBER_RE.search(text) is not None
    impact = bool(set(tokens) & _IMPACT_TERMS)
    scope = bool(set(tokens) & _SCOPE_TERMS)
    relevance_matches = sum(
        1 for term in job_terms if _term_in_text(term, text, alias_index)
    )
    relevant = relevance_matches > 0
    tool_only = _is_tool_only(text)
    weak = _WEAK_OPENER_RE.search(text) is not None

    value = 50.0
    drivers: list[str] = []
    if quantified:
        value += 24.0
        drivers.append("quantified impact")
    else:
        drivers.append("unquantified")
    if impact:
        value += 12.0
        drivers.append("impact verb")
    if scope:
        value += 16.0
        drivers.append("scope/leadership/architecture signal")
    if relevant:
        relevance_score = min(relevance_matches, 2) * 10.0
        value += relevance_score
        drivers.append(f"job relevance={relevance_score:g}")
    else:
        value -= 12.0
        drivers.append("low job relevance")
    if tool_only:
        value -= 24.0
        drivers.append("tool-only phrasing")
    if duplicate:
        value -= 18.0
        drivers.append("redundant bullet")
    if weak:
        value -= 8.0
        drivers.append("weak opener")

    return value, ", ".join(drivers)


def _is_tool_only(text: str) -> bool:
    if _TOOL_ONLY_RE.search(text) is not None:
        return True
    words = _tokens(text)
    return len(words) <= 8 and "," in text and not (set(words) & _IMPACT_TERMS)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)?", text.lower())


def _select_lowest_with_boundary_ties(
    scores: list[_BulletScore], count: int
) -> list[_BulletScore]:
    ordered = sorted(
        scores,
        key=lambda item: (item.score, item.work_index, item.achievement_index),
    )
    if count >= len(ordered):
        return ordered
    boundary_score = ordered[count - 1].score
    return [item for item in ordered if item.score <= boundary_score]


def _deferred_scores(scores: list[_BulletScore]) -> set[float]:
    counts = Counter(item.score for item in scores)
    return {score for score, occurrences in counts.items() if occurrences > 1}
