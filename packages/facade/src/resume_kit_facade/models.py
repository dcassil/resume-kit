"""Transport-agnostic request and options models for the capability facade.

These models carry only ``resume_kit_schemas`` value types plus a shared
:class:`CapabilityOptions` bundle.  They deliberately do NOT construct or import
any concrete LLM provider: a caller passes an already-built
:class:`~resume_kit_core.StructuredCompletionProvider` (or ``None``) via the
``provider`` option.  Transports translate their own inputs (CLI args, MCP tool
params, HTTP bodies) into these models before calling a capability.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from resume_kit_core import StructuredCompletionProvider
from resume_kit_core.storage import ArtifactStore
from resume_kit_export import ExportFormat, ExportOptions
from resume_kit_schemas import (
    CandidateEvidence,
    JobDescription,
    ResumeDocument,
)


@dataclass(frozen=True)
class CapabilityOptions:
    """Cross-capability execution options shared by every facade callable.

    Attributes:
        no_llm: Force the deterministic, provider-free path for capabilities
            that have one.  When True the ``provider`` is never invoked.
        strict: Escalate advisory warnings to failures in the response
            substrate (see ``build_success(strict=...)``).
        human_in_loop: Request human-in-the-loop behaviour for capabilities
            that support it (currently ``align-resume``).
        provider: An already-constructed structured-completion provider, or
            ``None``.  LLM-requiring capabilities return the stable
            provider-not-configured error when this is ``None`` and
            ``no_llm`` is False.
        artifact_store: Optional :class:`~resume_kit_core.storage.ArtifactStore`
            injection point for capabilities that persist rendered bytes (e.g.
            ``export-resume``).  When ``None`` such capabilities fall back to a
            deterministic in-memory store.  No concrete backend is required.
    """

    no_llm: bool = False
    strict: bool = False
    human_in_loop: bool = False
    provider: StructuredCompletionProvider | None = None
    artifact_store: ArtifactStore | None = None


@dataclass(frozen=True)
class ExtractResumeRequest:
    """Inputs for the extract-resume capability."""

    content: bytes
    filename: str


@dataclass(frozen=True)
class ExtractJobDescriptionRequest:
    """Inputs for the extract-job-description capability."""

    raw_text: str


@dataclass(frozen=True)
class CheckResumeAtsRequest:
    """Inputs for the check-resume-ats capability.

    ``alias_file`` is an optional path to a project alias JSON (RIT-T-0068
    format). When set, scoring becomes aware of those project synonyms for this
    call; ``None`` (the default) is seed-only, identical to pre-0009 behaviour.
    """

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class CheckResumeJobMatchRequest:
    """Inputs for the check-resume-job-match capability.

    ``alias_file`` optionally points at a project alias JSON (RIT-T-0068
    format) to make matching aware of project synonyms for this call; ``None``
    (default) is seed-only, identical to pre-0009 behaviour.
    """

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class SelectBestResumeRequest:
    """Inputs for the select-best-resume capability."""

    resumes: Sequence[ResumeDocument]
    job: JobDescription
    labels: Sequence[str] | None = None


@dataclass(frozen=True)
class CompareResumeVersionsRequest:
    """Inputs for the compare-resume-versions capability."""

    base: ResumeDocument
    candidate: ResumeDocument
    job: JobDescription
    base_label: str = "base"
    candidate_label: str = "candidate"


@dataclass(frozen=True)
class IdentifyResumeGapsRequest:
    """Inputs for the identify-resume-gaps capability.

    ``alias_file`` optionally points at a project alias JSON (RIT-T-0068
    format) to make gap analysis aware of project synonyms for this call;
    ``None`` (default) is seed-only, identical to pre-0009 behaviour.
    """

    job: JobDescription
    tailored: ResumeDocument
    master: ResumeDocument
    alias_file: str | Path | None = None


@dataclass(frozen=True)
class AlignResumeRequest:
    """Inputs for the align-resume capability."""

    resume: ResumeDocument
    job: JobDescription
    evidence: Sequence[CandidateEvidence] | None = None


@dataclass(frozen=True)
class ValidateResumeTruthRequest:
    """Inputs for the validate-resume-truth capability."""

    resume: ResumeDocument
    evidence: list[CandidateEvidence] = field(default_factory=list)


@dataclass(frozen=True)
class BuildCandidateEvidenceRequest:
    """Inputs for the build-candidate-evidence capability."""

    resume: ResumeDocument
    approved_claims: list[CandidateEvidence] | list[str] | None = None


@dataclass(frozen=True)
class ExportResumeRequest:
    """Inputs for the export-resume capability.

    The exported artifact id is deterministic: a caller may supply an explicit
    ``artifact_id``; otherwise :meth:`resolved_artifact_id` derives a stable id
    from a SHA-256 hash of the format plus the rendered content — no UUIDs,
    timestamps, or random values.
    """

    resume: ResumeDocument
    format: ExportFormat
    options: ExportOptions | None = None
    artifact_id: str | None = None

    def resolved_artifact_id(self, data: bytes) -> str:
        """Return the caller-supplied id or a deterministic hash-derived one."""
        if self.artifact_id is not None:
            return self.artifact_id
        digest = hashlib.sha256(self.format.value.encode("utf-8") + data)
        return f"resume-{self.format.value}-{digest.hexdigest()}"
