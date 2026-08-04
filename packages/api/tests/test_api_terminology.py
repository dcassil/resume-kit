"""API tests for the terminology-alignment routes (RIT-I-0010).

``POST /suggest-terminology`` lists alias-hit mirror suggestions and
``POST /align-terminology`` applies exactly one accepted suggestion at one
location, returning the updated resume + before/after delta. Both are thin
adapters over the facade; the k8s/Kubernetes seed alias drives the suggestion.
"""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from resume_kit_api.app import create_app

client = TestClient(create_app())


def _resume() -> dict[str, Any]:
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


def _job() -> dict[str, Any]:
    return {
        "title": "Platform Engineer",
        "summary": "Kubernetes platform role.",
        "requirements": [{"text": "k8s", "keywords": ["k8s"]}],
        "keywords": ["k8s"],
    }


def _suggestion() -> dict[str, Any]:
    return {
        "jd_keyword": "k8s",
        "current_wording": "kubernetes",
        "locations": ["workExperience[0].description[0]"],
        "canonical": "kubernet",
    }


def test_suggest_terminology_lists_alias_hit() -> None:
    resp = client.post(
        "/suggest-terminology", json={"resume": _resume(), "job": _job()}
    )
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["errors"] == []
    assert any(s["jd_keyword"] == "k8s" for s in payload["data"])


def test_align_terminology_applies_one_suggestion() -> None:
    resp = client.post(
        "/align-terminology",
        json={
            "suggestion": _suggestion(),
            "location": "workExperience[0].description[0]",
            "resume": _resume(),
            "job": _job(),
        },
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["swap_applied"] is True
    assert data["freedom"] == 4
    assert (
        data["resume"]["workExperience"][0]["description"][0]
        == "Ran workloads on k8s across three regions."
    )


def test_align_terminology_missing_location_is_422() -> None:
    resp = client.post(
        "/align-terminology",
        json={"suggestion": _suggestion(), "resume": _resume(), "job": _job()},
    )
    assert resp.status_code == 422
