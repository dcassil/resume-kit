"""Resume Kit Facade — the single in-process capability boundary for Phase 5.

Every Phase 5 transport (CLI, MCP, API, bridge) calls the capabilities in this
package instead of touching engine functions directly, so all surfaces stay in
parity and every result flows through the ``resume_kit_core`` interface
substrate.
"""

__version__ = "0.0.0"

from resume_kit_facade.alias_scope import use_alias_file
from resume_kit_facade.capabilities import (
    REGISTRY,
    align_resume,
    align_terminology,
    build_candidate_evidence_capability,
    check_resume_ats,
    check_resume_job_match,
    compare_resume_versions,
    export_resume,
    extract_job_description,
    extract_resume,
    identify_resume_gaps,
    select_best_resume,
    suggest_terminology,
    validate_resume_truth_capability,
)
from resume_kit_facade.models import (
    AlignResumeRequest,
    AlignTerminologyRequest,
    AlignTerminologyResult,
    BuildCandidateEvidenceRequest,
    CapabilityOptions,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    CompareResumeVersionsRequest,
    ExportResumeRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    IdentifyResumeGapsRequest,
    SelectBestResumeRequest,
    SuggestTerminologyRequest,
    TerminologyAlignmentDelta,
    ValidateResumeTruthRequest,
)

__all__ = [
    # registry
    "REGISTRY",
    # capability callables
    "align_resume",
    "align_terminology",
    "build_candidate_evidence_capability",
    "check_resume_ats",
    "check_resume_job_match",
    "compare_resume_versions",
    "export_resume",
    "extract_job_description",
    "extract_resume",
    "identify_resume_gaps",
    "select_best_resume",
    "suggest_terminology",
    "validate_resume_truth_capability",
    # options
    "CapabilityOptions",
    # alias scoping helper
    "use_alias_file",
    # request models
    "AlignResumeRequest",
    "AlignTerminologyRequest",
    "BuildCandidateEvidenceRequest",
    "CheckResumeAtsRequest",
    "CheckResumeJobMatchRequest",
    "CompareResumeVersionsRequest",
    "ExportResumeRequest",
    "ExtractJobDescriptionRequest",
    "ExtractResumeRequest",
    "IdentifyResumeGapsRequest",
    "SelectBestResumeRequest",
    "SuggestTerminologyRequest",
    "ValidateResumeTruthRequest",
    # response models
    "AlignTerminologyResult",
    "TerminologyAlignmentDelta",
]
