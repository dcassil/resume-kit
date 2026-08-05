"""Envelope-shape tests for every Resume Kit API endpoint.

Each endpoint is exercised in-process via FastAPI's ``TestClient`` (backed by
httpx) with deterministic, no-network, no-LLM input.  The tests assert the
canonical :class:`InterfaceResponse` envelope shape is returned and that
warnings are kept separate from errors.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from resume_kit_api.app import create_app
from resume_kit_feedback import Candidate, FeatureContext
from resume_kit_schemas import (
    CandidateEvidence,
    EditFeedback,
    EditFeedbackReasonCode,
    EvidenceKind,
    JobDescription,
    ResumeDocument,
)

client = TestClient(create_app())


def _job() -> dict[str, Any]:
    return {
        "title": "Backend Engineer",
        "company": "Acme",
        "requirements": [{"text": "Python experience", "kind": "required", "keywords": ["python"]}],
    }


def _resume() -> dict[str, Any]:
    return {"summary": "Python engineer with Docker experience."}


_ENVELOPE_KEYS = {
    "data",
    "warnings",
    "errors",
    "requires_human_input",
    "questions",
    "artifacts",
    "provenance",
}


def _assert_envelope(payload: dict[str, Any]) -> None:
    assert set(payload) >= _ENVELOPE_KEYS
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["errors"], list)
    assert isinstance(payload["questions"], list)
    # Warnings are a distinct channel from errors.
    assert payload["warnings"] is not payload["errors"]


def test_extract_deterministic() -> None:
    resp = client.post("/extract", json={"content": "Jane Doe\nPython Engineer", "no_llm": True})
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_extract_job_deterministic() -> None:
    resp = client.post(
        "/extract-job", json={"raw_text": "Backend Engineer at Acme", "no_llm": True}
    )
    assert resp.status_code == 200
    payload = resp.json()
    _assert_envelope(payload)
    assert payload["data"] is not None


def test_check_ats() -> None:
    resp = client.post("/check-ats", json={"resume": _resume(), "job": _job()})
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_match() -> None:
    resp = client.post("/match", json={"resume": _resume(), "job": _job()})
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_select() -> None:
    resp = client.post("/select", json={"resumes": [_resume(), _resume()], "job": _job()})
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_compare() -> None:
    resp = client.post(
        "/compare",
        json={"base": _resume(), "candidate": _resume(), "job": _job()},
    )
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_identify_gaps() -> None:
    resp = client.post(
        "/identify-gaps",
        json={"job": _job(), "tailored": _resume(), "master": _resume()},
    )
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_align_deterministic() -> None:
    resp = client.post("/align", json={"resume": _resume(), "job": _job(), "no_llm": True})
    assert resp.status_code == 200
    payload = resp.json()
    _assert_envelope(payload)
    assert payload["data"] is not None


def test_validate_truth() -> None:
    resp = client.post("/validate-truth", json={"resume": _resume(), "evidence": []})
    assert resp.status_code == 200
    payload = resp.json()
    _assert_envelope(payload)
    assert payload["data"]["needs_evidence_count"] >= 1
    assert payload["data"]["claims"][0]["reason_code"] == "missing_evidence"


def test_build_evidence() -> None:
    resp = client.post("/build-evidence", json={"resume": _resume()})
    assert resp.status_code == 200
    payload = resp.json()
    _assert_envelope(payload)
    assert isinstance(payload["data"], list)


def _feedback() -> dict[str, Any]:
    return EditFeedback(
        edit_id="edit-1",
        resume_id="resume-1",
        job_id="job-1",
        section="summary",
        edit_type="keyword_substitution",
        original_text="Built APIs.",
        proposed_text="Built Python APIs.",
        final_text=None,
        predicted_ats_gain=2.0,
        confidence=0.8,
        outcome="rejected",
        reason_code=EditFeedbackReasonCode.NOT_MY_VOICE,
        timestamp="2026-08-05T00:00:00+00:00",
    ).model_dump(mode="json")


def test_feedback_and_evidence_routes(tmp_path: Path) -> None:
    record = client.post(
        "/record-edit-feedback",
        json={"feedback": _feedback(), "base_path": str(tmp_path / "resume-kit")},
    )
    assert record.status_code == 200
    _assert_envelope(record.json())

    refresh = client.post(
        "/refresh-preferences",
        json={
            "now": "2026-08-05T00:00:00+00:00",
            "base_path": str(tmp_path / "resume-kit"),
        },
    )
    assert refresh.status_code == 200
    _assert_envelope(refresh.json())

    context = FeatureContext(
        resume=ResumeDocument(summary="Python engineer."),
        job=JobDescription(raw_text="Docker"),
        evidence=[
            CandidateEvidence(
                id="ev-docker",
                kind=EvidenceKind.SKILL,
                content="Docker",
                user_confirmed=True,
            )
        ],
    )
    rank = client.post(
        "/rank-edit-candidates",
        json={
            "candidates": [
                Candidate(candidate_id="c1", section="skill", proposed_text="Docker").model_dump(
                    mode="json"
                )
            ],
            "context": context.model_dump(mode="json"),
        },
    )
    assert rank.status_code == 200
    payload = rank.json()
    _assert_envelope(payload)
    assert len(payload["data"]["ranked"]) == 1

    add = client.post(
        "/add-evidence",
        json={
            "confirmed": True,
            "root": str(tmp_path),
            "content": "Confirmed Docker work",
            "kind": "user_statement",
            "tags": ["Docker"],
            "update_active": True,
        },
    )
    assert add.status_code == 200
    add_payload = add.json()
    _assert_envelope(add_payload)
    assert add_payload["data"]["evidence"]["user_confirmed"] is True


def test_review_edits_routes_registered() -> None:
    paths = {route.path for route in client.app.routes}
    assert {
        "/review-edits/open",
        "/review-edits/prompt",
        "/review-edits/decide",
        "/review-edits/commit",
        "/review-edits/status",
        "/review-edits/reconcile",
    }.issubset(paths)


def test_build_evidence_approved_claims_envelope_feeds_validate_truth() -> None:
    built = client.post(
        "/build-evidence",
        json={"resume": _resume(), "approved_claims": ["Confirmed Docker work"]},
    )
    assert built.status_code == 200
    envelope = built.json()
    validate = client.post(
        "/validate-truth",
        json={"resume": _resume(), "evidence": {"data": envelope["data"]}},
    )
    assert validate.status_code == 200
    _assert_envelope(validate.json())


def test_body_validation_error_is_422() -> None:
    # Missing required fields -> FastAPI request validation (not the envelope).
    resp = client.post("/check-ats", json={})
    assert resp.status_code == 422


def test_export_pdf_returns_pdf_bytes() -> None:
    resp = client.post("/export", json={"resume": _resume(), "format": "pdf"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert "attachment" in resp.headers["content-disposition"]
    assert resp.headers["x-artifact-id"]
    assert resp.content.startswith(b"%PDF-")


def test_export_docx_returns_docx_bytes() -> None:
    resp = client.post("/export", json={"resume": _resume(), "format": "docx"})
    assert resp.status_code == 200
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    # DOCX is a zip container -> "PK" local-file-header signature.
    assert resp.content.startswith(b"PK")


def test_export_invalid_format_is_422() -> None:
    # Unknown format value -> FastAPI request validation (not the envelope).
    resp = client.post("/export", json={"resume": _resume(), "format": "rtf"})
    assert resp.status_code == 422
