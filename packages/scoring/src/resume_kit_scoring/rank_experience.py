"""Job-aware deterministic ranking for experience-entry budget trims."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from resume_kit_schemas import JobDescription, TrimCandidate, TrimKind
from resume_kit_schemas.canonical import Experience, Resume
from resume_kit_terms import AliasIndex, load_effective_alias_index

from .rank_skills import _job_terms, _term_in_text

_QUANTIFIED_RE = re.compile(r"\d")
_SENIOR_TITLE_TERMS = frozenset(
    {
        "architect",
        "director",
        "head",
        "lead",
        "manager",
        "principal",
        "senior",
        "staff",
    }
)
_MID_TITLE_TERMS = frozenset({"developer", "engineer", "owner", "specialist"})
_JUNIOR_TITLE_TERMS = frozenset({"assistant", "associate", "intern", "junior"})
_PRESENT_MONTH = 9999 * 12 + 11


@dataclass(frozen=True)
class _ExperienceScore:
    index: int
    experience: Experience
    score: float
    rationale: str
    continuity_risk: bool


def rank_experience(
    resume: Resume,
    job: JobDescription,
    *,
    count: int,
    alias_index: AliasIndex | None = None,
) -> list[TrimCandidate]:
    """Return low-value experience entries as ordered compress/trim candidates."""

    if count <= 0 or not resume.work:
        return []

    index = alias_index if alias_index is not None else load_effective_alias_index(None)
    job_terms = _job_terms(job)
    scores: list[_ExperienceScore] = []
    for work_index, experience in enumerate(resume.work):
        recency = _recency_score(experience)
        seniority = _seniority_score(experience.title)
        relevance = _relevance_score(experience, job_terms, index)
        quantified = _has_quantified_outcome(experience)
        continuity_risk = _continuity_risk(resume.work, work_index)
        value = recency + seniority + relevance + (18.0 if quantified else 0.0)
        if continuity_risk:
            value += 10.0

        drivers = [
            f"recency={recency:g}",
            f"seniority={seniority:g}",
            f"job relevance={relevance:g}",
            "quantified outcome" if quantified else "no quantified outcome",
        ]
        if continuity_risk:
            drivers.append("continuity risk if removed")

        scores.append(
            _ExperienceScore(
                index=work_index,
                experience=experience,
                score=value,
                rationale=", ".join(drivers),
                continuity_risk=continuity_risk,
            )
        )

    entry_count = max(1, (count + 1) // 2)
    selected = _select_lowest_with_boundary_ties(scores, entry_count)
    deferred_scores = _deferred_scores(selected)
    candidates: list[TrimCandidate] = []
    for item in selected:
        deferred = item.score in deferred_scores
        rationale = item.rationale
        if deferred:
            rationale = f"{rationale}; equal score tie requires human decision"
            candidates.append(
                TrimCandidate(
                    kind=TrimKind.DEFER,
                    dimension="experience_entries",
                    path=f"work[{item.index}]",
                    score=item.score,
                    rationale=rationale,
                    deferred=True,
                )
            )
            continue

        candidates.append(
            TrimCandidate(
                kind=TrimKind.COMPRESS,
                dimension="experience_entries",
                path=f"work[{item.index}]",
                score=item.score,
                rationale=f"{rationale}; compress bullets before considering removal",
            )
        )
        candidates.append(
            TrimCandidate(
                kind=TrimKind.TRIM,
                dimension="experience_entries",
                path=f"work[{item.index}]",
                score=item.score,
                rationale=f"{rationale}; remove only after compression is insufficient",
            )
        )
    return candidates


def _recency_score(experience: Experience) -> float:
    end_month = _date_to_month(experience.endDate)
    if end_month is None:
        end_month = _date_to_month(experience.startDate)
    if end_month is None:
        return 6.0
    if end_month >= _PRESENT_MONTH:
        return 30.0
    end_year = end_month // 12
    if end_year >= 2022:
        return 24.0
    if end_year >= 2018:
        return 16.0
    if end_year >= 2014:
        return 8.0
    return 0.0


def _seniority_score(title: str) -> float:
    tokens = set(_tokens(title))
    if tokens & _SENIOR_TITLE_TERMS:
        return 24.0
    if tokens & _MID_TITLE_TERMS:
        return 12.0
    if tokens & _JUNIOR_TITLE_TERMS:
        return 2.0
    return 6.0


def _relevance_score(
    experience: Experience, job_terms: list[str], alias_index: AliasIndex
) -> float:
    text = _experience_text(experience)
    matches = sum(1 for term in job_terms if _term_in_text(term, text, alias_index))
    return float(min(matches, 3) * 12)


def _has_quantified_outcome(experience: Experience) -> bool:
    return any(
        bool(achievement.metrics) or _QUANTIFIED_RE.search(achievement.text) is not None
        for achievement in experience.achievements
    )


def _continuity_risk(experiences: list[Experience], index: int) -> bool:
    if len(experiences) <= 1:
        return False
    experience = experiences[index]
    if experience.endDate == "present":
        return True
    if index == 0 or index == len(experiences) - 1:
        return False
    return (
        _date_to_month(experience.startDate) is not None
        and _date_to_month(experience.endDate) is not None
    )


def _experience_text(experience: Experience) -> str:
    parts = [experience.organization, experience.title]
    if experience.summary is not None:
        parts.append(experience.summary)
    parts.extend(experience.skills)
    parts.extend(experience.technologies)
    for achievement in experience.achievements:
        parts.append(achievement.text)
        parts.extend(achievement.skills)
        parts.extend(achievement.keywords)
    return " ".join(parts)


def _date_to_month(value: str | None) -> int | None:
    if value is None:
        return None
    if value == "present":
        return _PRESENT_MONTH
    parts = value.split("-")
    if not parts or not parts[0].isdigit():
        return None
    year = int(parts[0])
    month = 1
    if len(parts) >= 2 and parts[1].isdigit():
        month = int(parts[1])
    return year * 12 + (month - 1)


def _tokens(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _select_lowest_with_boundary_ties(
    scores: list[_ExperienceScore], count: int
) -> list[_ExperienceScore]:
    ordered = sorted(scores, key=lambda item: (item.score, item.index))
    if count >= len(ordered):
        return ordered
    boundary_score = ordered[count - 1].score
    return [item for item in ordered if item.score <= boundary_score]


def _deferred_scores(scores: list[_ExperienceScore]) -> set[float]:
    counts = Counter(item.score for item in scores)
    return {score for score, occurrences in counts.items() if occurrences > 1}
