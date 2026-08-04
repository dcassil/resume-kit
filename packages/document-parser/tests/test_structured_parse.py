"""Provider-boundary tests for structured resume parsing.

All tests use the in-memory ``FakeStructuredCompletionProvider`` from
``resume_kit_core.testing`` — no network, no concrete LLM provider.
"""

from __future__ import annotations

import pytest
from resume_kit_core.errors import WarningCode
from resume_kit_core.testing import FakeStructuredCompletionProvider
from resume_kit_document_parser import (
    ParseMethod,
    extract_resume_text_only,
    parse_resume_structured,
)

_RESUME_MD = b"""# Jane Smith

Senior Engineer

## Experience

Acme Corp - Engineer
Jun 2020 - Aug 2021
- Built things
"""


def _sample_parsed() -> dict[str, object]:
    return {
        "personalInfo": {
            "name": "Jane Smith",
            "title": "Senior Engineer",
            "email": "jane@example.com",
        },
        "summary": "Experienced engineer.",
        "workExperience": [
            {
                "id": 1,
                "title": "Engineer",
                "company": "Acme Corp",
                "years": "2020 - 2021",
                "description": ["Built things"],
            }
        ],
    }


@pytest.mark.asyncio
async def test_happy_path_returns_valid_document() -> None:
    provider = FakeStructuredCompletionProvider(responses=[_sample_parsed()])

    result = await parse_resume_structured(_RESUME_MD, "resume.md", provider)

    assert result.document is not None
    assert result.document.personalInfo.name == "Jane Smith"
    assert result.document.workExperience[0].company == "Acme Corp"
    assert result.confidence > 0.5
    # Provenance carries parser lineage + the llm method.
    methods = {p.metadata["method"] for p in result.provenance}
    assert ParseMethod.llm.value in methods
    assert all(p.metadata["parser"] for p in result.provenance)
    # The provider received a request.
    assert len(provider.calls) == 1


@pytest.mark.asyncio
async def test_malformed_output_degrades_without_crash() -> None:
    # Non-dict output → provider fake would still return the queued value;
    # we simulate a queue-exhausted provider (raises ResumeKitError).
    provider = FakeStructuredCompletionProvider(responses=[])

    result = await parse_resume_structured(_RESUME_MD, "resume.md", provider)

    assert result.document is None
    assert result.confidence < 0.5
    codes = {w.code for w in result.warnings}
    assert WarningCode.PROVIDER_FALLBACK_USED in codes


@pytest.mark.asyncio
async def test_invalid_schema_output_degrades() -> None:
    # workExperience must be a list; a string triggers a ValidationError.
    provider = FakeStructuredCompletionProvider(
        responses=[{"workExperience": "not-a-list"}]
    )

    result = await parse_resume_structured(_RESUME_MD, "resume.md", provider)

    assert result.document is None
    assert result.confidence < 0.5
    codes = {w.code for w in result.warnings}
    assert WarningCode.INCOMPLETE_DATA in codes


@pytest.mark.asyncio
async def test_dropped_months_are_repaired() -> None:
    provider = FakeStructuredCompletionProvider(responses=[_sample_parsed()])

    result = await parse_resume_structured(_RESUME_MD, "resume.md", provider)

    assert result.document is not None
    # Markdown had "Jun 2020 - Aug 2021"; the year-only "2020 - 2021" is repaired.
    assert result.document.workExperience[0].years == "Jun 2020 - Aug 2021"


@pytest.mark.asyncio
async def test_empty_text_degrades() -> None:
    provider = FakeStructuredCompletionProvider(responses=[_sample_parsed()])

    result = await parse_resume_structured(b"", "resume.md", provider)

    assert result.document is None
    assert result.confidence < 0.5
    codes = {w.code for w in result.warnings}
    assert WarningCode.INCOMPLETE_DATA in codes
    # Provider is never called when there is no text.
    assert len(provider.calls) == 0


def test_text_only_path_has_no_document_and_unavailable_warning() -> None:
    result = extract_resume_text_only(_RESUME_MD, "resume.md")

    assert result.document is None
    assert "Jane Smith" in result.text
    codes = {w.code for w in result.warnings}
    assert WarningCode.PROVIDER_FALLBACK_USED in codes
