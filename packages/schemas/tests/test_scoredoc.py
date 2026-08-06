"""Tests for the ScoreDoc schema (RIT-T-0105).

Pure-data models: construction, JSON round-trip stability, pinned enum values,
and frozen/immutable semantics. No projection logic is exercised here.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from resume_kit_schemas import (
    KeywordZone,
    ScoreDegree,
    ScoreDoc,
    ScoreEntities,
    ScoreRole,
    ScoreSection,
    ZonedKeywordIndex,
)


def test_keyword_zone_values_pinned() -> None:
    assert [z.value for z in KeywordZone] == [
        "experience",
        "skills_list",
        "summary",
        "education",
        "projects",
        "other",
    ]


def _doc() -> ScoreDoc:
    return ScoreDoc(
        sections=[
            ScoreSection(
                name="Experience", zone=KeywordZone.EXPERIENCE, text="Built Python services."
            ),
            ScoreSection(name="Skills", zone=KeywordZone.SKILLS_LIST, text="Python, FastAPI"),
        ],
        entities=ScoreEntities(
            name="Daniel Cassil",
            email="me@example.com",
            phone="555-1234",
            links=["linkedin.com/in/dc"],
            roles=[
                ScoreRole(
                    title="Engineer",
                    company="Acme",
                    start_date="2019",
                    end_date="Present",
                    duration_months=72,
                )
            ],
            total_years_experience=6.0,
            education=[ScoreDegree(degree="BS CS", institution="State U")],
        ),
        zoned_index=ZonedKeywordIndex(
            token_zones={"python": [KeywordZone.EXPERIENCE, KeywordZone.SKILLS_LIST]},
            zone_tokens={KeywordZone.SKILLS_LIST: ["python", "fastapi"]},
        ),
    )


def test_scoredoc_round_trip_stable() -> None:
    doc = _doc()
    restored = ScoreDoc.model_validate_json(doc.model_dump_json())
    assert restored == doc
    assert restored.entities.total_years_experience == 6.0
    assert restored.zoned_index.token_zones["python"] == [
        KeywordZone.EXPERIENCE,
        KeywordZone.SKILLS_LIST,
    ]


def test_defaults_are_empty_and_deterministic() -> None:
    doc = ScoreDoc()
    assert doc.sections == []
    assert doc.entities == ScoreEntities()
    assert doc.zoned_index.token_zones == {}
    assert doc.schema_version >= 1


def test_models_are_frozen() -> None:
    role = ScoreRole(title="Engineer")
    with pytest.raises(ValidationError):
        role.title = "Manager"  # type: ignore[misc]
