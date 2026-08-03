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
