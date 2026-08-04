"""Unit tests for the normalization pipeline."""

from __future__ import annotations

import pytest
from resume_kit_terms import normalize, surface_form


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("Mentoring", "mentor"),
        ("mentored", "mentor"),
        ("mentor", "mentor"),
        ("Testing", "test"),
        ("tested", "test"),
    ],
)
def test_stem_families_collapse(term: str, expected: str) -> None:
    assert normalize(term) == expected


def test_inflectional_family_members_agree() -> None:
    # Inflectional suffixes (-ing, -ed) collapse to a shared stem.
    forms = {normalize(t) for t in ["mentor", "mentoring", "mentored"]}
    assert len(forms) == 1


def test_derivational_suffix_not_stemmed() -> None:
    # Snowball strips inflectional suffixes but NOT derivational ones like
    # -ship: mentoring/mentorship do not collapse via stemming. That bridge is
    # the alias lexicon's job (RIT-T-0063), not the stemmer's.
    assert normalize("mentorship") != normalize("mentoring")


@pytest.mark.parametrize(
    ("term", "expected"),
    [
        ("Node.js", "node js"),
        ("node js", "node js"),
        ("  RESTful   APIs ", "rest api"),
        ("CI/CD", "ci cd"),
    ],
)
def test_punctuation_and_space_collapse(term: str, expected: str) -> None:
    assert normalize(term) == expected


def test_ascii_fold_neutralizes_typographic_noise() -> None:
    # Curly quotes, middle dot, en/em dashes must not survive to defeat matching.
    assert normalize("Node·js") == normalize("Node.js")
    assert normalize("café") == normalize("cafe")
    assert normalize("re–build") == normalize("re-build")


def test_empty_and_symbol_only_normalize_to_empty() -> None:
    assert normalize("") == ""
    assert normalize("   ") == ""
    assert normalize("!!!") == ""


def test_normalize_is_deterministic() -> None:
    assert normalize("Architecting") == normalize("Architecting")


def test_surface_form_does_not_stem() -> None:
    # surface_form folds case/punctuation/unicode but keeps the word intact.
    assert surface_form("Mentoring") == "mentoring"
    assert surface_form("Node.js") == "node js"
    # ...whereas normalize stems it.
    assert normalize("Mentoring") == "mentor"
    assert surface_form("Mentoring") != normalize("Mentoring")


def test_distinct_skills_not_collapsed_by_stemming() -> None:
    # Guard against over-aggressive stemming merging unrelated tech tokens.
    assert normalize("React") != normalize("Redux")
    assert normalize("Java") != normalize("JavaScript")
    assert normalize("Python") != normalize("PyTorch")
