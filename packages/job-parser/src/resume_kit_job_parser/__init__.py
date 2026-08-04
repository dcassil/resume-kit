"""
Resume Kit Job Parser — Phase 3 job description extraction and parsing.

Provides parsing and extraction services for job descriptions from various sources
and providers, with support for deterministic non-LLM extraction paths.
"""

from .parse import parse_job_description, parse_job_description_text_only

__version__ = "0.0.0"

__all__ = [
    "parse_job_description",
    "parse_job_description_text_only",
]
