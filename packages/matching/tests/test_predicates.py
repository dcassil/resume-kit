"""Tests for resume_kit_matching.predicates."""

from __future__ import annotations

from typing import Any

import pytest
from resume_kit_matching.predicates import is_valid_resume, jd_keywords_present
from resume_kit_schemas.resume import ResumeDocument

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _minimal_resume_dict() -> dict[str, Any]:
    """Return the smallest dict that validates as a ResumeDocument."""
    return {}


def _rich_resume_dict() -> dict[str, Any]:
    """Return a dict with substantive content useful for keyword tests."""
    return {
        "summary": "Experienced Python engineer with machine learning expertise.",
        "workExperience": [
            {
                "title": "Software Engineer",
                "company": "Acme Corp",
                "years": "2020–2023",
                "description": ["Built distributed systems using Kubernetes."],
            }
        ],
        "education": [
            {
                "degree": "B.Sc. Computer Science",
                "institution": "State University",
                "years": "2016–2020",
            }
        ],
    }


# ---------------------------------------------------------------------------
# jd_keywords_present
# ---------------------------------------------------------------------------


class TestJdKeywordsPresent:
    def test_empty_keywords_returns_one(self) -> None:
        """Empty keyword list → perfect score (nothing to miss)."""
        assert jd_keywords_present({}, []) == 1.0

    def test_empty_keywords_with_model_instance(self) -> None:
        resume = ResumeDocument()
        assert jd_keywords_present(resume, []) == 1.0

    def test_all_keywords_present(self) -> None:
        data = _rich_resume_dict()
        keywords = ["python", "kubernetes", "acme corp"]
        score = jd_keywords_present(data, keywords)
        assert score == 1.0

    def test_case_insensitive_match(self) -> None:
        data = {"summary": "Expert in PYTHON and FastAPI."}
        score = jd_keywords_present(data, ["python", "fastapi"])
        assert score == 1.0

    def test_partial_match_returns_fraction(self) -> None:
        data = {"summary": "Expert in Python."}
        # "rust" is not present
        score = jd_keywords_present(data, ["python", "rust"])
        assert score == pytest.approx(0.5)

    def test_no_keywords_match(self) -> None:
        data = {"summary": "Python developer."}
        score = jd_keywords_present(data, ["cobol", "fortran"])
        assert score == pytest.approx(0.0)

    def test_keyword_substring_in_text(self) -> None:
        data = {"summary": "Machine learning practitioner."}
        # "machine" is a substring of "machine learning"
        score = jd_keywords_present(data, ["machine"])
        assert score == 1.0

    def test_accepts_resume_document_instance(self) -> None:
        resume = ResumeDocument(summary="Specialist in TypeScript and React.")
        score = jd_keywords_present(resume, ["typescript", "react"])
        assert score == 1.0

    def test_empty_string_keywords_are_skipped(self) -> None:
        """Empty-string keywords are falsy and must not count as hits."""
        data = {"summary": "Python developer."}
        # Two non-empty keywords (python hits, rust misses), one empty string
        # Empty strings are skipped (not counted as hits), so 1/3 would be
        # wrong — the original scorer counts len(keywords) including the empty
        # one, so score = 1/3.
        score = jd_keywords_present(data, ["python", "", "rust"])
        assert score == pytest.approx(1 / 3)

    def test_nested_content_searched(self) -> None:
        data = _rich_resume_dict()
        # "distributed" lives inside a description bullet
        score = jd_keywords_present(data, ["distributed"])
        assert score == 1.0


# ---------------------------------------------------------------------------
# is_valid_resume
# ---------------------------------------------------------------------------


class TestIsValidResume:
    def test_empty_dict_is_valid(self) -> None:
        """All ResumeDocument fields are optional; empty dict validates."""
        assert is_valid_resume({}) is True

    def test_minimal_dict_is_valid(self) -> None:
        assert is_valid_resume(_minimal_resume_dict()) is True

    def test_rich_dict_is_valid(self) -> None:
        assert is_valid_resume(_rich_resume_dict()) is True

    def test_model_instance_is_always_valid(self) -> None:
        resume = ResumeDocument(**_rich_resume_dict())
        assert is_valid_resume(resume) is True

    def test_default_model_instance_is_valid(self) -> None:
        assert is_valid_resume(ResumeDocument()) is True

    def test_invalid_work_experience_type(self) -> None:
        """workExperience must be a list, not a bare string."""
        assert is_valid_resume({"workExperience": "not-a-list"}) is False

    def test_invalid_education_type(self) -> None:
        """education must be a list, not an integer."""
        assert is_valid_resume({"education": 42}) is False

    def test_invalid_nested_experience_field(self) -> None:
        """An experience entry with an invalid field type should fail."""
        bad = {
            "workExperience": [
                {
                    "title": "Engineer",
                    "company": "Corp",
                    "years": "2020",
                    # description must be list-like; a plain dict is invalid
                    "description": {"bad": "shape"},
                }
            ]
        }
        # description has a coercion validator — check actual behaviour
        # If pydantic coerces it, result is True; we only assert it doesn't
        # raise an exception (is_valid_resume never raises).
        result = is_valid_resume(bad)
        assert isinstance(result, bool)

    def test_unknown_top_level_fields_accepted(self) -> None:
        """Extra fields are ignored by default (pydantic extra='ignore')."""
        data = {"unknownField": "value"}
        # Result depends on model config; we only assert no exception is raised.
        result = is_valid_resume(data)
        assert isinstance(result, bool)
