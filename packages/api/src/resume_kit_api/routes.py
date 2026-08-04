"""FastAPI route registration for the Resume Kit REST API.

One ``POST`` endpoint is registered per Phase 5 capability.  Each route is a
thin adapter: it validates its request body (a pydantic model from
:mod:`resume_kit_api.models`), translates it into the matching frozen
``resume_kit_facade`` request dataclass plus a ``CapabilityOptions`` bundle,
awaits the facade capability, and returns the resulting
:class:`~resume_kit_core.InterfaceResponse` as JSON.  No engine package is
imported here and no business logic runs; the facade owns all dispatch.

HTTP status policy
------------------
The structured envelope is authoritative: success, warnings (kept separate
from errors), ``requires_human_input`` + ``questions``, provenance, and
artifacts always travel in the body, and the body is returned intact no matter
what status is chosen.  We select the status from the envelope so HTTP callers
get a coarse, deterministic signal without having to parse the body:

* no errors (ok or needs-input) -> ``200 OK``
* ``invalid_input`` / ``validation_failed`` / ``schema_mismatch`` /
  ``missing_required_field`` -> ``422 Unprocessable Entity``
* ``provider_not_configured`` -> ``501 Not Implemented``
* other provider errors (unavailable/timeout/rate-limited/...) -> ``502``
* anything else (internal) -> ``500 Internal Server Error``

Because the envelope is always emitted verbatim, a client may ignore the status
entirely and drive purely off ``errors`` / ``requires_human_input``.
"""

from __future__ import annotations

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from resume_kit_core.errors import ErrorCode
from resume_kit_core.response import InterfaceResponse
from resume_kit_facade.capabilities import REGISTRY
from resume_kit_facade.models import (
    AlignResumeRequest,
    BuildCandidateEvidenceRequest,
    CapabilityOptions,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    CompareResumeVersionsRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    IdentifyResumeGapsRequest,
    SelectBestResumeRequest,
    ValidateResumeTruthRequest,
)

from resume_kit_api.models import (
    AlignResumeBody,
    BuildCandidateEvidenceBody,
    CheckResumeAtsBody,
    CheckResumeJobMatchBody,
    CompareResumeVersionsBody,
    ExtractJobDescriptionBody,
    ExtractResumeBody,
    IdentifyResumeGapsBody,
    SelectBestResumeBody,
    ValidateResumeTruthBody,
    _Options,
)

_STATUS_BY_CODE: dict[ErrorCode, int] = {
    ErrorCode.INVALID_INPUT: 422,
    ErrorCode.MISSING_REQUIRED_FIELD: 422,
    ErrorCode.VALIDATION_FAILED: 422,
    ErrorCode.SCHEMA_MISMATCH: 422,
    ErrorCode.PROVIDER_NOT_CONFIGURED: 501,
    ErrorCode.PROVIDER_UNAVAILABLE: 502,
    ErrorCode.PROVIDER_TIMEOUT: 502,
    ErrorCode.PROVIDER_RATE_LIMITED: 502,
    ErrorCode.PROVIDER_INVALID_RESPONSE: 502,
    ErrorCode.PROVIDER_JSON_PARSE_FAILED: 502,
}


def _status_for(response: InterfaceResponse[object]) -> int:
    """Pick the HTTP status for a finished envelope (body returned intact)."""
    for error in response.errors:
        return _STATUS_BY_CODE.get(error.code, 500)
    return 200


def _render(response: InterfaceResponse[object]) -> Response:
    """Serialise the envelope to JSON with the policy-selected status."""
    return JSONResponse(
        content=response.model_dump(mode="json"),
        status_code=_status_for(response),
    )


def _options(body: _Options) -> CapabilityOptions:
    """Build shared execution options from any request body's flags."""
    return CapabilityOptions(
        no_llm=body.no_llm,
        strict=body.strict,
        human_in_loop=body.human_in_loop,
    )


def register_routes(app: FastAPI) -> None:
    """Register one POST endpoint per Phase 5 capability on ``app``."""

    @app.post("/extract")
    async def extract(body: ExtractResumeBody) -> Response:
        request = ExtractResumeRequest(
            content=body.content.encode("utf-8"), filename=body.filename
        )
        return _render(await REGISTRY["extract-resume"](request, _options(body)))

    @app.post("/extract-job")
    async def extract_job(body: ExtractJobDescriptionBody) -> Response:
        request = ExtractJobDescriptionRequest(raw_text=body.raw_text)
        return _render(
            await REGISTRY["extract-job-description"](request, _options(body))
        )

    @app.post("/check-ats")
    async def check_ats(body: CheckResumeAtsBody) -> Response:
        request = CheckResumeAtsRequest(resume=body.resume, job=body.job)
        return _render(await REGISTRY["check-resume-ats"](request, _options(body)))

    @app.post("/match")
    async def match(body: CheckResumeJobMatchBody) -> Response:
        request = CheckResumeJobMatchRequest(resume=body.resume, job=body.job)
        return _render(
            await REGISTRY["check-resume-job-match"](request, _options(body))
        )

    @app.post("/select")
    async def select(body: SelectBestResumeBody) -> Response:
        request = SelectBestResumeRequest(
            resumes=body.resumes, job=body.job, labels=body.labels
        )
        return _render(await REGISTRY["select-best-resume"](request, _options(body)))

    @app.post("/compare")
    async def compare(body: CompareResumeVersionsBody) -> Response:
        request = CompareResumeVersionsRequest(
            base=body.base,
            candidate=body.candidate,
            job=body.job,
            base_label=body.base_label,
            candidate_label=body.candidate_label,
        )
        return _render(
            await REGISTRY["compare-resume-versions"](request, _options(body))
        )

    @app.post("/identify-gaps")
    async def identify_gaps(body: IdentifyResumeGapsBody) -> Response:
        request = IdentifyResumeGapsRequest(
            job=body.job, tailored=body.tailored, master=body.master
        )
        return _render(
            await REGISTRY["identify-resume-gaps"](request, _options(body))
        )

    @app.post("/align")
    async def align(body: AlignResumeBody) -> Response:
        request = AlignResumeRequest(
            resume=body.resume, job=body.job, evidence=body.evidence
        )
        return _render(await REGISTRY["align-resume"](request, _options(body)))

    @app.post("/validate-truth")
    async def validate_truth(body: ValidateResumeTruthBody) -> Response:
        request = ValidateResumeTruthRequest(
            resume=body.resume, evidence=body.evidence
        )
        return _render(
            await REGISTRY["validate-resume-truth"](request, _options(body))
        )

    @app.post("/build-evidence")
    async def build_evidence(body: BuildCandidateEvidenceBody) -> Response:
        request = BuildCandidateEvidenceRequest(
            resume=body.resume, approved_claims=body.approved_claims
        )
        return _render(
            await REGISTRY["build-candidate-evidence"](request, _options(body))
        )
