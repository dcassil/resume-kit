"""API tests for the check-structure route (RIT-T-0077)."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient
from resume_kit_api.app import create_app

client = TestClient(create_app())


def _complete_resume() -> dict[str, Any]:
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


def test_check_ats_structure_reports_section_completeness() -> None:
    resp = client.post("/check-structure", json={"resume": _complete_resume()})
    assert resp.status_code == 200
    payload = resp.json()
    assert payload["errors"] == []
    data = payload["data"]
    assert data["section_completeness"] == 75.0
    assert isinstance(data["recommendations"], list)
    assert "keyword_match" not in data
    assert "overall_score" not in data


def test_check_ats_structure_missing_resume_is_422() -> None:
    resp = client.post("/check-structure", json={})
    assert resp.status_code == 422
