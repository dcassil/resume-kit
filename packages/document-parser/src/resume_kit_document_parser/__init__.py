"""
Resume Kit Document Parser — Phase 2 document extraction and parsing.

Provides parsing and extraction services for resume documents in various formats
(PDF, DOCX, etc.) as input to the resume evaluation pipeline.
"""

from .results import ParseMethod, ParseResult
from .structured import extract_resume_text_only, parse_resume_structured
from .text_extraction import TextExtractionResult, extract_resume_text

__version__ = "0.0.0"

__all__ = [
    "ParseMethod",
    "ParseResult",
    "TextExtractionResult",
    "extract_resume_text",
    "extract_resume_text_only",
    "parse_resume_structured",
]
