"""Characterization tests for keywords.py — locking upstream behavior.

Each test encodes an observable behavior from the upstream refiner.py so that
any future divergence is caught immediately.
"""

from __future__ import annotations

from typing import Any

import pytest
from resume_kit_matching.keywords import (
    _keyword_in_text,
    analyze_keyword_gaps,
    calculate_keyword_match,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resume_dict(**overrides: Any) -> dict[str, Any]:
    """Minimal camelCase resume dict, optionally overridden."""
    base: dict[str, Any] = {
        "summary": "",
        "workExperience": [],
        "education": [],
        "personalProjects": [],
        "additional": {},
        "customSections": {},
    }
    base.update(overrides)
    return base


def _jd_keywords(
    *,
    required: list[str] | None = None,
    preferred: list[str] | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "keywords": keywords or [],
    }


# ---------------------------------------------------------------------------
# _keyword_in_text — whole-term boundary matching
# ---------------------------------------------------------------------------


class TestKeywordInText:
    """SVC-010: term-boundary semantics must NOT match sub-strings."""

    def test_exact_match(self) -> None:
        assert _keyword_in_text("python", "I know python well") is True

    def test_case_insensitive(self) -> None:
        assert _keyword_in_text("Python", "proficient in PYTHON") is True

    def test_multi_word_keyword(self) -> None:
        assert _keyword_in_text("machine learning", "background in machine learning") is True

    def test_substring_does_not_match(self) -> None:
        # "go" must not match inside "going"
        assert _keyword_in_text("go", "going to the store") is False

    def test_python_does_not_match_pythonic(self) -> None:
        assert _keyword_in_text("python", "pythonic code style") is False

    def test_empty_keyword_returns_false(self) -> None:
        assert _keyword_in_text("", "any text") is False

    def test_keyword_with_only_whitespace_returns_false(self) -> None:
        assert _keyword_in_text("   ", "any text") is False

    def test_keyword_at_start_of_string(self) -> None:
        assert _keyword_in_text("rust", "rust is my favorite language") is True

    def test_keyword_at_end_of_string(self) -> None:
        assert _keyword_in_text("rust", "favorite language is rust") is True

    def test_keyword_not_present(self) -> None:
        assert _keyword_in_text("kotlin", "I know java and scala") is False


# ---------------------------------------------------------------------------
# calculate_keyword_match
# ---------------------------------------------------------------------------


class TestCalculateKeywordMatch:
    def test_empty_keywords_returns_zero(self) -> None:
        """SVC-009: empty keyword set → 0 %, not 100 %."""
        resume = _resume_dict(summary="I know everything")
        assert calculate_keyword_match(resume, _jd_keywords()) == pytest.approx(0.0)

    def test_all_matched_returns_100(self) -> None:
        resume = _resume_dict(summary="python java sql")
        jd = _jd_keywords(required=["python", "java", "sql"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(100.0)

    def test_none_matched_returns_zero(self) -> None:
        resume = _resume_dict(summary="excel word powerpoint")
        jd = _jd_keywords(required=["python", "java"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(0.0)

    def test_partial_match(self) -> None:
        resume = _resume_dict(summary="python is great")
        jd = _jd_keywords(required=["python", "java"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(50.0)

    def test_deduplication_across_buckets(self) -> None:
        """Same keyword in required + preferred counts once."""
        resume = _resume_dict(summary="python developer")
        jd = _jd_keywords(required=["python"], preferred=["python"])
        # set collapses to 1 keyword; it is matched → 100 %
        assert calculate_keyword_match(resume, jd) == pytest.approx(100.0)

    def test_substring_not_counted(self) -> None:
        """'go' in 'going' must not count as a match."""
        resume = _resume_dict(summary="going to the store")
        jd = _jd_keywords(required=["go"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(0.0)

    def test_skills_extracted_from_work_experience(self) -> None:
        resume = _resume_dict(
            workExperience=[
                {"title": "Engineer", "company": "Acme", "description": ["used python daily"]}
            ]
        )
        jd = _jd_keywords(required=["python"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(100.0)

    def test_skills_extracted_from_additional(self) -> None:
        resume = _resume_dict(additional={"technicalSkills": ["rust", "go"]})
        jd = _jd_keywords(required=["rust"])
        assert calculate_keyword_match(resume, jd) == pytest.approx(100.0)


# ---------------------------------------------------------------------------
# analyze_keyword_gaps
# ---------------------------------------------------------------------------


class TestAnalyzeKeywordGaps:
    def test_no_missing_keywords(self) -> None:
        tailored = _resume_dict(summary="python java sql")
        master = _resume_dict(summary="python java sql")
        jd = _jd_keywords(required=["python", "java", "sql"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.missing_keywords == []
        assert result.injectable_keywords == []
        assert result.non_injectable_keywords == []
        assert result.current_match_percentage == pytest.approx(100.0)
        assert result.potential_match_percentage == pytest.approx(100.0)

    def test_injectable_split(self) -> None:
        """Keywords in master but not in tailored → injectable."""
        tailored = _resume_dict(summary="java sql")
        master = _resume_dict(summary="python java sql")  # has python
        jd = _jd_keywords(required=["python", "java", "sql"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert "python" in result.missing_keywords
        assert "python" in result.injectable_keywords
        assert result.non_injectable_keywords == []

    def test_non_injectable_split(self) -> None:
        """Keywords absent from both tailored and master → non-injectable."""
        tailored = _resume_dict(summary="java sql")
        master = _resume_dict(summary="java sql")  # no python
        jd = _jd_keywords(required=["python", "java", "sql"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert "python" in result.missing_keywords
        assert "python" in result.non_injectable_keywords
        assert result.injectable_keywords == []

    def test_current_match_percentage(self) -> None:
        tailored = _resume_dict(summary="java sql")
        master = _resume_dict(summary="python java sql")
        jd = _jd_keywords(required=["python", "java", "sql"])
        result = analyze_keyword_gaps(jd, tailored, master)
        # 2 of 3 present in tailored → 66.67 %
        assert result.current_match_percentage == pytest.approx(200 / 3)

    def test_potential_match_percentage(self) -> None:
        tailored = _resume_dict(summary="java sql")
        master = _resume_dict(summary="python java sql")
        jd = _jd_keywords(required=["python", "java", "sql"])
        result = analyze_keyword_gaps(jd, tailored, master)
        # python is injectable → 0 non-injectable → potential = 100 %
        assert result.potential_match_percentage == pytest.approx(100.0)

    def test_near_identical_inputs_emit_warning(self) -> None:
        """Identical tailored/master → degeneracy warning (RIT-T-0126)."""
        tailored = _resume_dict(summary="java sql")
        master = _resume_dict(summary="java sql")
        jd = _jd_keywords(required=["python", "java", "sql"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert len(result.warnings) == 1
        assert "near-identical" in result.warnings[0].lower()

    def test_distinct_inputs_emit_no_warning(self) -> None:
        """Clearly distinct tailored/master → no false-positive warning."""
        tailored = _resume_dict(summary="java sql")
        master = _resume_dict(summary="python golang rust kubernetes docker")
        jd = _jd_keywords(required=["python", "java", "sql"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.warnings == []

    def test_sentence_requirement_excluded_from_denominator(self) -> None:
        """RIT-T-0128: prose requirement text must not depress the match score.

        A JobDescription whose only requirements are one concrete skill and one
        full sentence should score against the single concrete token, not two.
        """
        from resume_kit_schemas import JobDescription, Requirement, RequirementKind

        jd = JobDescription(
            title="Engineer",
            requirements=[
                Requirement(text="Python", kind=RequirementKind.REQUIRED),
                Requirement(
                    text=(
                        "4-6+ years of professional experience building modern, "
                        "large-scale web applications"
                    ),
                    kind=RequirementKind.REQUIRED,
                ),
            ],
        )
        resume = _resume_dict(summary="python")
        # Only the concrete "Python" token is scored → full coverage, not 50%.
        assert calculate_keyword_match(resume, jd) == pytest.approx(100.0)

    def test_empty_keyword_set_returns_zero_current(self) -> None:
        tailored = _resume_dict(summary="python")
        master = _resume_dict(summary="python")
        result = analyze_keyword_gaps(_jd_keywords(), tailored, master)
        # all_jd_keywords empty → total=1 (guard), missing=0 → current=100%
        # (upstream: (1-0)/1*100)
        assert result.current_match_percentage == pytest.approx(100.0)

    def test_keywords_bucket_included(self) -> None:
        """The 'keywords' bucket is included alongside required/preferred."""
        tailored = _resume_dict(summary="docker")
        master = _resume_dict(summary="docker kubernetes")
        jd = _jd_keywords(keywords=["docker", "kubernetes"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert "kubernetes" in result.missing_keywords
        assert "kubernetes" in result.injectable_keywords

    def test_custom_section_text_extraction(self) -> None:
        """Text from customSections is extracted and matched."""
        tailored = _resume_dict(
            customSections={
                "certifications": {
                    "sectionType": "text",
                    "text": "AWS Certified Solutions Architect",
                }
            }
        )
        master = _resume_dict(
            customSections={
                "certifications": {
                    "sectionType": "text",
                    "text": "AWS Certified Solutions Architect",
                }
            }
        )
        jd = _jd_keywords(required=["aws"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.missing_keywords == []
        assert result.current_match_percentage == pytest.approx(100.0)

    def test_custom_section_string_list_extraction(self) -> None:
        tailored = _resume_dict(
            customSections={
                "skills_extra": {
                    "sectionType": "stringList",
                    "strings": ["terraform", "ansible"],
                }
            }
        )
        master = tailored
        jd = _jd_keywords(required=["terraform"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.missing_keywords == []

    def test_custom_section_item_list_extraction(self) -> None:
        tailored = _resume_dict(
            customSections={
                "open_source": {
                    "sectionType": "itemList",
                    "items": [
                        {
                            "title": "Contributor",
                            "subtitle": "OSS Project",
                            "description": ["contributed rust crates"],
                        }
                    ],
                }
            }
        )
        master = tailored
        jd = _jd_keywords(required=["rust"])
        result = analyze_keyword_gaps(jd, tailored, master)
        assert result.missing_keywords == []

    # --- Regression guard ---------------------------------------------------

    def test_catches_regression_substring_matching(self) -> None:
        """Regression: 'go' must NOT match 'going'.

        If _keyword_in_text ever regresses to substring matching, this test
        catches it: 'going' would falsely satisfy the 'go' keyword, making it
        appear present in tailored when it is not. The synonym-aware rewire
        (RIT-T-0064) preserves this by NOT accepting stem-only matches.
        """
        tailored = _resume_dict(summary="going to the office daily")
        master = _resume_dict(summary="experience with go programming")
        jd = _jd_keywords(required=["go"])
        result = analyze_keyword_gaps(jd, tailored, master)
        # 'go' not a whole term in tailored → must be missing
        assert "go" in result.missing_keywords
        # 'go' IS a whole term in master → injectable, not non-injectable
        assert "go" in result.injectable_keywords
        assert "go" not in result.non_injectable_keywords
