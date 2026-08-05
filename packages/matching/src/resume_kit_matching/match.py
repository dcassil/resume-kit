"""Deterministic, explainable job-match scoring.

Original resume-kit code. Composes existing deterministic primitives —
``resume_kit_matching.keywords`` (keyword coverage + gap analysis) and
``resume_kit_ats.engine.compute_ats_score`` (ATS contribution) — into a single
explainable :class:`~resume_kit_schemas.JobMatchReport`.

Design principles (vision):

* **No keyword-repetition reward.** Keyword coverage is presence-based: a term
  that appears once earns exactly the same credit as one that appears many
  times. Extra credit comes only from *support* (how many required / preferred
  requirements are actually covered) and *placement* (where the evidence
  appears — a dedicated skills section or work experience counts for more than
  an incidental mention).
* **Explainable.** Every dimension records concrete ``evidence``,
  ``missing_evidence``, a ``rationale``, and a ``weight``; the ``overall_score``
  is the weight-normalised sum of the dimension scores, so it is fully
  auditable.
* **Deterministic.** No LLM, no network, no randomness — identical inputs always
  produce byte-identical reports.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

from resume_kit_ats.engine import compute_ats_score
from resume_kit_schemas import (
    JobDescription,
    JobMatchReport,
    KeywordGapAnalysis,
    KeywordZone,
    MatchDimensionScore,
    Requirement,
    RequirementKind,
    ResumeDocument,
)
from resume_kit_scoring import project_scoredoc

from .keywords import analyze_keyword_gaps, calculate_keyword_match

__all__ = ["check_job_match"]

# ---------------------------------------------------------------------------
# Dimension keys + weights (sum == 1.0).
# ---------------------------------------------------------------------------
_KEY_KEYWORD = "keyword_coverage"
_KEY_REQUIRED = "required_coverage"
_KEY_PREFERRED = "preferred_coverage"
_KEY_PLACEMENT = "evidence_placement"
_KEY_ATS = "ats_contribution"

_WEIGHTS: dict[str, float] = {
    _KEY_KEYWORD: 0.20,
    _KEY_REQUIRED: 0.35,
    _KEY_PREFERRED: 0.10,
    _KEY_PLACEMENT: 0.15,
    _KEY_ATS: 0.20,
}


def _keyword_in_text(keyword: str, text_lower: str) -> bool:
    """Whole-word, presence-only match (repetition is irrelevant)."""
    escaped = re.escape(keyword.strip().lower())
    if not escaped:
        return False
    return bool(re.search(rf"(?<!\w){escaped}(?!\w)", text_lower))


def _requirement_terms(req: Requirement) -> list[str]:
    """Return the searchable terms for a requirement (keywords, else text)."""
    if req.keywords:
        return [k for k in req.keywords if k.strip()]
    return [req.text] if req.text.strip() else []


def _requirement_is_covered(req: Requirement, text_lower: str) -> bool:
    """A requirement is covered if any of its terms is present in the resume."""
    return any(_keyword_in_text(term, text_lower) for term in _requirement_terms(req))


#: Zones counted as high-value for placement. Sourcing from ScoreDoc means a
#: skill in a *categorized* custom section (e.g. "Cloud Skills") is treated as a
#: canonical skill, not incidental body text — the RIT-T-0107 fix. Placement
#: ignores dates, so a fixed reference date keeps the projection deterministic.
_HIGH_VALUE_ZONES = frozenset({KeywordZone.SKILLS_LIST, KeywordZone.EXPERIENCE})
_PLACEMENT_REF_DATE = date(2000, 1, 1)


def _high_value_text(resume: ResumeDocument) -> str:
    """Concatenated text from high-value placement zones (skills + experience).

    Placement credit derives ONLY from presence in these structured, high-value
    locations — never from how many times a term is repeated anywhere. The zones
    are read from the canonical ``ScoreDoc`` projection, so categorized skills in
    custom sections that map to the skills/experience zones count here too.
    """
    scoredoc = project_scoredoc(resume, reference_date=_PLACEMENT_REF_DATE)
    parts = [
        section.text
        for section in scoredoc.sections
        if section.zone in _HIGH_VALUE_ZONES and section.text
    ]
    return " ".join(parts).lower()


def _coverage_dimension(
    key: str,
    name: str,
    requirements: list[Requirement],
    resume_text_lower: str,
) -> MatchDimensionScore:
    """Score how many requirements of one kind are supported by the resume."""
    if not requirements:
        return MatchDimensionScore(
            key=key,
            name=name,
            score=0.0,
            weight=_WEIGHTS[key],
            evidence=[],
            missing_evidence=[],
            rationale=f"No {name.lower()} were listed in the job description.",
        )

    covered: list[str] = []
    missing: list[str] = []
    for req in requirements:
        label = req.text or ", ".join(req.keywords)
        if _requirement_is_covered(req, resume_text_lower):
            covered.append(label)
        else:
            missing.append(label)

    score = len(covered) / len(requirements) * 100
    return MatchDimensionScore(
        key=key,
        name=name,
        score=round(score, 1),
        weight=_WEIGHTS[key],
        evidence=[f"Covered: {c}" for c in covered],
        missing_evidence=[f"Not addressed: {m}" for m in missing],
        rationale=(
            f"{len(covered)} of {len(requirements)} {name.lower()} are supported "
            f"by resume content."
        ),
    )


def _keyword_dimension(
    resume: ResumeDocument,
    job: JobDescription,
    gap: KeywordGapAnalysis,
) -> MatchDimensionScore:
    """Presence-based keyword coverage — immune to keyword repetition.

    Delegates to ``calculate_keyword_match``, which counts each unique JD
    keyword at most once, so repeating a term never raises this score.
    """
    score = calculate_keyword_match(resume, job)
    evidence: list[str] = []
    if job.keywords:
        present = [k for k in job.keywords if k not in gap.missing_keywords]
        if present:
            evidence.append("Present JD keywords: " + ", ".join(sorted(present)))
    return MatchDimensionScore(
        key=_KEY_KEYWORD,
        name="Keyword coverage",
        score=round(score, 1),
        weight=_WEIGHTS[_KEY_KEYWORD],
        evidence=evidence,
        missing_evidence=(
            ["Missing JD keywords: " + ", ".join(sorted(gap.missing_keywords))]
            if gap.missing_keywords
            else []
        ),
        rationale=(
            "Presence-based coverage of unique JD keywords; a keyword counts "
            "once regardless of how often it appears."
        ),
    )


def _placement_dimension(
    resume: ResumeDocument,
    job: JobDescription,
) -> MatchDimensionScore:
    """Reward evidence located in high-value zones (skills / experience).

    Placement is presence-in-a-good-location, again independent of repetition:
    a term present in the skills section scores identically whether it appears
    once or many times there.
    """
    all_requirements = list(job.requirements) + list(job.qualifications)
    terms: list[str] = []
    seen: set[str] = set()
    for req in all_requirements:
        for term in _requirement_terms(req):
            norm = term.strip().lower()
            if norm and norm not in seen:
                seen.add(norm)
                terms.append(term)
    for kw in job.keywords:
        norm = kw.strip().lower()
        if norm and norm not in seen:
            seen.add(norm)
            terms.append(kw)

    if not terms:
        return MatchDimensionScore(
            key=_KEY_PLACEMENT,
            name="Evidence placement",
            score=0.0,
            weight=_WEIGHTS[_KEY_PLACEMENT],
            evidence=[],
            missing_evidence=[],
            rationale="No requirement or keyword terms to place.",
        )

    high_value = _high_value_text(resume)
    well_placed = [t for t in terms if _keyword_in_text(t, high_value)]
    poorly_placed = [t for t in terms if t not in well_placed]

    score = len(well_placed) / len(terms) * 100
    return MatchDimensionScore(
        key=_KEY_PLACEMENT,
        name="Evidence placement",
        score=round(score, 1),
        weight=_WEIGHTS[_KEY_PLACEMENT],
        evidence=(
            ["In skills/experience: " + ", ".join(sorted(well_placed))]
            if well_placed
            else []
        ),
        missing_evidence=(
            ["Not in skills/experience: " + ", ".join(sorted(poorly_placed))]
            if poorly_placed
            else []
        ),
        rationale=(
            f"{len(well_placed)} of {len(terms)} JD terms appear in high-value "
            f"zones (skills section or work experience)."
        ),
    )


def _ats_dimension(ats_overall: float) -> MatchDimensionScore:
    """Fold the composed ATS overall score in as one weighted dimension."""
    return MatchDimensionScore(
        key=_KEY_ATS,
        name="ATS contribution",
        score=round(ats_overall, 1),
        weight=_WEIGHTS[_KEY_ATS],
        evidence=[f"ATS overall score: {round(ats_overall, 1)}"],
        missing_evidence=[],
        rationale=(
            "Composed from the deterministic ATS engine (keyword match, skills "
            "coverage, section completeness)."
        ),
    )


def check_job_match(
    resume: ResumeDocument,
    job: JobDescription,
) -> JobMatchReport:
    """Return an explainable, deterministic :class:`JobMatchReport`.

    Args:
        resume: The canonical structured resume to score.
        job: The structured job description to score against.

    Returns:
        A :class:`JobMatchReport` whose ``overall_score`` is the
        weight-normalised composite of five explainable dimensions: keyword
        coverage, required-requirement coverage, preferred-requirement
        coverage, evidence placement, and ATS contribution.
    """
    resume_text_lower = _resume_full_text(resume)

    # --- Keyword gap + ATS (composed primitives; resume is its own master). ---
    gap = analyze_keyword_gaps(job, resume, resume)
    keyword_match_pct = calculate_keyword_match(resume, job)
    ats = compute_ats_score(
        resume,
        job,
        keyword_match_percentage=keyword_match_pct,
        missing_keywords=gap.non_injectable_keywords,
        injectable_keywords=gap.injectable_keywords,
    )

    # --- Dimensions ---
    required = [
        r for r in job.requirements if r.kind == RequirementKind.REQUIRED
    ] + [q for q in job.qualifications if q.kind == RequirementKind.REQUIRED]
    preferred = [
        r for r in job.requirements if r.kind == RequirementKind.PREFERRED
    ] + [q for q in job.qualifications if q.kind == RequirementKind.PREFERRED]

    dimensions = [
        _keyword_dimension(resume, job, gap),
        _coverage_dimension(
            _KEY_REQUIRED, "Required requirements", required, resume_text_lower
        ),
        _coverage_dimension(
            _KEY_PREFERRED, "Preferred requirements", preferred, resume_text_lower
        ),
        _placement_dimension(resume, job),
        _ats_dimension(ats.overall_score),
    ]

    total_weight = sum(d.weight for d in dimensions)
    if total_weight > 0:
        overall = sum(d.score * d.weight for d in dimensions) / total_weight
    else:
        overall = 0.0
    overall = max(0.0, min(100.0, overall))

    # --- Recommendations (deterministic, ordered). ---
    recommendations = _build_recommendations(dimensions, gap, ats.recommendations)

    # --- Confidence: how much signal the JD actually provided. ---
    confidence = _confidence(job)

    return JobMatchReport(
        overall_score=round(overall, 1),
        dimensions=dimensions,
        ats_score=ats,
        keyword_gap=gap,
        confidence=round(confidence, 2),
        recommendations=recommendations,
    )


def _resume_full_text(resume: ResumeDocument) -> str:
    """Flatten all resume string content into one lowercased block."""
    parts: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, dict):
            for value in obj.values():
                _walk(value)

    _walk(resume.model_dump())
    return " ".join(parts).lower()


def _build_recommendations(
    dimensions: list[MatchDimensionScore],
    gap: KeywordGapAnalysis,
    ats_recs: list[str],
) -> list[str]:
    """Assemble ordered, deterministic recommendations from the dimensions."""
    recs: list[str] = []
    by_key = {d.key: d for d in dimensions}

    required_dim = by_key[_KEY_REQUIRED]
    if required_dim.missing_evidence:
        recs.append(
            "Address unmet required requirements: "
            + "; ".join(m.removeprefix("Not addressed: ") for m in
                        required_dim.missing_evidence)
            + "."
        )

    preferred_dim = by_key[_KEY_PREFERRED]
    if preferred_dim.missing_evidence:
        recs.append(
            "Consider adding preferred qualifications: "
            + "; ".join(m.removeprefix("Not addressed: ") for m in
                        preferred_dim.missing_evidence)
            + "."
        )

    if gap.injectable_keywords:
        recs.append(
            "These JD keywords are in your master resume but missing here — "
            "add them: " + ", ".join(sorted(gap.injectable_keywords)) + "."
        )

    placement_dim = by_key[_KEY_PLACEMENT]
    if placement_dim.missing_evidence:
        recs.append(
            "Move key terms into your skills section or work-experience bullets "
            "for stronger placement credit."
        )

    for rec in ats_recs:
        if rec not in recs:
            recs.append(rec)

    return recs


def _confidence(job: JobDescription) -> float:
    """Confidence in the assessment based on how structured the JD is.

    A JD with explicit, keyword-annotated requirements yields a high-confidence
    match; a bare keyword list or empty JD yields lower confidence.
    """
    all_reqs = list(job.requirements) + list(job.qualifications)
    if not all_reqs and not job.keywords:
        return 0.0
    if not all_reqs:
        return 0.5
    annotated = sum(1 for r in all_reqs if r.keywords)
    ratio = annotated / len(all_reqs)
    # 0.6 floor for having structured requirements, up to 1.0 when all annotated.
    return 0.6 + 0.4 * ratio
