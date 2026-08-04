"""Deterministic resume-variant selection against a single job.

Original resume-kit code. Ranks N resume variants against one job description
by reusing the existing explainable scorer
(:func:`resume_kit_matching.match.check_job_match`) — it performs no scoring of
its own — and emits the canonical
:class:`~resume_kit_schemas.ResumeSelectionResult`.

Design principles:

* **Reuse, don't reimplement.** Each variant is scored via ``check_job_match``;
  this module only orders the resulting reports and explains the winner.
* **Deterministic.** Ranking is by ``overall_score`` descending with a stable
  tie-break on the variant's original input position, so identical inputs always
  produce byte-identical results.
* **Caller-provided identity.** Variants are identified by caller-supplied
  labels, or — absent labels — by their stable list position. No persistence
  ids are invented.
"""

from __future__ import annotations

from collections.abc import Sequence

from resume_kit_schemas import (
    JobDescription,
    ResumeDocument,
    ResumeSelectionResult,
    ResumeVariantScore,
)

from .match import check_job_match

__all__ = ["select_best"]


def _label_for(index: int, labels: Sequence[str] | None) -> str:
    """Return the caller label for *index*, or a stable positional fallback."""
    if labels is not None and index < len(labels):
        label = labels[index].strip()
        if label:
            return label
    return f"variant-{index}"


def _explain(
    ranked: list[ResumeVariantScore],
) -> str:
    """Build a human-readable explanation of why the top variant won."""
    if not ranked:
        return "No resume variants were provided to select from."

    best = ranked[0]
    if len(ranked) == 1:
        return (
            f"Only one variant ({best.label}) was provided; it scored "
            f"{best.overall_score:.1f}/100."
        )

    runner_up = ranked[1]
    margin = best.overall_score - runner_up.overall_score
    if margin > 0:
        lead = (
            f"outscoring the next best ({runner_up.label}, "
            f"{runner_up.overall_score:.1f}) by {margin:.1f} points"
        )
    else:
        lead = (
            f"tied with {runner_up.label} on score "
            f"({runner_up.overall_score:.1f}); it won on input order"
        )
    return (
        f"Selected {best.label} with the highest overall match score of "
        f"{best.overall_score:.1f}/100, {lead}."
    )


def select_best(
    resumes: Sequence[ResumeDocument],
    job: JobDescription,
    labels: Sequence[str] | None = None,
) -> ResumeSelectionResult:
    """Rank *resumes* against *job* and select the best variant.

    Args:
        resumes: The resume variants to compare, in caller order. The variant's
            position in this sequence is its stable identity when no matching
            label is provided.
        job: The structured job description to score every variant against.
        labels: Optional caller-provided labels aligned by index with
            *resumes*. Missing or blank labels fall back to a positional
            ``variant-<index>`` identifier.

    Returns:
        A :class:`ResumeSelectionResult` with variants ordered best-first by
        ``overall_score`` (stable tie-break by original input position), the
        selected best variant id, and a human-readable explanation.
    """
    scored: list[tuple[int, ResumeVariantScore]] = []
    for index, resume in enumerate(resumes):
        label = _label_for(index, labels)
        report = check_job_match(resume, job)
        scored.append(
            (
                index,
                ResumeVariantScore(variant_id=label, label=label, report=report),
            )
        )

    # Deterministic: score descending, ties broken by original input position.
    scored.sort(key=lambda pair: (-pair[1].overall_score, pair[0]))
    ranked = [variant for _, variant in scored]

    selected_id = ranked[0].variant_id if ranked else None
    return ResumeSelectionResult(
        ranked=ranked,
        selected_variant_id=selected_id,
        explanation=_explain(ranked),
    )
