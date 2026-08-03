"""Characterization tests locking upstream resume-model coercion behavior.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/tests/unit/test_description_styles.py
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Retargeted from ``app.schemas.models`` to canonical
#   ``resume_kit_schemas`` names; added coverage for string/list description
#   coercion, optional-text coercion, summary coercion, and default filling to
#   prove the ported validators still catch breakage.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import pytest
from resume_kit_schemas import (
    CustomSectionItem,
    Education,
    Experience,
    Project,
    ResumeData,
    ResumeDocument,
)


def test_experience_description_styles_are_aligned_to_descriptions() -> None:
    experience = Experience.model_validate(
        {
            "description": ["Built APIs", "Led migrations", "Reduced latency"],
            "descriptionStyles": [None, "plain"],
        }
    )
    # Missing/unknown style rows default to "bullet"; alignment tracks description count.
    assert experience.descriptionStyles == ["bullet", "plain", "bullet"]


def test_project_description_styles_are_trimmed_to_description_count() -> None:
    project = Project.model_validate(
        {"description": ["Built CLI"], "descriptionStyles": ["plain", "bullet"]}
    )
    assert project.descriptionStyles == ["plain"]


def test_resume_data_defaults_missing_custom_item_styles_to_bullets() -> None:
    resume = ResumeData.model_validate(
        {
            "customSections": {
                "publications": {
                    "sectionType": "itemList",
                    "items": [{"title": "Paper", "description": ["Accepted", "Presented"]}],
                }
            }
        }
    )
    items = resume.customSections["publications"].items
    assert items is not None
    item = items[0]
    assert isinstance(item, CustomSectionItem)
    assert item.descriptionStyles == ["bullet", "bullet"]


def test_description_string_is_split_into_bullet_lines() -> None:
    # A single string block coerces into cleaned bullet lines (prefixes stripped).
    exp = Experience.model_validate(
        {"description": "- Built APIs\n* Led migrations\n1. Reduced latency"}
    )
    assert exp.description == ["Built APIs", "Led migrations", "Reduced latency"]


def test_education_optional_description_coerces_nested_text() -> None:
    edu = Education.model_validate({"description": {"text": "Graduated with honors"}})
    assert edu.description == "Graduated with honors"
    empty = Education.model_validate({"description": []})
    assert empty.description is None


def test_summary_coerces_nested_value() -> None:
    resume = ResumeDocument.model_validate({"summary": {"text": "Senior engineer"}})
    assert resume.summary == "Senior engineer"


def test_resume_document_fills_defaults() -> None:
    resume = ResumeDocument.model_validate({})
    assert resume.personalInfo.name == ""
    assert resume.workExperience == []
    assert resume.summary == ""


def test_custom_section_promotes_string_items_to_titled_items() -> None:
    section = ResumeData.model_validate(
        {"customSections": {"awards": {"sectionType": "itemList", "items": ["Best Paper"]}}}
    ).customSections["awards"]
    assert section.items is not None
    assert section.items[0].title == "Best Paper"
    assert section.items[0].id == 1


def test_resume_data_roundtrips_through_json() -> None:
    # Locks canonical round-trip behavior relied on by improve/confirm hashing.
    raw = {"personalInfo": {"name": "Ada"}, "summary": "Engineer"}
    canonical = ResumeData.model_validate(raw).model_dump()
    again = ResumeData.model_validate(canonical).model_dump()
    assert canonical == again


def test_alias_is_same_class() -> None:
    assert ResumeData is ResumeDocument


@pytest.mark.parametrize("bad", [123, 4.5])
def test_experience_scalar_description_coerces_to_string(bad: object) -> None:
    exp = Experience.model_validate({"description": bad})
    assert exp.description == [str(bad)]
