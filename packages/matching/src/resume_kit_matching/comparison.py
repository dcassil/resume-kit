"""Deterministic version comparison between two resume variants.

Original resume-kit code. Compares a *base* and *candidate* resume against one
job by reusing the existing explainable scorer
(:func:`resume_kit_matching.match.check_job_match`) — it performs no scoring of
its own — and emits the canonical
:class:`~resume_kit_schemas.ResumeComparisonResult` with per-metric
:class:`~resume_kit_schemas.ScoreDelta` entries.

Metrics compared (before = base, after = candidate):

* ``match.overall`` — overall explainable job-match score.
* ``ats.overall`` — composed ATS overall score.
* ``keyword.match_pct`` — ATS keyword-match sub-score (%).

All comparisons are deterministic: identical inputs always produce identical
results.
"""

from __future__ import annotations

from resume_kit_schemas import (
    JobDescription,
    JobMatchReport,
    ResumeComparisonResult,
    ResumeDocument,
    ScoreDelta,
)

from .match import check_job_match

__all__ = ["compare_versions"]

_METRIC_MATCH = "match.overall"
_METRIC_ATS = "ats.overall"
_METRIC_KEYWORD = "keyword.match_pct"


def _ats_overall(report: JobMatchReport) -> float:
    """Return the composed ATS overall score, or 0.0 when unavailable."""
    return report.ats_score.overall_score if report.ats_score is not None else 0.0


def _keyword_match_pct(report: JobMatchReport) -> float:
    """Return the ATS keyword-match sub-score (%), or 0.0 when unavailable."""
    if report.ats_score is None:
        return 0.0
    return report.ats_score.sub_scores.keyword_match


def _delta(metric: str, before: float, after: float) -> ScoreDelta:
    """Build a rounded :class:`ScoreDelta` for one metric."""
    before_r = round(before, 1)
    after_r = round(after, 1)
    return ScoreDelta(
        metric=metric,
        before=before_r,
        after=after_r,
        delta=round(after_r - before_r, 1),
    )


def _summarize(deltas: list[ScoreDelta]) -> str:
    """Build a short, deterministic improvement/regression summary."""
    improved = [d.metric for d in deltas if d.delta > 0]
    regressed = [d.metric for d in deltas if d.delta < 0]
    unchanged = [d.metric for d in deltas if d.delta == 0]

    overall = next((d for d in deltas if d.metric == _METRIC_MATCH), None)
    if overall is None:
        headline = "Compared candidate against base."
    elif overall.delta > 0:
        headline = (
            f"Candidate improves overall match by {overall.delta:.1f} points "
            f"({overall.before:.1f} -> {overall.after:.1f})."
        )
    elif overall.delta < 0:
        headline = (
            f"Candidate regresses overall match by {abs(overall.delta):.1f} "
            f"points ({overall.before:.1f} -> {overall.after:.1f})."
        )
    else:
        headline = (
            f"Candidate leaves overall match unchanged at {overall.after:.1f}."
        )

    parts = [headline]
    if improved:
        parts.append("Improved: " + ", ".join(improved) + ".")
    if regressed:
        parts.append("Regressed: " + ", ".join(regressed) + ".")
    if unchanged:
        parts.append("Unchanged: " + ", ".join(unchanged) + ".")
    return " ".join(parts)


def compare_versions(
    base: ResumeDocument,
    candidate: ResumeDocument,
    job: JobDescription,
    base_label: str = "base",
    candidate_label: str = "candidate",
) -> ResumeComparisonResult:
    """Compare two resume versions against *job* and report score deltas.

    Args:
        base: The baseline resume version (the "before").
        candidate: The candidate resume version (the "after").
        job: The structured job description to score both versions against.
        base_label: Human-readable label for the baseline version.
        candidate_label: Human-readable label for the candidate version.

    Returns:
        A :class:`ResumeComparisonResult` with per-metric
        :class:`ScoreDelta` entries for overall job match, ATS overall, and
        keyword match %, plus a short summary of improvements/regressions.
    """
    base_report = check_job_match(base, job)
    candidate_report = check_job_match(candidate, job)

    deltas = [
        _delta(
            _METRIC_MATCH,
            base_report.overall_score,
            candidate_report.overall_score,
        ),
        _delta(
            _METRIC_ATS,
            _ats_overall(base_report),
            _ats_overall(candidate_report),
        ),
        _delta(
            _METRIC_KEYWORD,
            _keyword_match_pct(base_report),
            _keyword_match_pct(candidate_report),
        ),
    ]

    return ResumeComparisonResult(
        variant_labels=[base_label, candidate_label],
        deltas=deltas,
        summary=_summarize(deltas),
    )
