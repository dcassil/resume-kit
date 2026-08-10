"""Tests for the shared interface result-shaping substrate."""

from __future__ import annotations

from resume_kit_core.errors import (
    CoreError,
    CoreWarning,
    ErrorCode,
    ResumeKitError,
    WarningCode,
)
from resume_kit_core.interface import (
    ExitCode,
    build_needs_input,
    build_provider_not_configured,
    build_success,
    exit_code_for,
    from_exception,
    from_resume_kit_error,
)
from resume_kit_core.response import InterfaceResponse, ProvenanceRef, Question
from resume_kit_core.storage import ArtifactRef


class TestBuildSuccess:
    def test_preserves_warnings_artifacts_provenance(self) -> None:
        warn = CoreWarning(code=WarningCode.INCOMPLETE_DATA, message="w")
        art = ArtifactRef(artifact_id="a1", artifact_type="resume")
        prov = ProvenanceRef(source_id="s1", source_type="resume")
        resp = build_success(
            {"score": "0.9"},
            warnings=[warn],
            artifacts=[art],
            provenance=[prov],
        )
        assert resp.ok is True
        assert resp.data == {"score": "0.9"}
        assert resp.warnings == [warn]
        assert resp.artifacts == [art]
        assert resp.provenance == [prov]
        assert resp.errors == []

    def test_strict_no_warnings_stays_success(self) -> None:
        resp = build_success({"x": "y"}, strict=True)
        assert resp.ok is True
        assert resp.errors == []

    def test_strict_with_warnings_escalates_to_failure(self) -> None:
        warn = CoreWarning(code=WarningCode.TRUNCATED_OUTPUT, message="cut")
        resp = build_success({"x": "y"}, warnings=[warn], strict=True)
        assert resp.ok is False
        assert len(resp.errors) == 1
        assert resp.errors[0].code == ErrorCode.VALIDATION_FAILED
        assert resp.warnings == [warn]
        assert exit_code_for(resp) == ExitCode.INVALID_INPUT


class TestProviderNotConfigured:
    def test_maps_to_provider_not_configured(self) -> None:
        resp = build_provider_not_configured()
        assert resp.ok is False
        assert resp.errors[0].code == ErrorCode.PROVIDER_NOT_CONFIGURED
        assert exit_code_for(resp) == ExitCode.PROVIDER_NOT_CONFIGURED

    def test_serialized_error_code_is_stable(self) -> None:
        assert ErrorCode.PROVIDER_NOT_CONFIGURED.value == "provider_not_configured"
        # Distinct from generic provider-unavailable.
        assert (
            ErrorCode.PROVIDER_NOT_CONFIGURED.value
            != ErrorCode.PROVIDER_UNAVAILABLE.value
        )
        resp = build_provider_not_configured()
        dumped = resp.model_dump()
        assert dumped["errors"][0]["code"] == "provider_not_configured"


class TestErrorMapping:
    def test_resume_kit_error_preserves_code(self) -> None:
        exc = ResumeKitError.from_code(
            ErrorCode.ARTIFACT_NOT_FOUND, "missing"
        )
        resp = from_resume_kit_error(exc)
        assert resp.errors[0].code == ErrorCode.ARTIFACT_NOT_FOUND
        assert resp.errors[0].message == "missing"

    def test_generic_exception_maps_to_internal_error(self) -> None:
        resp = from_exception(ValueError("secret token abc123"))
        assert resp.errors[0].code == ErrorCode.INTERNAL_ERROR
        # No content/secret leakage.
        assert "secret" not in resp.errors[0].message
        assert "abc123" not in str(resp.model_dump())
        assert resp.errors[0].details["exception_type"] == "ValueError"
        assert exit_code_for(resp) == ExitCode.INTERNAL_ERROR

    def test_validation_error_maps_to_validation_not_internal(self) -> None:
        """RIT-T-0156 B2: a pydantic ValidationError in the build path must
        surface as a validation-class error naming the offending field, not the
        opaque internal_error."""
        from pydantic import BaseModel, ValidationError

        class _Model(BaseModel):
            organization: str

        try:
            _Model.model_validate({"organization": 123})
        except ValidationError as exc:
            resp = from_exception(exc)

        assert resp.errors[0].code == ErrorCode.VALIDATION_FAILED
        assert resp.errors[0].code != ErrorCode.INTERNAL_ERROR
        # The message names the offending field/entry.
        assert "organization" in resp.errors[0].message
        assert exit_code_for(resp) == ExitCode.INVALID_INPUT


class TestNeedsInput:
    def test_human_input_response(self) -> None:
        q = Question(question_id="q1", text="Which role?")
        resp = build_needs_input([q])
        assert resp.requires_human_input is True
        assert resp.questions == [q]
        assert resp.ok is False
        assert exit_code_for(resp) == ExitCode.HUMAN_INPUT_REQUIRED


class TestExitCodeSelection:
    def test_ok(self) -> None:
        assert exit_code_for(build_success({"a": "b"})) == ExitCode.OK

    def test_warnings_alone_are_zero(self) -> None:
        warn = CoreWarning(code=WarningCode.INCOMPLETE_DATA, message="w")
        resp = build_success({"a": "b"}, warnings=[warn])
        assert exit_code_for(resp) == ExitCode.OK
        assert exit_code_for(resp) == 0

    def test_invalid_input(self) -> None:
        resp = InterfaceResponse.failure(
            [CoreError(code=ErrorCode.INVALID_INPUT, message="bad")]
        )
        assert exit_code_for(resp) == ExitCode.INVALID_INPUT

    def test_provider_unavailable(self) -> None:
        resp = InterfaceResponse.failure(
            [CoreError(code=ErrorCode.PROVIDER_UNAVAILABLE, message="down")]
        )
        assert exit_code_for(resp) == ExitCode.PROVIDER_UNAVAILABLE

    def test_unknown_error_maps_to_internal(self) -> None:
        resp = InterfaceResponse.failure(
            [CoreError(code=ErrorCode.UNKNOWN, message="?")]
        )
        assert exit_code_for(resp) == ExitCode.INTERNAL_ERROR
