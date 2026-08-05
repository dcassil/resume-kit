from __future__ import annotations

import base64

import pytest
from resume_kit_core.testing import FakeStructuredCompletionProvider
from resume_kit_mcp.server import TOOLS
from resume_kit_mcp.tools import HANDLERS, TOOL_NAMES


def _resume(
    summary: str = "Python engineer with Docker experience.",
) -> dict[str, object]:
    return {
        "personalInfo": {
            "name": "Jane Dev",
            "email": "jane@example.com",
            "phone": "555-1000",
        },
        "summary": summary,
        "workExperience": [
            {
                "title": "Engineer",
                "company": "Acme",
                "years": "2020-2024",
                "description": ["Built Python APIs with Docker."],
            }
        ],
        "additional": {"technicalSkills": ["Python", "Docker"]},
    }


def _job() -> dict[str, object]:
    return {
        "title": "Backend Engineer",
        "company": "Acme",
        "requirements": [
            {
                "text": "Python experience",
                "kind": "required",
                "keywords": ["Python"],
            }
        ],
        "keywords": ["Python", "Docker"],
    }


def _assert_envelope(payload: dict[str, object]) -> None:
    assert set(payload) == {
        "data",
        "warnings",
        "errors",
        "requires_human_input",
        "questions",
        "artifacts",
        "provenance",
    }
    assert isinstance(payload["warnings"], list)
    assert isinstance(payload["errors"], list)
    assert isinstance(payload["requires_human_input"], bool)
    assert isinstance(payload["questions"], list)
    assert isinstance(payload["artifacts"], list)
    assert isinstance(payload["provenance"], list)


def _assert_export_envelope(payload: dict[str, object]) -> None:
    assert set(payload) == {
        "data",
        "warnings",
        "errors",
        "requires_human_input",
        "questions",
        "artifacts",
        "provenance",
        "artifact_bytes_base64",
    }
    assert isinstance(payload["artifact_bytes_base64"], str)
    canonical = {
        key: payload[key] for key in payload if key != "artifact_bytes_base64"
    }
    _assert_envelope(canonical)


def test_registers_exactly_the_stable_tools() -> None:
    expected = {
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
        "resume_export",
        "resume_suggest_terminology",
        "resume_align_terminology",
        "project_init",
        "project_set_active",
    }
    assert set(TOOL_NAMES) == expected
    assert set(HANDLERS) == expected
    assert {tool.name for tool in TOOLS} == expected


@pytest.mark.parametrize(
    ("name", "arguments", "data_kind"),
    [
        (
            "resume_extract",
            {"content": b"Jane Dev\nPython Engineer", "filename": "cv.txt"},
            type(None),
        ),
        ("job_description_extract", {"raw_text": "Backend Engineer\nPython"}, dict),
        ("resume_check_ats", {"resume": _resume(), "job": _job()}, dict),
        ("resume_check_job_match", {"resume": _resume(), "job": _job()}, dict),
        (
            "resume_select_best",
            {"resumes": [_resume(), _resume("Generalist.")], "job": _job()},
            dict,
        ),
        (
            "resume_compare_versions",
            {"base": _resume(), "candidate": _resume(), "job": _job()},
            dict,
        ),
        (
            "resume_identify_gaps",
            {"job": _job(), "tailored": _resume(), "master": _resume()},
            dict,
        ),
        ("resume_align", {"resume": _resume(), "job": _job()}, dict),
        ("resume_validate_truth", {"resume": _resume(), "evidence": []}, dict),
        ("candidate_evidence_build", {"resume": _resume()}, list),
    ],
)
async def test_each_deterministic_tool_returns_json_envelope(
    name: str,
    arguments: dict[str, object],
    data_kind: type[object],
) -> None:
    arguments["no_llm"] = True
    payload = await HANDLERS[name](arguments)

    _assert_envelope(payload)
    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    assert isinstance(payload["data"], data_kind)


async def test_warnings_remain_separate_from_errors() -> None:
    payload = await HANDLERS["resume_extract"](
        {"content": b"Jane Dev\nPython Engineer", "filename": "cv.txt", "no_llm": True}
    )

    _assert_envelope(payload)
    warnings = payload["warnings"]
    assert isinstance(warnings, list)
    assert warnings
    assert payload["errors"] == []


async def test_validate_truth_returns_reason_code_fields() -> None:
    payload = await HANDLERS["resume_validate_truth"](
        {"resume": _resume(), "evidence": [], "no_llm": True}
    )

    _assert_envelope(payload)
    data = payload["data"]
    assert isinstance(data, dict)
    assert data["needs_evidence_count"] >= 1
    assert data["claims"][0]["reason_code"] == "missing_evidence"


async def test_resume_align_human_in_loop_surfaces_questions_without_advancing() -> None:
    provider = FakeStructuredCompletionProvider(
        [
            {
                "changes": [
                    {
                        "path": "summary",
                        "action": "replace",
                        "original": "Python engineer with Docker experience.",
                        "value": "Python engineer with Docker experience.",
                        "reason": "No-op review gate test.",
                    }
                ]
            }
        ]
    )

    payload = await HANDLERS["resume_align"](
        {
            "resume": _resume(),
            "job": _job(),
            "provider": provider,
            "human_in_loop": True,
        }
    )

    _assert_envelope(payload)
    assert payload["errors"] == []
    assert payload["requires_human_input"] is True
    assert payload["questions"]
    data = payload["data"]
    assert isinstance(data, dict)
    review_state = data["review_state"]
    assert isinstance(review_state, dict)
    assert review_state["current_section"] == "summary"
    assert review_state["decisions"] == []


@pytest.mark.parametrize(
    ("format_value", "signature"),
    [
        ("pdf", b"%PDF-"),
        ("docx", b"PK"),
    ],
)
async def test_resume_export_returns_envelope_metadata_and_base64_bytes(
    format_value: str,
    signature: bytes,
) -> None:
    payload = await HANDLERS["resume_export"](
        {"resume": _resume(), "format": format_value}
    )

    _assert_export_envelope(payload)
    assert payload["errors"] == []
    assert payload["requires_human_input"] is False
    data = payload["data"]
    artifacts = payload["artifacts"]
    assert isinstance(data, dict)
    assert isinstance(artifacts, list)
    assert len(artifacts) == 1
    artifact = artifacts[0]
    assert isinstance(artifact, dict)
    assert data["artifact_id"] == artifact["artifact_id"]
    assert data["artifact_type"] == "resume"
    assert artifact["metadata"] == {"format": format_value}
    raw = base64.b64decode(str(payload["artifact_bytes_base64"]))
    assert raw.startswith(signature)


async def test_resume_export_rejects_invalid_format() -> None:
    payload = await HANDLERS["resume_export"]({"resume": _resume(), "format": "html"})

    _assert_envelope(payload)
    assert payload["data"] is None
    assert payload["errors"]
    error = payload["errors"][0]
    assert isinstance(error, dict)
    assert error["code"] == "invalid_input"
    assert error["details"] == {"field": "format"}
