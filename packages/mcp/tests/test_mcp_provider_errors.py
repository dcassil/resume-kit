from __future__ import annotations

import pytest
from resume_kit_mcp.tools import HANDLERS


def _resume() -> dict[str, object]:
    return {"summary": "Python engineer."}


def _job() -> dict[str, object]:
    return {"title": "Backend Engineer"}


@pytest.mark.parametrize(
    ("name", "arguments", "capability"),
    [
        (
            "resume_extract",
            {"content": b"Jane Dev", "filename": "resume.txt"},
            "extract-resume",
        ),
        (
            "job_description_extract",
            {"raw_text": "Backend Engineer"},
            "extract-job-description",
        ),
        (
            "resume_align",
            {"resume": _resume(), "job": _job()},
            "align-resume",
        ),
    ],
)
async def test_llm_requiring_tools_without_provider_return_structured_error(
    name: str,
    arguments: dict[str, object],
    capability: str,
) -> None:
    payload = await HANDLERS[name](arguments)

    assert payload["data"] is None
    assert payload["warnings"] == []
    assert payload["requires_human_input"] is False
    assert payload["questions"] == []
    errors = payload["errors"]
    assert isinstance(errors, list)
    assert len(errors) == 1
    assert errors[0]["code"] == "provider_not_configured"
    assert errors[0]["details"] == {"capability": capability}

