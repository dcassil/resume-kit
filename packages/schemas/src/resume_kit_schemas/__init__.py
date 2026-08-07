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
    AtsStructureFinding,
    AtsStructureReport,
    ATSSubScores,
    FixAffordance,
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
    TerminologyAlignment,
)
from .ats_view import (
    ATS_VIEW_DISCLAIMER,
    ATS_VIEW_SCHEMA_VERSION,
    AtsViewReport,
)
from .best_practices import (
    BEST_PRACTICES_SCHEMA_VERSION,
    BestPracticesFinding,
    BestPracticesReport,
    FindingLocation,
    FindingSeverity,
    ProvenanceKind,
    ResolutionKind,
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
from .feedback import (
    CandidateFeatures,
    EditFeedback,
    EditFeedbackReasonCode,
    EditOutcome,
    PreferencePair,
    UserPreferenceProfile,
)
from .job import JobDescription, Requirement, RequirementKind
from .keyword_hygiene import is_concrete_keyword, sanitize_keywords
from .provenance import ClaimProvenance, ProvenanceReasonCode, ProvenanceStatus
from .results import (
    AlignmentResult,
    FaithfulnessCode,
    FaithfulnessFinding,
    FaithfulnessReport,
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
from .scoredoc import (
    SCOREDOC_SCHEMA_VERSION,
    KeywordZone,
    ScoreDegree,
    ScoreDoc,
    ScoreEntities,
    ScoreRole,
    ScoreSection,
    ZonedKeywordIndex,
)

__version__ = "0.0.0"

__all__ = [
    # keyword hygiene (RIT-T-0128)
    "is_concrete_keyword",
    "sanitize_keywords",
    # scoredoc (RIT-I-0017)
    "SCOREDOC_SCHEMA_VERSION",
    "KeywordZone",
    "ScoreDegree",
    "ScoreDoc",
    "ScoreEntities",
    "ScoreRole",
    "ScoreSection",
    "ZonedKeywordIndex",
    # ats-view (RIT-T-0109)
    "ATS_VIEW_DISCLAIMER",
    "ATS_VIEW_SCHEMA_VERSION",
    "AtsViewReport",
    # best-practices (RIT-I-0016)
    "BEST_PRACTICES_SCHEMA_VERSION",
    "BestPracticesFinding",
    "BestPracticesReport",
    "FindingLocation",
    "FindingSeverity",
    "ProvenanceKind",
    "ResolutionKind",
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
    # feedback (preference learning)
    "EditFeedback",
    "EditFeedbackReasonCode",
    "EditOutcome",
    "UserPreferenceProfile",
    "CandidateFeatures",
    "PreferencePair",
    # provenance
    "ClaimProvenance",
    "ProvenanceReasonCode",
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
    "AtsStructureFinding",
    "AtsStructureReport",
    "FixAffordance",
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
    "TerminologyAlignment",
    # common
    "Warning",
    "Severity",
    "Artifact",
    "ArtifactKind",
    # results (Phase 4)
    "AlignmentResult",
    "FaithfulnessCode",
    "FaithfulnessFinding",
    "FaithfulnessReport",
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
