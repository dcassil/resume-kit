"""Canonical analysis / scoring domain models.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream paths:
#   apps/backend/app/schemas/refinement.py
#     (RefinementConfig, KeywordGapAnalysis, AlignmentViolation, AlignmentReport,
#      RefinementStats, RefinementResult)
#   apps/backend/app/schemas/models.py:577-616 (ATSSubScores, ATSScore)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Ported the refinement + ATS schema-only primitives, re-namespaced
#   under resume_kit_schemas, dropping the API-facing ``RefinementResult.to_stats``
#   response helper. Field shapes, bounds (ge/le), and defaults preserved. Added
#   the New ``AnalysisReport`` umbrella that composes these into one domain
#   contract with structured warnings.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Warning


class ATSSubScores(BaseModel):
    """Individual component scores that make up the ATS overall score."""

    keyword_match: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Keyword match % (0-100)."
    )
    skills_coverage: float = Field(
        default=0.0, ge=0.0, le=100.0, description="JD skills matched in resume (0-100)."
    )
    section_completeness: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Key resume sections present (0-100)."
    )


class ATSScore(BaseModel):
    """ATS-style score breakdown for a resume against a job description."""

    overall_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Weighted composite ATS score (0-100)."
    )
    sub_scores: ATSSubScores = Field(default_factory=ATSSubScores)
    missing_keywords: list[str] = Field(default_factory=list)
    injectable_keywords: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)


class KeywordGapAnalysis(BaseModel):
    """Result of keyword gap analysis. Ported from upstream refinement schema."""

    missing_keywords: list[str] = Field(default_factory=list)
    injectable_keywords: list[str] = Field(
        default_factory=list,
        description="Missing keywords that exist in the master resume (safe to add).",
    )
    non_injectable_keywords: list[str] = Field(
        default_factory=list,
        description="Missing keywords not in the master resume (cannot add truthfully).",
    )
    current_match_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    potential_match_percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class AlignmentViolation(BaseModel):
    """A single alignment violation between tailored and master resume."""

    field_path: str = Field(description="Path to the violated field in resume data.")
    violation_type: str = Field(
        description=(
            "Type: fabricated_skill, skill_variant, fabricated_cert, "
            "fabricated_company, invented_content."
        )
    )
    value: str = Field(description="The violating value.")
    severity: str = Field(default="warning", description="critical, warning, or info.")


class AlignmentReport(BaseModel):
    """Master-resume alignment validation result. Ported from upstream."""

    is_aligned: bool = Field(default=True)
    violations: list[AlignmentViolation] = Field(default_factory=list)
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)


class RefinementConfig(BaseModel):
    """Configuration for refinement passes. Ported from upstream."""

    enable_keyword_injection: bool = True
    enable_ai_phrase_removal: bool = True
    enable_master_alignment_check: bool = True
    max_refinement_passes: int = Field(default=2, ge=1, le=5)


class RefinementStats(BaseModel):
    """Statistics from the multi-pass refinement process. Ported from upstream."""

    passes_completed: int = Field(default=0, ge=0)
    keywords_injected: int = Field(default=0, ge=0)
    ai_phrases_removed: list[str] = Field(default_factory=list)
    alignment_violations_fixed: int = Field(default=0, ge=0)
    initial_match_percentage: float = Field(default=0.0, ge=0.0, le=100.0)
    final_match_percentage: float = Field(default=0.0, ge=0.0, le=100.0)


class AnalysisReport(BaseModel):
    """Umbrella domain report for a resume-vs-job analysis.

    New resume-kit contract that composes the ported ATS, keyword-gap,
    alignment, and refinement primitives into a single self-contained domain
    artifact, plus structured warnings. No transport/persistence fields.
    """

    ats_score: ATSScore | None = None
    keyword_gap: KeywordGapAnalysis | None = None
    alignment: AlignmentReport | None = None
    refinement_stats: RefinementStats | None = None
    warnings: list[Warning] = Field(default_factory=list)


class MatchDimensionScore(BaseModel):
    """One explainable scoring dimension of a job-match report.

    The unit that makes scoring explainable: it names a dimension, records its
    weighted score, and carries the concrete evidence that supports the score
    (presence + support + placement) plus the evidence that is missing. This is
    what lets scoring reflect real support for a requirement rather than mere
    keyword repetition.
    """

    key: str = Field(description="Stable machine key for the dimension (e.g. 'skills').")
    name: str = Field(description="Human-readable dimension name.")
    score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Dimension score (0-100)."
    )
    weight: float = Field(
        default=1.0,
        ge=0.0,
        le=1.0,
        description="Relative weight of this dimension in the overall score (0-1).",
    )
    evidence: list[str] = Field(
        default_factory=list,
        description=(
            "Concrete supporting evidence, including where it appears "
            "(presence + support + placement)."
        ),
    )
    missing_evidence: list[str] = Field(
        default_factory=list,
        description="Expected evidence that was not found for this dimension.",
    )
    rationale: str = Field(
        default="", description="Short explanation of how the score was derived."
    )


class JobMatchReport(BaseModel):
    """Overall explainable match of a resume against a job.

    Composes the existing ``ATSScore`` and ``KeywordGapAnalysis`` primitives
    rather than duplicating them, and carries per-dimension explanations so the
    overall score is auditable. Scoring is presence + support + placement based
    (evidence lives on each ``MatchDimensionScore``), not keyword-repetition.
    """

    overall_score: float = Field(
        default=0.0, ge=0.0, le=100.0, description="Weighted composite match score (0-100)."
    )
    dimensions: list[MatchDimensionScore] = Field(
        default_factory=list,
        description="Per-dimension explainable scores that compose the overall score.",
    )
    ats_score: ATSScore | None = Field(
        default=None, description="Composed ATS breakdown, if computed."
    )
    keyword_gap: KeywordGapAnalysis | None = Field(
        default=None, description="Composed keyword-gap analysis, if computed."
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in the match assessment (0-1)."
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Actionable suggestions to improve the match.",
    )


class ResumeVariantScore(BaseModel):
    """A labeled resume variant paired with its match report for ranking."""

    variant_id: str = Field(description="Stable identifier for the resume variant.")
    label: str = Field(default="", description="Human-readable variant label.")
    report: JobMatchReport = Field(
        description="Full explainable match report for this variant."
    )

    @property
    def overall_score(self) -> float:
        """Convenience accessor for the variant's overall match score."""
        return self.report.overall_score


class ResumeSelectionResult(BaseModel):
    """Ranked selection of resume variants against a single job."""

    ranked: list[ResumeVariantScore] = Field(
        default_factory=list,
        description="Variants ordered best-first by overall match score.",
    )
    selected_variant_id: str | None = Field(
        default=None, description="Identifier of the chosen best variant, if any."
    )
    explanation: str = Field(
        default="", description="Why the selected variant was chosen over the others."
    )


class ScoreDelta(BaseModel):
    """A named metric compared across two resume variants."""

    metric: str = Field(description="Name of the compared metric (e.g. 'ats.overall').")
    before: float = Field(description="Value for the baseline / first variant.")
    after: float = Field(description="Value for the compared / second variant.")
    delta: float = Field(description="after - before (positive means improvement).")


class ResumeComparisonResult(BaseModel):
    """Deterministic comparison between two (or more) resume variants."""

    variant_labels: list[str] = Field(
        default_factory=list,
        description="Labels of the compared variants, in comparison order.",
    )
    deltas: list[ScoreDelta] = Field(
        default_factory=list,
        description="Per-metric ATS and match deltas between the variants.",
    )
    summary: str = Field(
        default="", description="Short human-readable summary of the comparison."
    )
