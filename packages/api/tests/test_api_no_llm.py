"""No-LLM deterministic-path tests for the Resume Kit API.

Confirms that every LLM-capable endpoint succeeds without a provider when the
caller opts into the deterministic path via ``no_llm``, entirely in-process
with no network and no LLM.
"""

from __future__ import annotations

from fastapi.testclient import TestClient
from resume_kit_api.app import create_app

client = TestClient(create_app())

_RESUME = {"summary": "Python engineer with Docker experience."}
_JOB = {
    "title": "Backend Engineer",
    "company": "Acme",
    "requirements": [
        {"text": "Python experience", "kind": "required", "keywords": ["python"]}
    ],
}


def test_extract_no_llm_succeeds() -> None:
    resp = client.post(
        "/extract", json={"content": "Jane Doe\nPython Engineer", "no_llm": True}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    # Deterministic text-only extraction returns no structured document but
    # surfaces the reason as a warning (kept separate from errors).
    assert payload["data"] is None
    assert any(
        w["code"] == "provider_fallback_used" for w in payload["warnings"]
    )


def test_extract_job_no_llm_succeeds() -> None:
    resp = client.post(
        "/extract-job", json={"raw_text": "Backend Engineer at Acme", "no_llm": True}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["errors"] == []
    assert payload["data"]["title"]


def test_export_no_provider_succeeds() -> None:
    # Export is deterministic: it renders bytes with no provider configured.
    resp = client.post(
        "/export", json={"resume": _RESUME, "format": "pdf", "no_llm": True}
    )
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content.startswith(b"%PDF-")


def test_align_no_llm_is_no_change() -> None:
    resp = client.post(
        "/align", json={"resume": _RESUME, "job": _JOB, "no_llm": True}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["errors"] == []
    assert payload["data"]["aligned_resume"]["summary"] == _RESUME["summary"]
