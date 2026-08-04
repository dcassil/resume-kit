from __future__ import annotations

from resume_kit_mcp.tools import HANDLERS


def _resume() -> dict[str, object]:
    return {
        "summary": "Backend engineer with Python experience.",
        "workExperience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "description": ["Built Python services."],
            }
        ],
        "additional": {"technicalSkills": ["Python"]},
    }


def _job() -> dict[str, object]:
    return {
        "title": "Backend Engineer",
        "requirements": [
            {"text": "Python", "kind": "required", "keywords": ["Python"]}
        ],
        "keywords": ["Python"],
    }


async def test_resume_extract_no_llm_succeeds_without_provider() -> None:
    payload = await HANDLERS["resume_extract"](
        {"content": "Jane Dev\nPython", "filename": "resume.txt", "no_llm": True}
    )

    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    assert payload["warnings"]


async def test_job_description_extract_no_llm_succeeds_without_provider() -> None:
    payload = await HANDLERS["job_description_extract"](
        {"raw_text": "Backend Engineer\nPython required", "no_llm": True}
    )

    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    data = payload["data"]
    assert isinstance(data, dict)
    assert data["title"] == "Backend Engineer"


async def test_resume_align_no_llm_succeeds_without_provider() -> None:
    payload = await HANDLERS["resume_align"](
        {"resume": _resume(), "job": _job(), "no_llm": True}
    )

    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    data = payload["data"]
    assert isinstance(data, dict)
    assert data["original_resume"] == data["aligned_resume"]


async def test_resume_export_succeeds_without_provider() -> None:
    payload = await HANDLERS["resume_export"](
        {"resume": _resume(), "format": "pdf", "no_llm": True}
    )

    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    assert isinstance(payload["data"], dict)
    assert isinstance(payload["artifact_bytes_base64"], str)
