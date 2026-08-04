"""Direct MCP tool handlers over the resume-kit capability facade."""

from __future__ import annotations

import base64
from collections.abc import Awaitable, Callable, Sequence
from typing import get_args, get_type_hints

from pydantic import BaseModel
from resume_kit_core import (
    CoreError,
    ErrorCode,
    InterfaceResponse,
    ResumeKitError,
    StructuredCompletionProvider,
)
from resume_kit_core.storage import ArtifactRef
from resume_kit_export.models import ExportFormat
from resume_kit_facade.capabilities import REGISTRY
from resume_kit_facade.models import (
    AlignResumeRequest,
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
    ValidateResumeTruthRequest,
)

ToolArguments = dict[str, object]
ToolResult = dict[str, object]
ToolHandler = Callable[[ToolArguments], Awaitable[ToolResult]]
ModelValidator = Callable[[object], object]

TOOL_NAMES: tuple[str, ...] = (
    "resume_extract",
    "job_description_extract",
    "resume_check_ats",
    "resume_check_job_match",
    "resume_select_best",
    "resume_compare_versions",
    "resume_identify_gaps",
    "resume_align",
    "resume_validate_truth",
    "candidate_evidence_build",
    "resume_export",
)

_OPTIONS = frozenset({"no_llm", "strict", "human_in_loop", "provider"})


class _ValidationFailure(Exception):
    """Input validation failure before dispatching to the facade."""

    def __init__(self, message: str, *, field: str | None = None) -> None:
        super().__init__(message)
        self.field = field


class _InMemoryArtifactStore:
    """Per-call MCP artifact store used to retrieve export bytes."""

    def __init__(self) -> None:
        self._store: dict[str, object] = {}

    async def put(
        self,
        artifact_id: str,
        artifact_type: str,
        data: object,
        *,
        content_type: str = "application/json",
        metadata: dict[str, object] | None = None,
    ) -> ArtifactRef:
        self._store[artifact_id] = data
        return ArtifactRef(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            content_type=content_type,
            metadata=metadata or {},
        )

    async def get(self, artifact_id: str) -> object:
        if artifact_id not in self._store:
            raise ResumeKitError(
                CoreError(
                    code=ErrorCode.ARTIFACT_NOT_FOUND,
                    message=f"Artifact '{artifact_id}' not found.",
                )
            )
        return self._store[artifact_id]

    async def exists(self, artifact_id: str) -> bool:
        return artifact_id in self._store


def _find_model_type(annotation: object) -> type[BaseModel]:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return annotation
    for nested in get_args(annotation):
        try:
            return _find_model_type(nested)
        except _ValidationFailure:
            continue
    raise _ValidationFailure("Could not resolve facade field model validator.")


def _model_validator(request_type: type[object], field: str) -> ModelValidator:
    field_type = _find_model_type(get_type_hints(request_type)[field])
    validator: ModelValidator = field_type.model_validate
    return validator


_VALIDATE_RESUME = _model_validator(CheckResumeAtsRequest, "resume")
_VALIDATE_JOB = _model_validator(CheckResumeAtsRequest, "job")
_VALIDATE_EVIDENCE = _model_validator(ValidateResumeTruthRequest, "evidence")


def _dump(response: InterfaceResponse[object]) -> ToolResult:
    return response.model_dump(mode="json")


def _validation_error(exc: _ValidationFailure) -> ToolResult:
    details: ToolArguments = {}
    if exc.field is not None:
        details["field"] = exc.field
    response: InterfaceResponse[object] = InterfaceResponse(
        errors=[
            CoreError(
                code=ErrorCode.INVALID_INPUT,
                message=str(exc),
                details=details,
            )
        ]
    )
    return _dump(response)


def _required(arguments: ToolArguments, field: str) -> object:
    if field not in arguments:
        raise _ValidationFailure(f"Missing required field '{field}'.", field=field)
    return arguments[field]


def _optional_bool(arguments: ToolArguments, field: str) -> bool:
    value = arguments.get(field, False)
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    raise _ValidationFailure(f"Field '{field}' must be a boolean.", field=field)


def _options(arguments: ToolArguments) -> CapabilityOptions:
    provider_value = arguments.get("provider")
    provider: StructuredCompletionProvider | None
    if provider_value is None:
        provider = None
    elif isinstance(provider_value, StructuredCompletionProvider):
        provider = provider_value
    else:
        raise _ValidationFailure(
            "Field 'provider' must implement StructuredCompletionProvider.",
            field="provider",
        )
    return CapabilityOptions(
        no_llm=_optional_bool(arguments, "no_llm"),
        strict=_optional_bool(arguments, "strict"),
        human_in_loop=_optional_bool(arguments, "human_in_loop"),
        provider=provider,
    )


def _string(arguments: ToolArguments, field: str) -> str:
    value = _required(arguments, field)
    if isinstance(value, str):
        return value
    raise _ValidationFailure(f"Field '{field}' must be a string.", field=field)


def _bytes(arguments: ToolArguments, field: str) -> bytes:
    value = _required(arguments, field)
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise _ValidationFailure(
        f"Field '{field}' must be bytes or a UTF-8 string.",
        field=field,
    )


def _optional_string(arguments: ToolArguments, field: str, default: str) -> str:
    value = arguments.get(field, default)
    if isinstance(value, str):
        return value
    raise _ValidationFailure(f"Field '{field}' must be a string.", field=field)


def _export_format(arguments: ToolArguments, field: str) -> ExportFormat:
    value = _string(arguments, field)
    try:
        return ExportFormat(value)
    except ValueError as exc:
        raise _ValidationFailure(
            "Field 'format' must be one of: pdf, docx.",
            field=field,
        ) from exc


def _make_request(request_type: type[object], fields: ToolArguments) -> object:
    return request_type(**fields)


def _validated(
    validator: ModelValidator,
    value: object,
    field: str,
) -> object:
    try:
        return validator(value)
    except ValueError as exc:
        raise _ValidationFailure(str(exc), field=field) from exc


def _resume(value: object, field: str) -> object:
    return _validated(_VALIDATE_RESUME, value, field)


def _job(value: object, field: str) -> object:
    return _validated(_VALIDATE_JOB, value, field)


def _evidence(value: object, field: str) -> object:
    return _validated(_VALIDATE_EVIDENCE, value, field)


def _object_list(arguments: ToolArguments, field: str) -> Sequence[object]:
    value = _required(arguments, field)
    if isinstance(value, list):
        return value
    raise _ValidationFailure(f"Field '{field}' must be a list.", field=field)


def _optional_evidence_list(
    arguments: ToolArguments,
    field: str,
) -> list[object] | None:
    value = arguments.get(field)
    if value is None:
        return None
    if not isinstance(value, list):
        raise _ValidationFailure(f"Field '{field}' must be a list.", field=field)
    return [_evidence(item, field) for item in value]


def _optional_labels(arguments: ToolArguments) -> list[str] | None:
    value = arguments.get("labels")
    if value is None:
        return None
    if not isinstance(value, list):
        raise _ValidationFailure("Field 'labels' must be a list.", field="labels")
    labels: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise _ValidationFailure(
                "Field 'labels' must contain only strings.",
                field="labels",
            )
        labels.append(item)
    return labels


def _approved_claims(arguments: ToolArguments) -> object:
    value = arguments.get("approved_claims")
    if value is None:
        return None
    if not isinstance(value, list):
        raise _ValidationFailure(
            "Field 'approved_claims' must be a list.",
            field="approved_claims",
        )
    if all(isinstance(item, str) for item in value):
        return [item for item in value if isinstance(item, str)]
    return [_evidence(item, "approved_claims") for item in value]


async def _call(
    facade_name: str,
    request: object,
    arguments: ToolArguments,
) -> ToolResult:
    try:
        options = _options(arguments)
    except _ValidationFailure as exc:
        return _validation_error(exc)
    response = await REGISTRY[facade_name](request, options)
    return _dump(response)


async def resume_extract(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            ExtractResumeRequest,
            {
                "content": _bytes(arguments, "content"),
                "filename": _string(arguments, "filename"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("extract-resume", request, arguments)


async def job_description_extract(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            ExtractJobDescriptionRequest,
            {"raw_text": _string(arguments, "raw_text")},
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("extract-job-description", request, arguments)


async def resume_check_ats(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            CheckResumeAtsRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "job": _job(_required(arguments, "job"), "job"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("check-resume-ats", request, arguments)


async def resume_check_job_match(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            CheckResumeJobMatchRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "job": _job(_required(arguments, "job"), "job"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("check-resume-job-match", request, arguments)


async def resume_select_best(arguments: ToolArguments) -> ToolResult:
    try:
        resumes = [
            _resume(item, "resumes") for item in _object_list(arguments, "resumes")
        ]
        request = _make_request(
            SelectBestResumeRequest,
            {
                "resumes": resumes,
                "job": _job(_required(arguments, "job"), "job"),
                "labels": _optional_labels(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("select-best-resume", request, arguments)


async def resume_compare_versions(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            CompareResumeVersionsRequest,
            {
                "base": _resume(_required(arguments, "base"), "base"),
                "candidate": _resume(_required(arguments, "candidate"), "candidate"),
                "job": _job(_required(arguments, "job"), "job"),
                "base_label": _optional_string(arguments, "base_label", "base"),
                "candidate_label": _optional_string(
                    arguments,
                    "candidate_label",
                    "candidate",
                ),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("compare-resume-versions", request, arguments)


async def resume_identify_gaps(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            IdentifyResumeGapsRequest,
            {
                "job": _job(_required(arguments, "job"), "job"),
                "tailored": _resume(_required(arguments, "tailored"), "tailored"),
                "master": _resume(_required(arguments, "master"), "master"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("identify-resume-gaps", request, arguments)


async def resume_align(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            AlignResumeRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "job": _job(_required(arguments, "job"), "job"),
                "evidence": _optional_evidence_list(arguments, "evidence"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("align-resume", request, arguments)


async def resume_validate_truth(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            ValidateResumeTruthRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "evidence": _optional_evidence_list(arguments, "evidence") or [],
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("validate-resume-truth", request, arguments)


async def candidate_evidence_build(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            BuildCandidateEvidenceRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "approved_claims": _approved_claims(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("build-candidate-evidence", request, arguments)


async def resume_export(arguments: ToolArguments) -> ToolResult:
    store = _InMemoryArtifactStore()
    try:
        options = _options(arguments)
        request = _make_request(
            ExportResumeRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "format": _export_format(arguments, "format"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    response = await REGISTRY["export-resume"](
        request,
        CapabilityOptions(
            no_llm=options.no_llm,
            strict=options.strict,
            human_in_loop=options.human_in_loop,
            provider=options.provider,
            artifact_store=store,
        ),
    )
    result = _dump(response)
    if response.errors:
        return result
    ref = response.data
    if isinstance(ref, ArtifactRef):
        data = await store.get(ref.artifact_id)
        if isinstance(data, bytes):
            result["artifact_bytes_base64"] = base64.b64encode(data).decode("ascii")
    return result


HANDLERS: dict[str, ToolHandler] = {
    "resume_extract": resume_extract,
    "job_description_extract": job_description_extract,
    "resume_check_ats": resume_check_ats,
    "resume_check_job_match": resume_check_job_match,
    "resume_select_best": resume_select_best,
    "resume_compare_versions": resume_compare_versions,
    "resume_identify_gaps": resume_identify_gaps,
    "resume_align": resume_align,
    "resume_validate_truth": resume_validate_truth,
    "candidate_evidence_build": candidate_evidence_build,
    "resume_export": resume_export,
}
