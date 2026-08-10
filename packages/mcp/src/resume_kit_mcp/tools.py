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
from resume_kit_facade import normalize_resume_input as _normalize_resume_input
from resume_kit_facade.capabilities import REGISTRY
from resume_kit_facade.models import (
    AddEvidenceRequest,
    AlignResumeRequest,
    AlignTerminologyRequest,
    AnalyzeBestPracticesRequest,
    AnalyzeShapeRequest,
    AtsViewRequest,
    BuildBaseRequest,
    BuildCandidateEvidenceRequest,
    BuildPerfectRequest,
    BuildRefineRequest,
    BuildStandardRequest,
    BuildStructureRequest,
    CapabilityOptions,
    CheckAtsStructureRequest,
    CheckResumeAtsRequest,
    CheckResumeJobMatchRequest,
    CommitSessionRequest,
    CompareResumeVersionsRequest,
    DecideChangeRequest,
    ExportResumeRequest,
    ExtractJobDescriptionRequest,
    ExtractResumeRequest,
    ExtractResumeTextRequest,
    IdentifyResumeGapsRequest,
    InitProjectRequest,
    OpenEditSessionRequest,
    RankEditCandidatesRequest,
    ReconcileSessionRequest,
    RecordEditFeedbackRequest,
    RefreshPreferencesRequest,
    SelectBestResumeRequest,
    SessionPromptRequest,
    SessionStatusRequest,
    SetActiveRequest,
    SuggestTerminologyRequest,
    ValidateFaithfulnessRequest,
    ValidateResumeTruthRequest,
)
from resume_kit_schemas import (
    EditFeedbackReasonCode,
    EvidenceKind,
    ReviewAction,
    UserPreferenceProfile,
)

ToolArguments = dict[str, object]
ToolResult = dict[str, object]
ToolHandler = Callable[[ToolArguments], Awaitable[ToolResult]]
ModelValidator = Callable[[object], object]

TOOL_NAMES: tuple[str, ...] = (
    "resume_extract",
    "resume_extract_text",
    "job_description_extract",
    "resume_check_ats",
    "resume_check_ats_structure",
    "resume_check_job_match",
    "resume_select_best",
    "resume_compare_versions",
    "resume_identify_gaps",
    "resume_align",
    "resume_validate_truth",
    "resume_validate_faithfulness",
    "candidate_evidence_build",
    "candidate_evidence_add",
    "edit_feedback_record",
    "edit_candidates_rank",
    "preferences_refresh",
    "edit_session_open",
    "edit_session_prompt",
    "edit_session_decide",
    "edit_session_commit",
    "edit_session_status",
    "edit_session_reconcile",
    "resume_export",
    "resume_suggest_terminology",
    "resume_align_terminology",
    "project_init",
    "project_set_active",
    "resume_build_base",
    "resume_analyze_shape",
    "resume_build_structure",
    "resume_build_standard",
    "resume_build_refine",
    "resume_build_perfect",
    "resume_analyze_best_practices",
    "resume_ats_view",
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
_VALIDATE_SUGGESTION = _model_validator(AlignTerminologyRequest, "suggestion")
_VALIDATE_FEEDBACK = _model_validator(RecordEditFeedbackRequest, "feedback")
_VALIDATE_PREFERENCE_PAIR = _model_validator(RecordEditFeedbackRequest, "preference_pair")
_VALIDATE_CANDIDATE = _model_validator(RankEditCandidatesRequest, "candidates")
_VALIDATE_FEATURE_CONTEXT = _model_validator(RankEditCandidatesRequest, "context")
_VALIDATE_CHANGE = _model_validator(OpenEditSessionRequest, "changes")
_VALIDATE_CLAIM_PROVENANCE = _model_validator(OpenEditSessionRequest, "claim_provenance")
_VALIDATE_SCORE_DELTA = _model_validator(OpenEditSessionRequest, "expected_score_deltas")


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


def _optional_alias_file(arguments: ToolArguments) -> str | None:
    value = arguments.get("alias_file")
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise _ValidationFailure("Field 'alias_file' must be a string.", field="alias_file")


def _export_format(arguments: ToolArguments, field: str) -> ExportFormat:
    value = _string(arguments, field)
    try:
        return ExportFormat(value)
    except ValueError as exc:
        raise _ValidationFailure(
            "Field 'format' must be one of: pdf, docx.",
            field=field,
        ) from exc


def _review_action(arguments: ToolArguments) -> ReviewAction:
    value = _string(arguments, "action")
    try:
        return ReviewAction(value)
    except ValueError as exc:
        raise _ValidationFailure(
            "Field 'action' must be a supported review action.",
            field="action",
        ) from exc


def _optional_feedback_reason(arguments: ToolArguments) -> EditFeedbackReasonCode | None:
    value = arguments.get("reason_code")
    if value is None:
        return None
    if not isinstance(value, str):
        raise _ValidationFailure("Field 'reason_code' must be a string.", field="reason_code")
    try:
        return EditFeedbackReasonCode(value)
    except ValueError as exc:
        raise _ValidationFailure(
            "Field 'reason_code' must be a supported edit-feedback reason.",
            field="reason_code",
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


def _resume_normalized(value: object, field: str) -> object:
    """Parse a resume that may be a canonical ``structure`` payload.

    Routes through the shared :func:`normalize_resume_input` seam so a canonical
    ``Resume`` payload is projected (bullets preserved) rather than leniently
    validated into an empty ``ResumeDocument`` (RIT-T-0163).
    """
    try:
        return _normalize_resume_input(value)
    except ValueError as exc:
        raise _ValidationFailure(str(exc), field=field) from exc


def _job(value: object, field: str) -> object:
    return _validated(_VALIDATE_JOB, value, field)


def _evidence(value: object, field: str) -> object:
    return _validated(_VALIDATE_EVIDENCE, value, field)


def _suggestion(value: object, field: str) -> object:
    return _validated(_VALIDATE_SUGGESTION, value, field)


def _optional_freedom(arguments: ToolArguments) -> int | None:
    value = arguments.get("freedom")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _ValidationFailure("Field 'freedom' must be an integer.", field="freedom")
    return value


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
    if isinstance(value, dict):
        value = value.get("data")
    if not isinstance(value, list):
        raise _ValidationFailure(f"Field '{field}' must be a list or envelope.", field=field)
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
    if isinstance(value, dict):
        value = value.get("data")
    if not isinstance(value, list):
        raise _ValidationFailure(
            "Field 'approved_claims' must be a list or envelope.",
            field="approved_claims",
        )
    if all(isinstance(item, str) for item in value):
        return [item for item in value if isinstance(item, str)]
    return [_evidence(item, "approved_claims") for item in value]


def _feedback(value: object, field: str) -> object:
    return _validated(_VALIDATE_FEEDBACK, value, field)


def _preference_pair(value: object, field: str) -> object:
    return _validated(_VALIDATE_PREFERENCE_PAIR, value, field)


def _candidate(value: object, field: str) -> object:
    return _validated(_VALIDATE_CANDIDATE, value, field)


def _feature_context(value: object, field: str) -> object:
    return _validated(_VALIDATE_FEATURE_CONTEXT, value, field)


def _change(value: object, field: str) -> object:
    return _validated(_VALIDATE_CHANGE, value, field)


def _claim_provenance(value: object, field: str) -> object:
    return _validated(_VALIDATE_CLAIM_PROVENANCE, value, field)


def _score_delta(value: object, field: str) -> object:
    return _validated(_VALIDATE_SCORE_DELTA, value, field)


def _preference_profile(arguments: ToolArguments) -> UserPreferenceProfile:
    value = arguments.get("profile")
    if value is None:
        return UserPreferenceProfile()
    try:
        return UserPreferenceProfile.model_validate(value)
    except ValueError as exc:
        raise _ValidationFailure(str(exc), field="profile") from exc


def _feedback_records(arguments: ToolArguments) -> list[object] | None:
    value = arguments.get("records")
    if value is None:
        return None
    if not isinstance(value, list):
        raise _ValidationFailure("Field 'records' must be a list.", field="records")
    return [_feedback(item, "records") for item in value]


def _evidence_kind(arguments: ToolArguments) -> EvidenceKind:
    value = _optional_string(arguments, "kind", EvidenceKind.USER_STATEMENT.value)
    try:
        return EvidenceKind(value)
    except ValueError as exc:
        allowed = ", ".join(item.value for item in EvidenceKind)
        raise _ValidationFailure(
            f"Field 'kind' must be one of: {allowed}.",
            field="kind",
        ) from exc


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


async def resume_extract_text(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            ExtractResumeTextRequest,
            {
                "content": _bytes(arguments, "content"),
                "filename": _string(arguments, "filename"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("extract-resume-text", request, arguments)


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
                "alias_file": _optional_alias_file(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("check-resume-ats", request, arguments)


async def resume_check_ats_structure(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            CheckAtsStructureRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("check-structure", request, arguments)


async def resume_check_job_match(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            CheckResumeJobMatchRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "job": _job(_required(arguments, "job"), "job"),
                "alias_file": _optional_alias_file(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("check-resume-job-match", request, arguments)


async def resume_select_best(arguments: ToolArguments) -> ToolResult:
    try:
        resumes = [_resume(item, "resumes") for item in _object_list(arguments, "resumes")]
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
    return await _call("select-resume", request, arguments)


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
    return await _call("compare-versions", request, arguments)


async def resume_identify_gaps(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            IdentifyResumeGapsRequest,
            {
                "job": _job(_required(arguments, "job"), "job"),
                "tailored": _resume(_required(arguments, "tailored"), "tailored"),
                "master": _resume(_required(arguments, "master"), "master"),
                "alias_file": _optional_alias_file(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("check-gaps", request, arguments)


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
                "alias_file": _optional_alias_file(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("validate-facts", request, arguments)


async def resume_validate_faithfulness(arguments: ToolArguments) -> ToolResult:
    try:
        fields: ToolArguments = {
            "resume": _resume(_required(arguments, "resume"), "resume"),
        }
        source_text = _optional_str(arguments, "source_text")
        if source_text is not None:
            fields["source_text"] = source_text
        else:
            fields["source_content"] = _bytes(arguments, "source_content")
            fields["source_filename"] = _optional_string(arguments, "source_filename", "source.txt")
        request = _make_request(ValidateFaithfulnessRequest, fields)
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("validate-faithfulness", request, arguments)


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
    return await _call("extract-evidence", request, arguments)


async def candidate_evidence_add(arguments: ToolArguments) -> ToolResult:
    try:
        if not _optional_bool(arguments, "confirmed"):
            raise _ValidationFailure(
                "Field 'confirmed' must be true to persist confirmed evidence.",
                field="confirmed",
            )
        tags_value = arguments.get("tags", [])
        if not isinstance(tags_value, list) or not all(
            isinstance(item, str) for item in tags_value
        ):
            raise _ValidationFailure("Field 'tags' must be a list of strings.", field="tags")
        request = _make_request(
            AddEvidenceRequest,
            {
                "content": _string(arguments, "content"),
                "kind": _evidence_kind(arguments),
                "tags": tags_value,
                "root": _optional_string(arguments, "root", "."),
                "evidence_file": _optional_string(
                    arguments,
                    "evidence_file",
                    "working/user-confirmed-evidence.json",
                ),
                "update_active": _optional_bool(arguments, "update_active"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("add-evidence", request, arguments)


async def edit_feedback_record(arguments: ToolArguments) -> ToolResult:
    try:
        preference_value = arguments.get("preference_pair")
        request = _make_request(
            RecordEditFeedbackRequest,
            {
                "feedback": _feedback(_required(arguments, "feedback"), "feedback"),
                "preference_pair": (
                    _preference_pair(preference_value, "preference_pair")
                    if preference_value is not None
                    else None
                ),
                "base_path": _optional_str(arguments, "base_path"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("record-edit-feedback", request, arguments)


async def edit_candidates_rank(arguments: ToolArguments) -> ToolResult:
    try:
        candidates = [
            _candidate(item, "candidates") for item in _object_list(arguments, "candidates")
        ]
        request = _make_request(
            RankEditCandidatesRequest,
            {
                "candidates": candidates,
                "context": _feature_context(_required(arguments, "context"), "context"),
                "profile": _preference_profile(arguments),
                "alias_file": _optional_alias_file(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("rank-edit-candidates", request, arguments)


async def preferences_refresh(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            RefreshPreferencesRequest,
            {
                "now": _string(arguments, "now"),
                "records": _feedback_records(arguments),
                "base_path": _optional_str(arguments, "base_path"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("refresh-preferences", request, arguments)


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


async def resume_suggest_terminology(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            SuggestTerminologyRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "job": _job(_required(arguments, "job"), "job"),
                "alias_file": _optional_alias_file(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("suggest-terminology", request, arguments)


async def resume_align_terminology(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            AlignTerminologyRequest,
            {
                "suggestion": _suggestion(_required(arguments, "suggestion"), "suggestion"),
                "location": _string(arguments, "location"),
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "job": _job(_required(arguments, "job"), "job"),
                "evidence": _optional_evidence_list(arguments, "evidence") or (),
                "freedom": _optional_freedom(arguments),
                "alias_file": _optional_alias_file(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("align-terminology", request, arguments)


def _optional_str(arguments: ToolArguments, field: str) -> str | None:
    value = arguments.get(field)
    if value is None:
        return None
    if isinstance(value, str):
        return value
    raise _ValidationFailure(f"Field '{field}' must be a string.", field=field)


async def project_init(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            InitProjectRequest,
            {"root": _optional_string(arguments, "root", ".")},
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("init-project", request, arguments)


async def project_set_active(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            SetActiveRequest,
            {
                "resume": _optional_str(arguments, "resume"),
                "resume_source": _optional_str(arguments, "resume_source"),
                "job": _optional_str(arguments, "job"),
                "job_source": _optional_str(arguments, "job_source"),
                "root": _optional_string(arguments, "root", "."),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("set-active", request, arguments)


def _optional_string_map(arguments: ToolArguments, field: str) -> dict[str, str] | None:
    value = arguments.get(field)
    if value is None:
        return None
    if not isinstance(value, dict):
        raise _ValidationFailure(f"Field '{field}' must be an object.", field=field)
    items: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise _ValidationFailure(
                f"Field '{field}' must map strings to strings.", field=field
            )
        items[key] = item
    return items


def _optional_answers(arguments: ToolArguments) -> dict[str, str] | None:
    return _optional_string_map(arguments, "answers")


async def resume_build_base(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            BuildBaseRequest,
            {
                "root": _optional_string(arguments, "root", "."),
                "mode": _optional_string(arguments, "mode", "auto"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("build-base", request, arguments)


async def resume_build_standard(arguments: ToolArguments) -> ToolResult:
    """Deprecated alias for resume_build_refine."""
    try:
        request = _make_request(
            BuildStandardRequest,
            {
                "root": _optional_string(arguments, "root", "."),
                "answers": _optional_answers(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("build-standard", request, arguments)


async def resume_build_refine(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            BuildRefineRequest,
            {
                "root": _optional_string(arguments, "root", "."),
                "answers": _optional_answers(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("build-refine", request, arguments)


async def resume_build_perfect(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            BuildPerfectRequest,
            {
                "root": _optional_string(arguments, "root", "."),
                "job": _optional_str(arguments, "job"),
                "decisions": _optional_string_map(arguments, "decisions"),
                "auto_fit": _optional_bool(arguments, "auto_fit"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("fit", request, arguments)


async def resume_analyze_shape(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            AnalyzeShapeRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "root": _optional_string(arguments, "root", "."),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("analyze-shape", request, arguments)


async def resume_build_structure(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            BuildStructureRequest,
            {
                "root": _optional_string(arguments, "root", "."),
                "answers": _optional_answers(arguments),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("build-structure", request, arguments)


async def resume_analyze_best_practices(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            AnalyzeBestPracticesRequest,
            {
                "resume": _resume_normalized(_required(arguments, "resume"), "resume"),
                "resume_version": _optional_str(arguments, "resume_version"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("analyze-best-practices", request, arguments)


async def resume_ats_view(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            AtsViewRequest,
            {
                "resume": _resume(_required(arguments, "resume"), "resume"),
                "reference_date": _optional_str(arguments, "reference_date"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("ats-view", request, arguments)


async def edit_session_open(arguments: ToolArguments) -> ToolResult:
    try:
        changes = [_change(item, "changes") for item in _object_list(arguments, "changes")]
        claim_value = arguments.get("claim_provenance", [])
        if not isinstance(claim_value, list):
            raise _ValidationFailure(
                "Field 'claim_provenance' must be a list.",
                field="claim_provenance",
            )
        delta_value = arguments.get("expected_score_deltas", [])
        if not isinstance(delta_value, list):
            raise _ValidationFailure(
                "Field 'expected_score_deltas' must be a list.",
                field="expected_score_deltas",
            )
        request = _make_request(
            OpenEditSessionRequest,
            {
                "mode": _string(arguments, "mode"),
                "changes": changes,
                "root": _optional_string(arguments, "root", "."),
                "evidence": _optional_evidence_list(arguments, "evidence") or [],
                "claim_provenance": [
                    _claim_provenance(item, "claim_provenance") for item in claim_value
                ],
                "expected_score_deltas": [
                    _score_delta(item, "expected_score_deltas") for item in delta_value
                ],
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("open-edit-session", request, arguments)


async def edit_session_prompt(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            SessionPromptRequest,
            {"root": _optional_string(arguments, "root", ".")},
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("session-prompt", request, arguments)


async def edit_session_decide(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            DecideChangeRequest,
            {
                "path": _string(arguments, "path"),
                "action": _review_action(arguments),
                "reason_code": _optional_feedback_reason(arguments),
                "note": _optional_str(arguments, "note"),
                "root": _optional_string(arguments, "root", "."),
                "edited_content": _optional_str(arguments, "edited_content"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("decide-change", request, arguments)


async def edit_session_commit(arguments: ToolArguments) -> ToolResult:
    try:
        freedom = _optional_freedom(arguments)
        request = _make_request(
            CommitSessionRequest,
            {
                "root": _optional_string(arguments, "root", "."),
                "freedom": 10 if freedom is None else freedom,
                "alias_timestamp": _optional_str(arguments, "alias_timestamp"),
            },
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("commit-session", request, arguments)


async def edit_session_status(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            SessionStatusRequest,
            {"root": _optional_string(arguments, "root", ".")},
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("session-status", request, arguments)


async def edit_session_reconcile(arguments: ToolArguments) -> ToolResult:
    try:
        request = _make_request(
            ReconcileSessionRequest,
            {"root": _optional_string(arguments, "root", ".")},
        )
    except _ValidationFailure as exc:
        return _validation_error(exc)
    return await _call("reconcile-session", request, arguments)


HANDLERS: dict[str, ToolHandler] = {
    "resume_extract": resume_extract,
    "resume_extract_text": resume_extract_text,
    "job_description_extract": job_description_extract,
    "resume_check_ats": resume_check_ats,
    "resume_check_ats_structure": resume_check_ats_structure,
    "resume_check_job_match": resume_check_job_match,
    "resume_select_best": resume_select_best,
    "resume_compare_versions": resume_compare_versions,
    "resume_identify_gaps": resume_identify_gaps,
    "resume_align": resume_align,
    "resume_validate_truth": resume_validate_truth,
    "resume_validate_faithfulness": resume_validate_faithfulness,
    "candidate_evidence_build": candidate_evidence_build,
    "candidate_evidence_add": candidate_evidence_add,
    "edit_feedback_record": edit_feedback_record,
    "edit_candidates_rank": edit_candidates_rank,
    "preferences_refresh": preferences_refresh,
    "edit_session_open": edit_session_open,
    "edit_session_prompt": edit_session_prompt,
    "edit_session_decide": edit_session_decide,
    "edit_session_commit": edit_session_commit,
    "edit_session_status": edit_session_status,
    "edit_session_reconcile": edit_session_reconcile,
    "resume_export": resume_export,
    "resume_suggest_terminology": resume_suggest_terminology,
    "resume_align_terminology": resume_align_terminology,
    "project_init": project_init,
    "project_set_active": project_set_active,
    "resume_build_base": resume_build_base,
    "resume_analyze_shape": resume_analyze_shape,
    "resume_build_structure": resume_build_structure,
    "resume_build_standard": resume_build_standard,
    "resume_build_refine": resume_build_refine,
    "resume_build_perfect": resume_build_perfect,
    "resume_analyze_best_practices": resume_analyze_best_practices,
    "resume_ats_view": resume_ats_view,
}
