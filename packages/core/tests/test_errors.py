"""Tests for error and warning value types."""

from __future__ import annotations

import pytest
from resume_kit_core.errors import (
    CoreError,
    CoreWarning,
    ErrorCode,
    ResumeKitError,
    WarningCode,
)


class TestCoreError:
    def test_construction_minimal(self) -> None:
        err = CoreError(code=ErrorCode.UNKNOWN, message="something failed")
        assert err.code == ErrorCode.UNKNOWN
        assert err.message == "something failed"
        assert err.details == {}

    def test_construction_with_details(self) -> None:
        err = CoreError(
            code=ErrorCode.PROVIDER_TIMEOUT,
            message="timed out",
            details={"timeout_seconds": 30},
        )
        assert err.details["timeout_seconds"] == 30

    def test_serialization_round_trip(self) -> None:
        err = CoreError(
            code=ErrorCode.VALIDATION_FAILED,
            message="bad data",
            details={"field": "name"},
        )
        data = err.model_dump()
        restored = CoreError.model_validate(data)
        assert restored == err

    def test_json_round_trip(self) -> None:
        err = CoreError(code=ErrorCode.INTERNAL_ERROR, message="oops")
        json_str = err.model_dump_json()
        restored = CoreError.model_validate_json(json_str)
        assert restored == err

    def test_all_error_codes_are_strings(self) -> None:
        for code in ErrorCode:
            assert isinstance(code.value, str)


class TestCoreWarning:
    def test_construction(self) -> None:
        warn = CoreWarning(
            code=WarningCode.INCOMPLETE_DATA,
            message="missing phone number",
        )
        assert warn.code == WarningCode.INCOMPLETE_DATA
        assert warn.details == {}

    def test_serialization_round_trip(self) -> None:
        warn = CoreWarning(
            code=WarningCode.TRUNCATED_OUTPUT,
            message="output was truncated",
            details={"max_tokens": 8192},
        )
        restored = CoreWarning.model_validate(warn.model_dump())
        assert restored == warn


class TestResumeKitError:
    def test_wraps_core_error(self) -> None:
        inner = CoreError(code=ErrorCode.ARTIFACT_NOT_FOUND, message="gone")
        exc = ResumeKitError(inner)
        assert exc.error is inner
        assert str(exc) == "gone"

    def test_from_code_factory(self) -> None:
        exc = ResumeKitError.from_code(
            ErrorCode.PROVIDER_UNAVAILABLE,
            "service down",
            details={"url": "http://example.com"},
        )
        assert exc.error.code == ErrorCode.PROVIDER_UNAVAILABLE
        assert exc.error.details["url"] == "http://example.com"

    def test_is_exception(self) -> None:
        exc = ResumeKitError.from_code(ErrorCode.UNKNOWN, "x")
        with pytest.raises(ResumeKitError):
            raise exc
