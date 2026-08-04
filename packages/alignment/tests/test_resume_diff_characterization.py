"""Characterization tests for deterministic resume diff behavior."""

from __future__ import annotations

from collections.abc import Mapping

from resume_kit_alignment.diff import calculate_resume_diff
from resume_kit_schemas.change import Diff, ResumeDiffSummary


def _values(changes: list[Diff], field_type: str, change_type: str) -> list[str | None]:
    return [
        c.new_value if change_type == "added" else c.original_value
        for c in changes
        if c.field_type == field_type and c.change_type == change_type
    ]


def test_returns_schema_diff_summary_and_diff_values() -> None:
    summary, changes = calculate_resume_diff({}, {"summary": "New summary."})

    assert isinstance(summary, ResumeDiffSummary)
    assert all(isinstance(change, Diff) for change in changes)


def test_summary_added_removed_modified_and_unchanged() -> None:
    added_summary, added = calculate_resume_diff({"summary": ""}, {"summary": "New."})
    removed_summary, removed = calculate_resume_diff({"summary": "Old."}, {"summary": ""})
    modified_summary, modified = calculate_resume_diff(
        {"summary": "Old."}, {"summary": "New."}
    )
    unchanged_summary, unchanged = calculate_resume_diff(
        {"summary": "Same."}, {"summary": "Same."}
    )

    assert [c.change_type for c in added if c.field_type == "summary"] == ["added"]
    assert [c.change_type for c in removed if c.field_type == "summary"] == ["removed"]
    assert [c.change_type for c in modified if c.field_type == "summary"] == ["modified"]
    assert [c for c in unchanged if c.field_type == "summary"] == []
    assert added_summary.total_changes == 1
    assert removed_summary.total_changes == 1
    assert modified_summary.total_changes == 1
    assert unchanged_summary.total_changes == 0


def test_skill_add_remove_case_insensitive_and_order_ignored() -> None:
    original = {"additional": {"technicalSkills": ["Python", "React"]}}
    improved = {"additional": {"technicalSkills": ["python", "Go"]}}

    summary, changes = calculate_resume_diff(original, improved)

    assert _values(changes, "skill", "added") == ["Go"]
    assert _values(changes, "skill", "removed") == ["React"]
    assert summary.skills_added == 1
    assert summary.skills_removed == 1
    assert summary.high_risk_changes == 1

    reordered_summary, reordered = calculate_resume_diff(
        {"additional": {"technicalSkills": ["Go", "Python"]}},
        {"additional": {"technicalSkills": ["Python", "Go"]}},
    )
    assert [c for c in reordered if c.field_type == "skill"] == []
    assert reordered_summary.skills_added == 0
    assert reordered_summary.skills_removed == 0


def test_certification_language_and_award_changes() -> None:
    original = {
        "additional": {
            "certificationsTraining": ["AWS SAA", "CKA"],
            "languages": ["English"],
            "awards": [],
        }
    }
    improved = {
        "additional": {
            "certificationsTraining": ["AWS SAA", "Security+"],
            "languages": ["English", "Spanish"],
            "awards": ["Employee of the Year 2022"],
        }
    }

    summary, changes = calculate_resume_diff(original, improved)

    assert _values(changes, "certification", "added") == ["Security+"]
    assert _values(changes, "certification", "removed") == ["CKA"]
    assert _values(changes, "language", "added") == ["Spanish"]
    assert _values(changes, "award", "added") == ["Employee of the Year 2022"]
    assert summary.certifications_added == 1


def test_language_order_is_ignored() -> None:
    _, changes = calculate_resume_diff(
        {"additional": {"languages": ["English", "Spanish"]}},
        {"additional": {"languages": ["Spanish", "English"]}},
    )

    assert [c for c in changes if c.field_type == "language"] == []


def test_description_changes_and_modified_count() -> None:
    original = {"workExperience": [{"description": ["Built APIs", "Led team"]}]}
    improved = {"workExperience": [{"description": ["Built APIs", "Led squad"]}]}

    summary, changes = calculate_resume_diff(original, improved)

    description_changes = [
        c for c in changes if c.field_type == "description" and c.change_type == "modified"
    ]
    assert len(description_changes) == 1
    assert description_changes[0].original_value == "Led team"
    assert description_changes[0].new_value == "Led squad"
    assert summary.descriptions_modified == 1


def test_handles_malformed_lists_gracefully() -> None:
    original = {
        "additional": {"technicalSkills": ["Python", {"name": "Go"}, None, 123]},
        "workExperience": [{"description": "Not a list"}],
    }
    improved = {"additional": {"technicalSkills": ["Python"]}}

    summary, changes = calculate_resume_diff(original, improved)

    assert _values(changes, "skill", "removed") == ["Go"]
    assert summary.skills_removed == 1


def test_experience_education_and_project_entry_changes() -> None:
    original: Mapping[str, object] = {
        "workExperience": [
            {"title": "Dev", "company": "A", "location": "NY", "years": "2020"},
        ],
        "education": [],
        "personalProjects": [{"name": "Tool", "role": "Creator", "years": "2021"}],
    }
    improved: Mapping[str, object] = {
        "workExperience": [
            {"title": "Dev", "company": "A", "location": "Remote", "years": "2020"},
            {"title": "Senior", "company": "B", "years": "2022"},
        ],
        "education": [{"institution": "MIT", "degree": "BS", "years": "2020"}],
        "personalProjects": [],
    }

    _, changes = calculate_resume_diff(original, improved)

    assert [
        c.change_type for c in changes if c.field_type == "experience"
    ] == ["modified", "added"]
    assert [c.change_type for c in changes if c.field_type == "education"] == ["added"]
    assert [c.change_type for c in changes if c.field_type == "project"] == ["removed"]


def test_education_description_change_is_not_duplicated() -> None:
    original = {
        "education": [
            {
                "institution": "MIT",
                "degree": "B.S. CS",
                "years": "2014 - 2018",
                "description": "Graduated with honors",
            }
        ]
    }
    improved = {
        "education": [
            {
                "institution": "MIT",
                "degree": "B.S. CS",
                "years": "2014 - 2018",
                "description": "Graduated with honors; focus on distributed systems",
            }
        ]
    }

    _, changes = calculate_resume_diff(original, improved)

    education_changes = [c for c in changes if c.field_type == "education"]
    assert len(education_changes) == 1
    assert education_changes[0].field_path == "education[0].description"
    assert education_changes[0].change_type == "modified"
