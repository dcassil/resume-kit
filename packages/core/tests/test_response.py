"""Tests for InterfaceResponse envelope."""

from __future__ import annotations

from resume_kit_core.errors import CoreError, CoreWarning, ErrorCode, WarningCode
from resume_kit_core.response import InterfaceResponse, ProvenanceRef, Question
from resume_kit_core.storage import ArtifactRef


class TestInterfaceResponseConstruction:
    def test_empty_defaults(self) -> None:
        resp: InterfaceResponse[None] = InterfaceResponse()
        assert resp.data is None
        assert resp.warnings == []
        assert resp.errors == []
        assert resp.requires_human_input is False
        assert resp.questions == []
        assert resp.artifacts == []
        assert resp.provenance == []

    def test_with_data(self) -> None:
        resp: InterfaceResponse[dict[str, str]] = InterfaceResponse(
            data={"key": "value"}
        )
        assert resp.data == {"key": "value"}

    def test_ok_property_true(self) -> None:
        resp: InterfaceResponse[str] = InterfaceResponse(data="done")
        assert resp.ok is True

    def test_ok_property_false_when_errors(self) -> None:
        resp: InterfaceResponse[None] = InterfaceResponse(
            errors=[CoreError(code=ErrorCode.UNKNOWN, message="err")]
        )
        assert resp.ok is False

    def test_ok_property_false_when_requires_human_input(self) -> None:
        resp: InterfaceResponse[None] = InterfaceResponse(requires_human_input=True)
        assert resp.ok is False


class TestInterfaceResponseFactories:
    def test_success_factory(self) -> None:
        warn = CoreWarning(code=WarningCode.INCOMPLETE_DATA, message="missing email")
        resp = InterfaceResponse.success({"result": 42}, warnings=[warn])
        assert resp.ok is True
        assert resp.data == {"result": 42}
        assert len(resp.warnings) == 1

    def test_failure_factory(self) -> None:
        err = CoreError(code=ErrorCode.PROVIDER_UNAVAILABLE, message="down")
        resp = InterfaceResponse.failure([err])
        assert resp.ok is False
        assert resp.data is None
        assert resp.errors[0].code == ErrorCode.PROVIDER_UNAVAILABLE

    def test_needs_input_factory(self) -> None:
        q = Question(question_id="q1", text="What is your name?")
        resp = InterfaceResponse.needs_input([q])
        assert resp.requires_human_input is True
        assert resp.ok is False
        assert resp.questions[0].question_id == "q1"


class TestInterfaceResponseSerialization:
    def test_model_dump(self) -> None:
        resp: InterfaceResponse[dict[str, int]] = InterfaceResponse(
            data={"n": 1},
            warnings=[CoreWarning(code=WarningCode.HUMAN_REVIEW_SUGGESTED, message="check")],
        )
        d = resp.model_dump()
        assert d["data"] == {"n": 1}
        assert d["warnings"][0]["code"] == WarningCode.HUMAN_REVIEW_SUGGESTED.value

    def test_model_dump_json(self) -> None:
        resp: InterfaceResponse[str] = InterfaceResponse(data="hello")
        json_str = resp.model_dump_json()
        assert '"hello"' in json_str

    def test_with_artifacts(self) -> None:
        ref = ArtifactRef(artifact_id="a1", artifact_type="resume")
        resp: InterfaceResponse[None] = InterfaceResponse(artifacts=[ref])
        assert resp.artifacts[0].artifact_id == "a1"
        d = resp.model_dump()
        assert d["artifacts"][0]["artifact_id"] == "a1"

    def test_with_provenance(self) -> None:
        prov = ProvenanceRef(source_id="doc1", source_type="resume")
        resp: InterfaceResponse[None] = InterfaceResponse(provenance=[prov])
        d = resp.model_dump()
        assert d["provenance"][0]["source_id"] == "doc1"


class TestQuestion:
    def test_construction(self) -> None:
        q = Question(question_id="q1", text="What is your goal?", hint="e.g. software engineer")
        assert q.hint == "e.g. software engineer"
        assert q.metadata == {}

    def test_round_trip(self) -> None:
        q = Question(question_id="q2", text="Years of experience?")
        restored = Question.model_validate(q.model_dump())
        assert restored == q


class TestProvenanceRef:
    def test_construction(self) -> None:
        prov = ProvenanceRef(
            source_id="doc1",
            source_type="resume",
            field_path="work_experience[0].title",
        )
        assert prov.field_path == "work_experience[0].title"

    def test_round_trip(self) -> None:
        prov = ProvenanceRef(source_id="s1", source_type="llm_response")
        restored = ProvenanceRef.model_validate(prov.model_dump())
        assert restored == prov
