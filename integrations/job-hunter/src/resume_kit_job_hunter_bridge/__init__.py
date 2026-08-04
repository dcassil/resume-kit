"""Resume Kit job-hunter bridge — a pure-library import surface (REQ-506).

Job-hunter imports these stable typed callables to reach resume-kit's
capabilities. The bridge delegates to the capability facade and returns
canonical :class:`~resume_kit_core.InterfaceResponse` payloads carrying
``resume_kit_schemas`` data. It never mutates job-hunter state and imports no
transport, CLI, MCP, API, storage, queue, or HTTP code.
"""

from __future__ import annotations

from resume_kit_job_hunter_bridge.bridge import (
    ResumeJobAnalysis,
    align_resume_for_job,
    align_resume_for_job_sync,
    analyze_resume_for_job,
    analyze_resume_for_job_sync,
    build_evidence,
    build_evidence_sync,
    export_resume,
    export_resume_sync,
    validate_truth,
    validate_truth_sync,
)

__version__ = "0.0.0"

__all__ = [
    "ResumeJobAnalysis",
    "analyze_resume_for_job",
    "align_resume_for_job",
    "build_evidence",
    "export_resume",
    "validate_truth",
    "analyze_resume_for_job_sync",
    "align_resume_for_job_sync",
    "build_evidence_sync",
    "export_resume_sync",
    "validate_truth_sync",
]
