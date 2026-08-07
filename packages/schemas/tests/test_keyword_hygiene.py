"""Tests for the deterministic keyword hygiene gate (RIT-T-0128)."""

from __future__ import annotations

import pytest
from resume_kit_schemas import is_concrete_keyword, sanitize_keywords


@pytest.mark.parametrize(
    "text",
    [
        "Python",
        "CI/CD",
        "Node.js",  # dotted token must NOT be treated as a sentence
        "distributed systems design",
        "multi-tenant",
        "large-scale web application development",  # 4 words, under the cap
    ],
)
def test_accepts_concrete_tokens(text: str) -> None:
    assert is_concrete_keyword(text) is True


@pytest.mark.parametrize(
    "text",
    [
        "",
        "   ",
        "5+ years",
        "4-6+ years of professional experience",
        "4-6+ years of professional experience building modern, large-scale web applications",
        "Build scalable, reliable backend systems.",  # terminal punctuation → prose
        "You will lead a team of engineers and own delivery",  # over the word cap
    ],
)
def test_rejects_prose_and_year_clauses(text: str) -> None:
    assert is_concrete_keyword(text) is False


def test_sanitize_filters_dedups_and_preserves_order() -> None:
    entries = [
        "Python",
        "5+ years",
        "4-6+ years of professional experience building modern, large-scale web apps",
        "React",
        "python",  # case-insensitive duplicate of Python
        "Node.js",
    ]
    assert sanitize_keywords(entries) == ["Python", "React", "Node.js"]


def test_sanitize_is_deterministic() -> None:
    entries = ["Docker", "kubernetes", "Docker", "prose sentence ends here."]
    assert sanitize_keywords(entries) == sanitize_keywords(entries)
    assert sanitize_keywords(entries) == ["Docker", "kubernetes"]
