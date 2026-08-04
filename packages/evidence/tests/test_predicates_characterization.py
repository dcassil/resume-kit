"""Characterization tests for predicates.py — locking upstream scorer behavior.

Each test encodes an observable behavior from upstream
apps/backend/tests/evals/scorers.py so future divergence is caught immediately.
"""

from __future__ import annotations

from typing import Any

from resume_kit_evidence.predicates import (
    flatten_resume_text,
    no_fabricated_employers,
    personal_info_unchanged,
    sections_preserved,
)


def _resume(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "personalInfo": {"name": "Ada Lovelace", "email": "ada@example.com"},
        "summary": "Engineer.",
        "workExperience": [{"company": "Acme", "title": "Dev", "description": ["Built"]}],
        "education": [{"degree": "BSc", "institution": "MIT"}],
        "personalProjects": [],
        "additional": {"technicalSkills": ["Python"]},
    }
    base.update(overrides)
    return base


# sections_preserved ----------------------------------------------------------


def test_sections_preserved_true_when_all_survive() -> None:
    assert sections_preserved(_resume(), _resume()) is True


def test_sections_preserved_false_when_populated_section_dropped() -> None:
    tailored = _resume(workExperience=[])
    assert sections_preserved(_resume(), tailored) is False


def test_sections_preserved_ignores_originally_empty_section() -> None:
    original = _resume(summary="")
    tailored = _resume(summary="")
    assert sections_preserved(original, tailored) is True


def test_sections_preserved_additional_all_empty_counts_empty() -> None:
    original = _resume(additional={"technicalSkills": []})
    tailored = _resume(additional={})
    assert sections_preserved(original, tailored) is True


# no_fabricated_employers -----------------------------------------------------


def test_no_fabricated_employers_empty_when_truthful() -> None:
    assert no_fabricated_employers(_resume(), _resume()) == []


def test_no_fabricated_employers_detects_new_company() -> None:
    tailored = _resume(
        workExperience=[
            {"company": "Acme"},
            {"company": "Globex"},
        ]
    )
    assert no_fabricated_employers(_resume(), tailored) == ["Globex"]


def test_no_fabricated_employers_case_insensitive_and_trimmed() -> None:
    tailored = _resume(workExperience=[{"company": "  acme  "}])
    assert no_fabricated_employers(_resume(), tailored) == []


def test_no_fabricated_employers_dedupes_repeats() -> None:
    tailored = _resume(
        workExperience=[{"company": "Globex"}, {"company": "globex"}]
    )
    assert no_fabricated_employers(_resume(), tailored) == ["Globex"]


# personal_info_unchanged -----------------------------------------------------


def test_personal_info_unchanged_true_when_identical() -> None:
    assert personal_info_unchanged(_resume(), _resume()) is True


def test_personal_info_unchanged_false_when_edited() -> None:
    tailored = _resume(personalInfo={"name": "Alan Turing"})
    assert personal_info_unchanged(_resume(), tailored) is False


def test_personal_info_unchanged_missing_treated_as_empty() -> None:
    original = {"summary": "x"}
    tailored = {"summary": "y"}
    assert personal_info_unchanged(original, tailored) is True


# flatten_resume_text ---------------------------------------------------------


def test_flatten_resume_text_lowercases_and_includes_nested() -> None:
    text = flatten_resume_text(_resume())
    assert "ada lovelace" in text
    assert "python" in text
    assert "built" in text
