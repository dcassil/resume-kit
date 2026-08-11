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

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field

from .best_practices import FindingLocation, FindingSeverity
from .common import Warning

MatchKind = Literal["exact", "stem", "alias"]
"""How a job-description keyword matched a resume term.

- ``exact`` — same surface form (modulo case/punctuation/Unicode noise).
- ``stem``  — equal only after Snowball stemming (``mentoring`` ↔ ``mentorship``).
- ``alias`` — equal only through the curated alias lexicon (``k8s`` ↔ ``Kubernetes``).

This mirrors ``resume_kit_terms.MatchKind`` and is the single provenance vocabulary
shared by the ``matching`` and ``ats`` engines (RIT-I-0008).
"""


class MatchedKeyword(BaseModel):
    """A job-description keyword found present in a resume, with match provenance.

    Emitted by both the keyword-matching engine and the ATS engine so downstream
    consumers (e.g. terminology alignment, RIT-I-0010) can distinguish an exact
    hit versus a synonym hit. ``canonical`` is set only for ``alias`` matches.
    """

    model_config = {"frozen": True}

    keyword: str = Field(description="The job-description keyword that matched.")
    kind: MatchKind = Field(description="How it matched: exact, stem, or alias.")
    canonical: str | None = Field(
        default=None,
        description="For alias matches, the canonical term of the alias group.",
    )

    @property
    def annotation(self) -> str:
        """Render provenance as a string: ``exact``/``stem``/``alias:<canonical>``."""
        if self.kind == "alias" and self.canonical is not None:
            return f"alias:{self.canonical}"
        return self.kind


class TerminologyAlignment(BaseModel):
    """A suggestion to mirror the employer's exact wording for an alias hit.

    Emitted by the terminology-alignment analyzer (RIT-I-0010) for each
    job-description keyword the resume already satisfies, but only under a
    *different* surface form reached through the curated alias lexicon (an
    ``alias`` match). The resume says ``current_wording``; the employer's exact
    wording is ``jd_keyword`` — the proposed mirror target. Analysis-only: this
    records where the current wording occurs so a later apply path (RIT-T-0073)
    can mirror it; it performs no mutation itself.

    Exact hits and no-match keywords never produce a ``TerminologyAlignment``:
    exact wording needs no mirroring and a missing keyword stays a gap.
    """

    model_config = {"frozen": True}

    jd_keyword: str = Field(
        description="Employer's exact wording — the proposed mirror target."
    )
    current_wording: str = Field(
        description="The resume's alias surface form that matched the keyword."
    )
    locations: list[str] = Field(
        default_factory=list,
        description=(
            "Dot+bracket resume paths where the current wording occurs "
            "(e.g. ``workExperience[0].description[1]``), sorted for determinism."
        ),
    )
    canonical: str = Field(
        description="Canonical term of the alias group (from match provenance)."
    )
    match_kind: Literal["alias"] = Field(
        default="alias",
        description=(
            "Provenance of the hit. Only ``alias`` today; kept as a field for "
            "forward-compat if a stem tier is ever re-enabled."
        ),
    )


class TerminologyCandidate(BaseModel):
    """A PROPOSED synonym pair the closed lexicon could not surface on its own.

    Emitted by the conservative fuzzy candidate proposer (RIT-T-0165) for each
    *missing* job-description keyword the resume plausibly satisfies under a
    different surface term the curated/alias matcher did not already reach — e.g.
    ``responsive design`` (JD) vs ``responsive UI`` (resume). It exists to SEED
    and GROW the project alias index, but it is a PROPOSAL ONLY: ``confirmed`` is
    always ``False`` here. Every candidate must still pass human confirmation and
    the existing truth gate before an alias is written; the proposer never
    auto-accepts and never mutates anything. Unconfirmed candidates therefore
    never affect scoring — the conservative-lexicon guarantee is preserved.
    """

    model_config = {"frozen": True}

    jd_keyword: str = Field(
        description="The missing employer keyword — the proposed alias canonical."
    )
    resume_phrase: str = Field(
        description="The resume's current surface wording proposed as the alias."
    )
    locations: list[str] = Field(
        default_factory=list,
        description=(
            "Dot+bracket resume paths where ``resume_phrase`` occurs "
            "(e.g. ``workExperience[0].description[1]``), sorted for determinism."
        ),
    )
    reason: str = Field(
        description=(
            "Human-readable why-this-was-proposed (e.g. \"shared stem "
            "'responsive', one differing token\") — advisory only, never scored."
        ),
    )
    confirmed: Literal[False] = Field(
        default=False,
        description=(
            "Always False: a proposer output is unconfirmed by construction. "
            "Confirmation + the truth gate happen downstream before any write."
        ),
    )


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
    matched_keywords: list[MatchedKeyword] = Field(
        default_factory=list,
        description=(
            "JD keywords found present in the resume, with match provenance "
            "(exact/stem/alias). Synonym-aware (RIT-I-0008)."
        ),
    )


class FixAffordance(StrEnum):
    """How the base fixer (RIT-T-0115) may act on a structural finding.

    The ``auto_safe_*`` values are deterministic, faithfulness-preserving
    transforms the fixer may apply unattended; ``needs_judgment`` requires the
    interactive walkthrough (missing facts, ambiguous rename, or a rewrite).
    This axis is orthogonal to :class:`FindingSeverity`. Unknown codes or a
    missing locator MUST be treated as ``needs_judgment``.
    """

    AUTO_SAFE_RENAME = "auto_safe_rename"
    AUTO_SAFE_STRIP = "auto_safe_strip"
    AUTO_SAFE_NORMALIZE = "auto_safe_normalize"
    AUTO_SAFE_REORDER = "auto_safe_reorder"
    NEEDS_JUDGMENT = "needs_judgment"


class AtsStructureFinding(BaseModel):
    """One machine-actionable structural finding (RIT-T-0114).

    The structured channel behind the human-readable ``recommendations``
    strings: a stable ``code``, the shared-taxonomy ``severity``, a structured
    ``location``, a ``fix_affordance`` telling the base fixer whether it can act
    unattended, and a small ``metadata`` map carrying the concrete target of the
    fix (matched span, replacement text, section name, normalized value).
    """

    model_config = {"frozen": True}

    code: str = Field(description="Stable finding code, e.g. 'PII_SSN', 'NONSTANDARD_SECTION'.")
    message: str = Field(description="Human-readable message (also surfaced in recommendations).")
    severity: FindingSeverity = Field(description="Shared grooming-finding severity.")
    fix_affordance: FixAffordance = Field(description="How the base fixer may act on this finding.")
    location: FindingLocation = Field(
        default_factory=FindingLocation,
        description="Structured locator for where the finding applies.",
    )
    metadata: dict[str, str] = Field(
        default_factory=dict,
        description="Concrete fix target (matched span, replacement, section name, etc.).",
    )


class AtsStructureReport(BaseModel):
    """Resume-only structural ATS report — no job, no composite score.

    Carries only the structural signal a resume can be assessed on without a
    job description: how many key sections are present and deterministic
    structural findings/recommendations (contact info, section presence, dates,
    formatting risks). Deliberately excludes ``keyword_match``,
    ``skills_coverage``, and any composite ``overall_score`` — those require a
    job and live on :class:`ATSScore`. Frozen because it is a pure report value.

    ``findings`` is the machine channel (RIT-T-0114) the base fixer consumes;
    ``recommendations`` is the human channel, derived deterministically from the
    findings' messages. Both are populated and kept in sync.
    """

    model_config = {"frozen": True}

    section_completeness: float = Field(
        default=0.0,
        ge=0.0,
        le=100.0,
        description="Key resume sections present (0-100).",
    )
    findings: list[AtsStructureFinding] = Field(
        default_factory=list,
        description="Machine-actionable structural findings (code + severity + fix affordance).",
    )
    recommendations: list[str] = Field(
        default_factory=list,
        description="Human-readable structural recommendations, derived from findings.",
    )


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
    matched_keywords: list[MatchedKeyword] = Field(
        default_factory=list,
        description=(
            "JD keywords found present in the resume, with match provenance "
            "(exact/stem/alias). Synonym-aware (RIT-I-0008)."
        ),
    )
    warnings: list[str] = Field(
        default_factory=list,
        description=(
            "Non-fatal advisories about input degeneracy that make the "
            "injectable/non-injectable split unreliable (e.g. tailored and "
            "master resolve to near-identical content). Empty on normal runs."
        ),
    )


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
