"""Canonical Pydantic v2 domain models for resume-kit.

This package holds transport-agnostic domain contracts only. HTTP/DB DTOs from
the upstream project are intentionally excluded (see ``references/attribution.md``).
"""

from __future__ import annotations

from .analysis import (
    AlignmentReport,
    AlignmentViolation,
    AnalysisReport,
    ATSScore,
    ATSSubScores,
    JobMatchReport,
    KeywordGapAnalysis,
    MatchDimensionScore,
    MatchedKeyword,
    MatchKind,
    RefinementConfig,
    RefinementStats,
    ResumeComparisonResult,
    ResumeSelectionResult,
    ResumeVariantScore,
    ScoreDelta,
)
from .change import (
    ChangeAction,
    ChangeProposal,
    ChangeSet,
    ChangeType,
    Confidence,
    Diff,
    FieldType,
    ResumeChange,
    ResumeDiffSummary,
)
from .common import Artifact, ArtifactKind, Severity, Warning
from .evidence import CandidateEvidence, EvidenceKind
from .job import JobDescription, Requirement, RequirementKind
from .provenance import ClaimProvenance, ProvenanceStatus
from .results import (
    AlignmentResult,
    PolicyDecision,
    PolicyReasonCode,
    PolicyRejection,
    ReviewAction,
    ReviewDecision,
    ReviewSession,
    SkillTarget,
    SkillTargetPlan,
    SkillTargetRejection,
    SkillTargetSource,
    TruthReport,
)
from .resume import (
    AdditionalInfo,
    Contact,
    CustomSection,
    CustomSectionItem,
    Education,
    Experience,
    PersonalInfo,
    Project,
    ResumeData,
    ResumeDocument,
    SectionMeta,
    SectionType,
    Skill,
    normalize_resume_data,
)

__version__ = "0.0.0"

__all__ = [
    # resume
    "ResumeDocument",
    "ResumeData",
    "PersonalInfo",
    "Contact",
    "Experience",
    "Education",
    "Project",
    "Skill",
    "AdditionalInfo",
    "SectionType",
    "SectionMeta",
    "CustomSection",
    "CustomSectionItem",
    "normalize_resume_data",
    # job
    "JobDescription",
    "Requirement",
    "RequirementKind",
    # evidence
    "CandidateEvidence",
    "EvidenceKind",
    # provenance
    "ClaimProvenance",
    "ProvenanceStatus",
    # change
    "ChangeProposal",
    "ResumeChange",
    "ChangeSet",
    "Diff",
    "ResumeDiffSummary",
    "ChangeAction",
    "ChangeType",
    "Confidence",
    "FieldType",
    # analysis
    "AnalysisReport",
    "ATSScore",
    "ATSSubScores",
    "KeywordGapAnalysis",
    "MatchedKeyword",
    "MatchKind",
    "AlignmentReport",
    "AlignmentViolation",
    "RefinementConfig",
    "RefinementStats",
    "MatchDimensionScore",
    "JobMatchReport",
    "ResumeVariantScore",
    "ResumeSelectionResult",
    "ScoreDelta",
    "ResumeComparisonResult",
    # common
    "Warning",
    "Severity",
    "Artifact",
    "ArtifactKind",
    # results (Phase 4)
    "AlignmentResult",
    "PolicyDecision",
    "PolicyReasonCode",
    "PolicyRejection",
    "ReviewAction",
    "ReviewDecision",
    "ReviewSession",
    "SkillTarget",
    "SkillTargetPlan",
    "SkillTargetRejection",
    "SkillTargetSource",
    "TruthReport",
]
