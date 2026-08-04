"""Unit tests for the TerminologyAlignment domain model (RIT-T-0072)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import TerminologyAlignment


def test_construction_and_defaults() -> None:
    ta = TerminologyAlignment(
        jd_keyword="k8s",
        current_wording="kubernetes",
        canonical="kubernet",
    )
    assert ta.jd_keyword == "k8s"
    assert ta.current_wording == "kubernetes"
    assert ta.canonical == "kubernet"
    assert ta.locations == []
    assert ta.match_kind == "alias"


def test_locations_preserved() -> None:
    ta = TerminologyAlignment(
        jd_keyword="mentorship",
        current_wording="mentoring",
        canonical="mentor",
        locations=["summary", "workExperience[0].description[1]"],
    )
    assert ta.locations == ["summary", "workExperience[0].description[1]"]


def test_frozen() -> None:
    ta = TerminologyAlignment(
        jd_keyword="k8s", current_wording="kubernetes", canonical="kubernet"
    )
    with pytest.raises(ValidationError):
        ta.jd_keyword = "changed"  # type: ignore[misc]


def test_match_kind_only_alias() -> None:
    with pytest.raises(ValidationError):
        TerminologyAlignment(
            jd_keyword="k8s",
            current_wording="kubernetes",
            canonical="kubernet",
            match_kind="exact",  # type: ignore[arg-type]
        )
