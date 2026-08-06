"""
Resume Kit Document Parser — Phase 2 document extraction and parsing.

Provides parsing and extraction services for resume documents in various formats
(PDF, DOCX, etc.) as input to the resume evaluation pipeline.
"""

from .parse_risk import (
    SOURCE_LAYOUT_HEADER_FOOTER,
    SOURCE_LAYOUT_IMAGE_ONLY,
    SOURCE_LAYOUT_MULTICOLUMN,
    SOURCE_LAYOUT_TABLE,
    SOURCE_LAYOUT_TEXTBOX,
    detect_source_parse_risks,
)
from .results import ParseMethod, ParseResult
from .structured import extract_resume_text_only, parse_resume_structured
from .text_extraction import TextExtractionResult, extract_resume_text

__version__ = "0.0.0"

__all__ = [
    "SOURCE_LAYOUT_HEADER_FOOTER",
    "SOURCE_LAYOUT_IMAGE_ONLY",
    "SOURCE_LAYOUT_MULTICOLUMN",
    "SOURCE_LAYOUT_TABLE",
    "SOURCE_LAYOUT_TEXTBOX",
    "ParseMethod",
    "ParseResult",
    "TextExtractionResult",
    "detect_source_parse_risks",
    "extract_resume_text",
    "extract_resume_text_only",
    "parse_resume_structured",
]
