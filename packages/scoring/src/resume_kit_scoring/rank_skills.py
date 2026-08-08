"""Job-aware deterministic ranking for skills-section budget trims."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from resume_kit_schemas import (
    JobDescription,
    TrimCandidate,
    TrimKind,
    sanitize_keywords,
)
from resume_kit_schemas.canonical import Resume, SkillGroup
from resume_kit_terms import AliasIndex, load_effective_alias_index, match, surface_form

_FOUNDATIONAL_SKILLS = frozenset(
    {
        "email",
        "internet",
        "microsoft office",
        "microsoft word",
        "typing",
        "web browsing",
    }
)
_SOFT_SKILLS = frozenset(
    {
        "adaptability",
        "communication",
        "collaboration",
        "creative thinking",
        "detail oriented",
        "leadership",
        "problem solving",
        "teamwork",
        "time management",
    }
)
_UMBRELLA_SKILLS = frozenset(
    {
        "agile",
        "backend",
        "cloud",
        "data",
        "databases",
        "devops",
        "frontend",
        "full stack",
        "management",
        "programming",
        "software development",
        "web development",
    }
)
_SPECIFIC_TECH_HINTS = frozenset(
    {
        "aws",
        "azure",
        "django",
        "docker",
        "fastapi",
        "flask",
        "gcp",
        "graphql",
        "java",
        "javascript",
        "kubernetes",
        "node",
        "postgresql",
        "python",
        "react",
        "redis",
        "rust",
        "sql",
        "terraform",
        "typescript",
    }
)


@dataclass(frozen=True)
class _SkillScore:
    index: int
    skill: SkillGroup
    score: float
    rationale: str


def rank_skills(
    resume: Resume,
    job: JobDescription,
    *,
    count: int,
    alias_index: AliasIndex | None = None,
) -> list[TrimCandidate]:
    """Return the lowest-value skill groups as ranked trim candidates.

    The function proposes ordering only; it never mutates ``resume``.
    """

    if count <= 0 or not resume.skills:
        return []

    index = alias_index if alias_index is not None else load_effective_alias_index(None)
    job_terms = _job_terms(job)
    usage_text = _resume_usage_text(resume)
    seen_terms: set[str] = set()
    scores: list[_SkillScore] = []

    for skill_index, skill in enumerate(resume.skills):
        labels = _skill_labels(skill)
        duplicate = _has_prior_duplicate(labels, seen_terms)
        seen_terms.update(
            _surface_label(label) for label in labels if _surface_label(label)
        )
        job_matched = _any_label_matches_job(labels, job_terms, index)
        used = _any_label_in_text(labels, usage_text, index)
        specific = any(_is_specific_technical(label) for label in labels)
        foundational = any(_is_foundational(label) for label in labels)
        soft = any(_is_soft(label) for label in labels)
        umbrella = any(_is_umbrella(label) for label in labels)

        value = 50.0
        drivers: list[str] = []
        if job_matched and used:
            value += 40.0
            drivers.append("job-matched and evidenced in experience/summary")
        elif job_matched:
            value += 24.0
            drivers.append("job-matched")
        elif used:
            value += 16.0
            drivers.append("evidenced in experience/summary")
        else:
            drivers.append("not evidenced outside skills")

        if specific:
            value += 14.0
            drivers.append("specific technical skill")
        if umbrella:
            value -= 8.0
            drivers.append("umbrella skill")
        if soft:
            value -= 10.0
            drivers.append("soft/generic skill")
        if foundational:
            value -= 20.0
            drivers.append("foundational tool")
        if duplicate:
            value -= 40.0
            drivers.append("duplicate skill")

        scores.append(
            _SkillScore(
                index=skill_index,
                skill=skill,
                score=value,
                rationale=", ".join(drivers),
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
                dimension="skills",
                path=f"skills[{item.index}]",
                score=item.score,
                rationale=rationale,
                deferred=deferred,
            )
        )
    return candidates


def _job_terms(job: JobDescription) -> list[str]:
    raw_terms: list[str] = []
    raw_terms.extend(job.keywords)
    for requirement in job.requirements:
        raw_terms.extend(requirement.keywords)
        raw_terms.append(requirement.text)
    for qualification in job.qualifications:
        raw_terms.extend(qualification.keywords)
        raw_terms.append(qualification.text)
    terms = sanitize_keywords(raw_terms)
    deduped: dict[str, str] = {}
    for term in terms:
        surface = surface_form(term)
        if surface:
            deduped.setdefault(surface, term)
    return list(deduped.values())


def _resume_usage_text(resume: Resume) -> str:
    parts: list[str] = []
    if resume.basics.summary is not None:
        parts.append(resume.basics.summary)
    for experience in resume.work:
        parts.append(experience.title)
        if experience.summary is not None:
            parts.append(experience.summary)
        parts.extend(experience.skills)
        parts.extend(experience.technologies)
        parts.extend(achievement.text for achievement in experience.achievements)
        for achievement in experience.achievements:
            parts.extend(achievement.skills)
            parts.extend(achievement.keywords)
    return " ".join(parts)


def _skill_labels(skill: SkillGroup) -> list[str]:
    return [skill.name, *skill.keywords]


def _has_prior_duplicate(labels: list[str], seen_terms: set[str]) -> bool:
    return any(_surface_label(label) in seen_terms for label in labels)


def _surface_label(label: str) -> str:
    return surface_form(label)


def _any_label_matches_job(
    labels: list[str], job_terms: list[str], alias_index: AliasIndex
) -> bool:
    return any(
        _terms_match(label, job_term, alias_index)
        for label in labels
        for job_term in job_terms
    )


def _any_label_in_text(labels: list[str], text: str, alias_index: AliasIndex) -> bool:
    return any(_term_in_text(label, text, alias_index) for label in labels)


def _terms_match(a: str, b: str, alias_index: AliasIndex) -> bool:
    return match(a, b, alias_index=alias_index, allow_stem=False).matched


def _term_in_text(term: str, text: str, alias_index: AliasIndex) -> bool:
    term_surface = surface_form(term)
    if not term_surface:
        return False

    tokens = surface_form(text).split()
    term_len = len(term_surface.split())
    if term_len == 0 or len(tokens) < term_len:
        return False

    for start in range(0, len(tokens) - term_len + 1):
        window = " ".join(tokens[start : start + term_len])
        if _terms_match(term, window, alias_index):
            return True
    return False


def _is_specific_technical(label: str) -> bool:
    surface = surface_form(label)
    if surface in _SPECIFIC_TECH_HINTS:
        return True
    if any(token in _SPECIFIC_TECH_HINTS for token in surface.split()):
        return True
    return any(char.isdigit() for char in label)


def _is_foundational(label: str) -> bool:
    return surface_form(label) in _FOUNDATIONAL_SKILLS


def _is_soft(label: str) -> bool:
    return surface_form(label) in _SOFT_SKILLS


def _is_umbrella(label: str) -> bool:
    return surface_form(label) in _UMBRELLA_SKILLS


def _select_lowest_with_boundary_ties(
    scores: list[_SkillScore], count: int
) -> list[_SkillScore]:
    ordered = sorted(scores, key=lambda item: (item.score, item.index))
    if count >= len(ordered):
        return ordered
    boundary_score = ordered[count - 1].score
    return [item for item in ordered if item.score <= boundary_score]


def _deferred_scores(scores: list[_SkillScore]) -> set[float]:
    counts = Counter(item.score for item in scores)
    return {score for score, occurrences in counts.items() if occurrences > 1}
