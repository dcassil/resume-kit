"""MCP tool tests for terminology alignment (RIT-I-0010).

``resume_suggest_terminology`` lists alias-hit mirror suggestions and
``resume_align_terminology`` applies exactly one accepted suggestion at one
location, returning the updated resume + before/after delta. Both are thin
adapters over the facade; the k8s/Kubernetes seed alias drives the suggestion.
"""

from __future__ import annotations

from resume_kit_mcp.tools import HANDLERS


def _resume() -> dict[str, object]:
    return {
        "personalInfo": {"name": "Sam Rivera"},
        "summary": "Platform engineer.",
        "workExperience": [
            {
                "id": 1,
                "title": "Platform Engineer",
                "company": "Northwind Ltd",
                "years": "2019-2024",
                "description": ["Ran workloads on Kubernetes across three regions."],
            }
        ],
        "additional": {"technicalSkills": ["Python", "Kubernetes"]},
    }


def _job() -> dict[str, object]:
    return {
        "title": "Platform Engineer",
        "summary": "Kubernetes platform role.",
        "requirements": [{"text": "k8s", "keywords": ["k8s"]}],
        "keywords": ["k8s"],
    }


def _suggestion() -> dict[str, object]:
    return {
        "jd_keyword": "k8s",
        "current_wording": "kubernetes",
        "locations": ["workExperience[0].description[0]"],
        "canonical": "kubernet",
    }


async def test_suggest_terminology_lists_alias_hit() -> None:
    payload = await HANDLERS["resume_suggest_terminology"](
        {"resume": _resume(), "job": _job()}
    )
    assert payload["errors"] == []
    data = payload["data"]
    assert isinstance(data, list)
    assert any(s["jd_keyword"] == "k8s" for s in data)


async def test_align_terminology_applies_one_suggestion() -> None:
    payload = await HANDLERS["resume_align_terminology"](
        {
            "suggestion": _suggestion(),
            "location": "workExperience[0].description[0]",
            "resume": _resume(),
            "job": _job(),
        }
    )
    assert payload["errors"] == []
    data = payload["data"]
    assert isinstance(data, dict)
    assert data["swap_applied"] is True
    assert data["freedom"] == 4
    assert (
        data["resume"]["workExperience"][0]["description"][0]
        == "Ran workloads on k8s across three regions."
    )


async def test_align_terminology_missing_location_is_validation_error() -> None:
    payload = await HANDLERS["resume_align_terminology"](
        {"suggestion": _suggestion(), "resume": _resume(), "job": _job()}
    )
    assert payload["errors"]
    assert payload["errors"][0]["details"]["field"] == "location"
