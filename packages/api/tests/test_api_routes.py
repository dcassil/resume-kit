"""Envelope-shape tests for every Resume Kit API endpoint.

Each endpoint is exercised in-process via FastAPI's ``TestClient`` (backed by
httpx) with deterministic, no-network, no-LLM input.  The tests assert the
canonical :class:`InterfaceResponse` envelope shape is returned and that
warnings are kept separate from errors.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from resume_kit_api.app import create_app

client = TestClient(create_app())


def _job() -> dict[str, Any]:
    return {
        "title": "Backend Engineer",
        "company": "Acme",
        "requirements": [
            {"text": "Python experience", "kind": "required", "keywords": ["python"]}
        ],
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
    resp = client.post(
        "/extract", json={"content": "Jane Doe\nPython Engineer", "no_llm": True}
    )
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
    resp = client.post(
        "/select", json={"resumes": [_resume(), _resume()], "job": _job()}
    )
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
    resp = client.post(
        "/align", json={"resume": _resume(), "job": _job(), "no_llm": True}
    )
    assert resp.status_code == 200
    payload = resp.json()
    _assert_envelope(payload)
    assert payload["data"] is not None


def test_validate_truth() -> None:
    resp = client.post(
        "/validate-truth", json={"resume": _resume(), "evidence": []}
    )
    assert resp.status_code == 200
    _assert_envelope(resp.json())


def test_build_evidence() -> None:
    resp = client.post("/build-evidence", json={"resume": _resume()})
    assert resp.status_code == 200
    payload = resp.json()
    _assert_envelope(payload)
    assert isinstance(payload["data"], list)


def test_body_validation_error_is_422() -> None:
    # Missing required fields -> FastAPI request validation (not the envelope).
    resp = client.post("/check-ats", json={})
    assert resp.status_code == 422
