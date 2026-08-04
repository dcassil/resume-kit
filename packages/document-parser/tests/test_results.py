"""Tests for resume_kit_document_parser.results — ParseResult contracts."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_core.errors import CoreWarning, WarningCode
from resume_kit_core.response import ProvenanceRef
from resume_kit_document_parser.results import ParseMethod, ParseResult
from resume_kit_schemas.resume import ResumeDocument

# ---------------------------------------------------------------------------
# ParseMethod enum
# ---------------------------------------------------------------------------


def test_parse_method_members() -> None:
    assert ParseMethod.deterministic == "deterministic"
    assert ParseMethod.llm == "llm"


# ---------------------------------------------------------------------------
# Default construction
# ---------------------------------------------------------------------------


def test_parse_result_defaults() -> None:
    result = ParseResult(text="some extracted text", confidence=1.0)

    assert result.text == "some extracted text"
    assert result.document is None
    assert result.confidence == 1.0
    assert result.warnings == []
    assert result.provenance == []


# ---------------------------------------------------------------------------
# Confidence bounds
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad_value", [-0.01, 1.01, -1.0, 2.0])
def test_confidence_out_of_range_rejected(bad_value: float) -> None:
    with pytest.raises(ValidationError):
        ParseResult(text="x", confidence=bad_value)


@pytest.mark.parametrize("good_value", [0.0, 0.5, 1.0])
def test_confidence_boundary_values_accepted(good_value: float) -> None:
    result = ParseResult(text="x", confidence=good_value)
    assert result.confidence == good_value


# ---------------------------------------------------------------------------
# No-LLM / text-only result
# ---------------------------------------------------------------------------


def test_text_only_result_with_provider_unavailable_warning() -> None:
    """document=None + PROVIDER_UNAVAILABLE warning signals LLM was not used."""
    warning = CoreWarning(
        code=WarningCode.PROVIDER_FALLBACK_USED,
        message="Structured parsing unavailable: no LLM provider configured.",
    )
    provenance = ProvenanceRef(
        source_id="resume.pdf",
        source_type="file",
        metadata={"parser": "PdfParser", "method": ParseMethod.deterministic},
    )

    result = ParseResult(
        text="# Jane Doe\nSoftware Engineer",
        confidence=1.0,
        document=None,
        warnings=[warning],
        provenance=[provenance],
    )

    assert result.document is None
    assert len(result.warnings) == 1
    assert result.warnings[0].code == WarningCode.PROVIDER_FALLBACK_USED
    assert result.provenance[0].source_id == "resume.pdf"
    assert result.provenance[0].metadata["method"] == ParseMethod.deterministic


# ---------------------------------------------------------------------------
# Structured result (document populated)
# ---------------------------------------------------------------------------


def test_parse_result_with_document() -> None:
    doc = ResumeDocument()
    provenance = ProvenanceRef(
        source_id="resume.docx",
        source_type="llm_response",
        metadata={"parser": "LlmStructuredParser", "method": ParseMethod.llm},
    )

    result = ParseResult(
        text="# Resume content",
        confidence=0.87,
        document=doc,
        provenance=[provenance],
    )

    assert result.document is not None
    assert result.confidence == 0.87
    assert result.provenance[0].metadata["method"] == ParseMethod.llm


# ---------------------------------------------------------------------------
# Pydantic v2 serialization round-trip
# ---------------------------------------------------------------------------


def test_round_trip_text_only() -> None:
    warning = CoreWarning(
        code=WarningCode.PROVIDER_FALLBACK_USED,
        message="No LLM available.",
    )
    original = ParseResult(
        text="Plain text resume",
        confidence=0.95,
        warnings=[warning],
    )

    dumped = original.model_dump()
    restored = ParseResult.model_validate(dumped)

    assert restored.text == original.text
    assert restored.confidence == original.confidence
    assert restored.document is None
    assert len(restored.warnings) == 1
    assert restored.warnings[0].code == WarningCode.PROVIDER_FALLBACK_USED


def test_round_trip_with_document() -> None:
    doc = ResumeDocument(summary="Experienced engineer.")
    provenance = ProvenanceRef(
        source_id="cv.pdf",
        source_type="llm_response",
        metadata={"parser": "LlmParser", "method": ParseMethod.llm},
    )
    original = ParseResult(
        text="# CV",
        confidence=0.75,
        document=doc,
        provenance=[provenance],
    )

    dumped = original.model_dump()
    restored = ParseResult.model_validate(dumped)

    assert restored.document is not None
    assert restored.document.summary == "Experienced engineer."
    assert restored.provenance[0].source_id == "cv.pdf"
    assert restored.provenance[0].metadata["parser"] == "LlmParser"
