"""Characterization tests for path_policy — locking upstream parity.

Each case encodes an observable behavior from upstream improver.py's
_is_path_allowed / _is_path_blocked (SHA 116f9cc3...) and the paths exercised by
upstream tests/unit/test_apply_diffs.py, so any future divergence is caught.
"""

from __future__ import annotations

import pytest
from resume_kit_policy.path_policy import is_path_allowed, is_path_blocked


@pytest.mark.parametrize(
    "path",
    [
        "summary",
        "workExperience[0].description",
        "workExperience[0].description[1]",
        "personalProjects[0].description[0]",
        "education[0].description",
        "additional.technicalSkills",
        "additional.languages",
        "additional.certificationsTraining",
        "additional.awards",
    ],
)
def test_allowed_paths_match_upstream_whitelist(path: str) -> None:
    assert is_path_allowed(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "",
        "personalInfo.name",
        "customSections.volunteer",
        "workExperience[0].years",
        "workExperience[0].company",
        "education[0].degree",
        # scalar-only: the [j] bullet form of education description is NOT allowed
        "education[0].description[0]",
        "nonexistent.field",
    ],
)
def test_non_allowed_paths_rejected(path: str) -> None:
    assert is_path_allowed(path) is False


@pytest.mark.parametrize(
    "path",
    [
        "personalInfo",
        "personalInfo.name",
        "personalInfo.email",
        "customSections",
        "customSections.volunteer",
        "sectionMeta.foo",
        "workExperience[0].years",
        "workExperience[0].company",
        "workExperience[0].location",
        "personalProjects[0].role",
        "education[0].degree",
        "education[0].institution",
        "education[0].years",
        # education non-description leaf blocked by the education carve-out
        "education[0].name",
    ],
)
def test_blocked_paths_match_upstream(path: str) -> None:
    assert is_path_blocked(path) is True


@pytest.mark.parametrize(
    "path",
    [
        "summary",
        "workExperience[0].description",
        "workExperience[0].description[1]",
        "personalProjects[0].description[0]",
        "education[0].description",
        "additional.technicalSkills",
        "additional.languages",
    ],
)
def test_editable_paths_not_blocked(path: str) -> None:
    assert is_path_blocked(path) is False


def test_education_description_is_the_only_editable_education_path() -> None:
    assert is_path_blocked("education[0].description") is False
    assert is_path_blocked("education[0].degree") is True
    assert is_path_blocked("education[0].institution") is True
    assert is_path_blocked("education[0].years") is True


@pytest.mark.parametrize(
    "leaf",
    ["years", "company", "institution", "title", "degree", "name", "role",
     "github", "website", "location", "id"],
)
def test_blocked_leaf_field_names(leaf: str) -> None:
    assert is_path_blocked(f"workExperience[0].{leaf}") is True
