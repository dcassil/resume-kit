"""Provider-not-configured tests for the LLM-requiring endpoints.

The HTTP transport never constructs a provider, so calling an LLM-requiring
endpoint (``/extract``, ``/extract-job``, ``/align``) without ``no_llm`` must
return the stable provider-not-configured structured error inside the envelope,
never a crash.  Per the documented status policy that maps to ``501``, while
the envelope body is returned intact.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from resume_kit_api.app import create_app
from resume_kit_core.errors import ErrorCode

client = TestClient(create_app())

_RESUME = {"summary": "Python engineer with Docker experience."}
_JOB = {
    "title": "Backend Engineer",
    "company": "Acme",
    "requirements": [
        {"text": "Python experience", "kind": "required", "keywords": ["python"]}
    ],
}


def _assert_provider_not_configured(status_code: int, payload: dict[str, Any]) -> None:
    assert status_code == 501
    assert payload["data"] is None
    assert payload["errors"], "expected a structured error in the envelope"
    codes = {e["code"] for e in payload["errors"]}
    assert ErrorCode.PROVIDER_NOT_CONFIGURED.value in codes
    # Envelope stays intact: warnings channel is present and separate.
    assert isinstance(payload["warnings"], list)


def test_extract_without_provider() -> None:
    resp = client.post("/extract", json={"content": "Jane Doe\nPython Engineer"})
    _assert_provider_not_configured(resp.status_code, resp.json())


def test_extract_job_without_provider() -> None:
    resp = client.post("/extract-job", json={"raw_text": "Backend Engineer at Acme"})
    _assert_provider_not_configured(resp.status_code, resp.json())


def test_align_without_provider() -> None:
    resp = client.post("/align", json={"resume": _RESUME, "job": _JOB})
    _assert_provider_not_configured(resp.status_code, resp.json())
