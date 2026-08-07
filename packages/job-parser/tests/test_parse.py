"""Tests for the provider-injected job-description parser.

All tests use :class:`~resume_kit_core.testing.FakeStructuredCompletionProvider`
only; no network or concrete LLM provider is involved.
"""

from __future__ import annotations

import pytest
from resume_kit_core.testing import FakeStructuredCompletionProvider
from resume_kit_job_parser.parse import (
    parse_job_description,
    parse_job_description_text_only,
)
from resume_kit_schemas.job import JobDescription, RequirementKind

_RAW_TEXT = (
    "Senior Backend Engineer\n"
    "Acme Corp\n\n"
    "We are hiring a backend engineer with strong Python and AWS skills."
)


@pytest.mark.asyncio
async def test_happy_path_maps_requirements_and_keywords() -> None:
    provider = FakeStructuredCompletionProvider(
        responses=[
            {
                "company": "Acme Corp",
                "role": "Senior Backend Engineer",
                "required_skills": ["Python", "AWS"],
                "preferred_skills": ["Kubernetes"],
                "experience_requirements": ["5+ years"],
                "education_requirements": ["Bachelor's in CS"],
                "key_responsibilities": ["Lead team"],
                "keywords": ["microservices", "agile"],
                "experience_years": 5,
                "seniority_level": "senior",
            }
        ]
    )

    result = await parse_job_description(_RAW_TEXT, provider)

    assert isinstance(result, JobDescription)
    assert result.title == "Senior Backend Engineer"
    assert result.company == "Acme Corp"
    assert result.raw_text == _RAW_TEXT

    # Required + experience + education all land in requirements.
    required_texts = [r.text for r in result.requirements]
    assert "Python" in required_texts
    assert "AWS" in required_texts
    assert "5+ years" in required_texts
    assert "Bachelor's in CS" in required_texts
    assert all(r.kind is RequirementKind.REQUIRED for r in result.requirements)

    # Preferred skills land in qualifications.
    assert [q.text for q in result.qualifications] == ["Kubernetes"]
    assert result.qualifications[0].kind is RequirementKind.PREFERRED

    # Keywords aggregate explicit keywords + skills, deduped.
    assert "microservices" in result.keywords
    assert "Python" in result.keywords
    assert "Kubernetes" in result.keywords

    # Summary captures seniority / years / responsibilities.
    assert "senior" in result.summary
    assert "5+ years" in result.summary
    assert "Lead team" in result.summary

    # Prompt was actually sent to the provider.
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_provider_error_falls_back_to_raw_text() -> None:
    # Empty queue with no default -> complete_json raises ResumeKitError.
    provider = FakeStructuredCompletionProvider()

    result = await parse_job_description(_RAW_TEXT, provider)

    assert isinstance(result, JobDescription)
    assert result.raw_text == _RAW_TEXT
    # Best-effort title from first line; no requirements without a provider.
    assert result.title == "Senior Backend Engineer"
    assert result.requirements == []
    assert result.qualifications == []
    assert result.keywords == []


@pytest.mark.asyncio
async def test_malformed_nondict_output_falls_back() -> None:
    provider = FakeStructuredCompletionProvider(
        responses=[["not", "a", "dict"]]  # type: ignore[list-item]
    )

    result = await parse_job_description(_RAW_TEXT, provider)

    assert isinstance(result, JobDescription)
    assert result.raw_text == _RAW_TEXT
    assert result.requirements == []
    assert result.keywords == []


@pytest.mark.asyncio
async def test_partial_dict_tolerates_missing_fields() -> None:
    provider = FakeStructuredCompletionProvider(
        responses=[{"role": "Data Analyst", "required_skills": ["SQL"]}]
    )

    result = await parse_job_description(_RAW_TEXT, provider)

    assert result.title == "Data Analyst"
    assert result.company == ""
    assert [r.text for r in result.requirements] == ["SQL"]
    assert result.keywords == ["SQL"]


@pytest.mark.asyncio
async def test_sentence_skill_dropped_from_keywords_but_text_retained() -> None:
    # RIT-T-0128: a prose "skill" must not enter keywords / requirement keywords,
    # but the requirement text is preserved verbatim for display.
    sentence = "4-6+ years of professional experience building large-scale web apps"
    provider = FakeStructuredCompletionProvider(
        responses=[
            {
                "role": "Engineer",
                "required_skills": ["Python", sentence],
                "keywords": ["React", sentence],
            }
        ]
    )

    result = await parse_job_description(_RAW_TEXT, provider)

    # The prose never appears as a keyword...
    assert sentence not in result.keywords
    assert result.keywords == ["React", "Python"]
    # ...and the prose requirement carries no sentence-shaped keyword.
    prose_reqs = [r for r in result.requirements if r.text == sentence]
    assert len(prose_reqs) == 1  # text retained for display
    assert prose_reqs[0].keywords == []  # but no fake keyword token
    # The concrete requirement keeps its token.
    python_reqs = [r for r in result.requirements if r.text == "Python"]
    assert python_reqs[0].keywords == ["Python"]


def test_text_only_path_preserves_raw_text() -> None:
    result = parse_job_description_text_only(_RAW_TEXT)

    assert isinstance(result, JobDescription)
    assert result.raw_text == _RAW_TEXT
    assert result.title == "Senior Backend Engineer"
    assert result.requirements == []
    assert result.qualifications == []
    assert result.keywords == []


def test_text_only_empty_input_is_minimal() -> None:
    result = parse_job_description_text_only("")

    assert result.raw_text == ""
    assert result.title == ""
