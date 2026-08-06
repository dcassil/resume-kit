"""MCP tool tests for check-structure (RIT-T-0077)."""

from __future__ import annotations

from resume_kit_mcp.tools import HANDLERS


def _complete_resume() -> dict[str, object]:
    return {
        "personalInfo": {
            "name": "Sam Rivera",
            "email": "sam@example.com",
            "phone": "555-0100",
        },
        "summary": "Platform engineer.",
        "workExperience": [
            {
                "id": 1,
                "title": "Platform Engineer",
                "company": "Northwind Ltd",
                "years": "2019-2024",
                "description": ["Ran production workloads across three regions."],
            }
        ],
        "additional": {"technicalSkills": ["Python", "Kubernetes"]},
    }


async def test_check_ats_structure_reports_section_completeness() -> None:
    payload = await HANDLERS["resume_check_ats_structure"](
        {"resume": _complete_resume()}
    )
    assert payload["errors"] == []
    data = payload["data"]
    assert isinstance(data, dict)
    assert data["section_completeness"] == 75.0
    assert isinstance(data["recommendations"], list)
    assert "keyword_match" not in data
    assert "overall_score" not in data


async def test_check_ats_structure_missing_resume_is_validation_error() -> None:
    payload = await HANDLERS["resume_check_ats_structure"]({})
    assert payload["errors"]
    assert payload["errors"][0]["details"]["field"] == "resume"
