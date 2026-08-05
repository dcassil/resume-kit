"""HTTP transport request bodies for the Resume Kit REST API.

Each model is a thin pydantic wrapper carrying ``resume_kit_schemas`` domain
value types plus the shared execution flags (:attr:`no_llm`, :attr:`strict`,
:attr:`human_in_loop`).  Bodies are validated by FastAPI and then translated
into the frozen ``resume_kit_facade`` request dataclasses by the routes; no
business logic lives here.  The API never accepts or constructs a concrete LLM
provider, so provider-requiring capabilities run only when the caller also sets
``no_llm`` (the deterministic path) — otherwise the facade returns the stable
provider-not-configured envelope.
"""

from __future__ import annotations

from pydantic import BaseModel, Field
from resume_kit_export.models import ExportFormat, ExportOptions
from resume_kit_schemas import (
    CandidateEvidence,
    JobDescription,
    ResumeDocument,
    TerminologyAlignment,
)


class _Options(BaseModel):
    """Execution flags shared by every endpoint body.

    ``provider`` is intentionally absent: the HTTP transport does not build or
    accept providers.  LLM paths are reachable only through the deterministic
    ``no_llm`` route; otherwise the facade emits provider-not-configured.
    """

    no_llm: bool = Field(default=False, description="Force the deterministic path.")
    strict: bool = Field(default=False, description="Escalate warnings to errors.")
    human_in_loop: bool = Field(
        default=False, description="Request human-in-the-loop behaviour."
    )


class ExtractResumeBody(_Options):
    """Body for ``POST /extract`` — raw resume text plus a filename."""

    content: str = Field(description="Raw resume text to extract from.")
    filename: str = Field(default="resume.txt", description="Source filename.")


class ExtractJobDescriptionBody(_Options):
    """Body for ``POST /extract-job``."""

    raw_text: str = Field(description="Raw job-description text.")


class CheckResumeAtsBody(_Options):
    """Body for ``POST /check-ats``."""

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class CheckAtsStructureBody(_Options):
    """Body for ``POST /check-ats-structure`` — resume only, no job."""

    resume: ResumeDocument


class CheckResumeJobMatchBody(_Options):
    """Body for ``POST /match``."""

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class SelectBestResumeBody(_Options):
    """Body for ``POST /select``."""

    resumes: list[ResumeDocument]
    job: JobDescription
    labels: list[str] | None = None


class CompareResumeVersionsBody(_Options):
    """Body for ``POST /compare``."""

    base: ResumeDocument
    candidate: ResumeDocument
    job: JobDescription
    base_label: str = "base"
    candidate_label: str = "candidate"


class IdentifyResumeGapsBody(_Options):
    """Body for ``POST /identify-gaps``."""

    job: JobDescription
    tailored: ResumeDocument
    master: ResumeDocument
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class SuggestTerminologyBody(_Options):
    """Body for ``POST /suggest-terminology``."""

    resume: ResumeDocument
    job: JobDescription
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class AlignTerminologyBody(_Options):
    """Body for ``POST /align-terminology`` — apply ONE accepted suggestion."""

    suggestion: TerminologyAlignment = Field(
        description="The accepted terminology-mirroring suggestion to apply."
    )
    location: str = Field(
        description="Resume path from ``suggestion.locations`` to apply the swap at."
    )
    resume: ResumeDocument
    job: JobDescription
    evidence: list[CandidateEvidence] = Field(default_factory=list)
    freedom: int | None = Field(
        default=None,
        description="Explicit policy-freedom level; default is the minimal level.",
    )
    alias_file: str | None = Field(
        default=None,
        description="Optional project alias JSON path for synonym-aware scoring.",
    )


class AlignResumeBody(_Options):
    """Body for ``POST /align``."""

    resume: ResumeDocument
    job: JobDescription
    evidence: list[CandidateEvidence] | None = None


class ValidateResumeTruthBody(_Options):
    """Body for ``POST /validate-truth``."""

    resume: ResumeDocument
    evidence: list[CandidateEvidence] = Field(default_factory=list)


class BuildCandidateEvidenceBody(_Options):
    """Body for ``POST /build-evidence``."""

    resume: ResumeDocument
    approved_claims: list[CandidateEvidence] | None = None


class ExportResumeBody(_Options):
    """Body for ``POST /export`` — render a resume to ``pdf`` or ``docx``.

    ``format`` selects the output; ``options`` carries the deterministic export
    tuning (fonts, margins, page size).  ``artifact_id`` may override the
    deterministic hash-derived id.
    """

    resume: ResumeDocument
    format: ExportFormat
    options: ExportOptions | None = None
    artifact_id: str | None = None
