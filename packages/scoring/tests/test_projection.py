"""Golden + determinism tests for project_scoredoc (RIT-T-0106)."""

from __future__ import annotations

from datetime import date

from resume_kit_schemas import (
    AdditionalInfo,
    Education,
    Experience,
    KeywordZone,
    PersonalInfo,
    Project,
    ResumeDocument,
)
from resume_kit_scoring import project_scoredoc
from resume_kit_terms import normalize

_REF = date(2025, 1, 1)


def _resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Daniel Cassil",
            email="me@example.com",
            phone="555-1234",
            linkedin="linkedin.com/in/dc",
        ),
        summary="Built Python services.",
        workExperience=[
            Experience(
                title="Staff Engineer",
                company="Acme",
                years="2019 - Present",
                description=["Led the billing platform."],
            ),
            Experience(
                title="Engineer",
                company="Beta",
                years="Jan 2016 - Dec 2018",
                description=["Shipped the API."],
            ),
        ],
        education=[
            Education(institution="State U", degree="BS Computer Science", years="2012 - 2016")
        ],
        personalProjects=[
            Project(name="OSS Tool", role="Author", years="2020", description=["A CLI."])
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "FastAPI", "Kubernetes"]),
    )


def test_zones_and_entities() -> None:
    doc = project_scoredoc(_resume(), reference_date=_REF)
    zones = {s.zone for s in doc.sections}
    assert KeywordZone.EXPERIENCE in zones
    assert KeywordZone.SKILLS_LIST in zones
    assert KeywordZone.SUMMARY in zones
    assert KeywordZone.EDUCATION in zones
    assert KeywordZone.PROJECTS in zones
    # categorized skill present as a canonical token in the skills zone
    skills_tokens = doc.zoned_index.zone_tokens[KeywordZone.SKILLS_LIST]
    assert normalize("Python") in skills_tokens
    assert normalize("Kubernetes") in skills_tokens
    # entities
    assert doc.entities.name == "Daniel Cassil"
    assert doc.entities.email == "me@example.com"
    assert doc.entities.links == ["linkedin.com/in/dc"]
    assert len(doc.entities.roles) == 2


def test_years_of_experience_union() -> None:
    doc = project_scoredoc(_resume(), reference_date=_REF)
    # 2016-01..2018-12 = 35 months; 2019-01..2025-01 = 72 months; no overlap.
    # total = 107 months / 12 = 8.9 (rounded 1 decimal)
    assert doc.entities.total_years_experience == round(107 / 12, 1)


def test_overlapping_roles_counted_once() -> None:
    resume = ResumeDocument(
        workExperience=[
            Experience(title="A", company="X", years="2018 - 2022"),
            Experience(title="B", company="Y", years="2020 - 2024"),  # overlaps A
        ]
    )
    doc = project_scoredoc(resume, reference_date=_REF)
    # union 2018..2024 = 72 months = 6.0 years, not 4+4=8
    assert doc.entities.total_years_experience == 6.0


def test_unparseable_dates_excluded() -> None:
    resume = ResumeDocument(
        workExperience=[Experience(title="A", company="X", years="a while ago")]
    )
    doc = project_scoredoc(resume, reference_date=_REF)
    assert doc.entities.roles[0].duration_months is None
    assert doc.entities.total_years_experience == 0.0


def test_open_ended_uses_reference_date() -> None:
    resume = ResumeDocument(
        workExperience=[Experience(title="A", company="X", years="2023 - Present")]
    )
    doc = project_scoredoc(resume, reference_date=date(2025, 1, 1))
    assert doc.entities.roles[0].duration_months == 24


def test_deterministic_identical_output() -> None:
    a = project_scoredoc(_resume(), reference_date=_REF)
    b = project_scoredoc(_resume(), reference_date=_REF)
    assert a.model_dump_json() == b.model_dump_json()


def test_custom_section_skills_map_to_skills_zone() -> None:
    """RIT-T-0108: a categorized custom skills section projects into the
    SKILLS_LIST zone (proves the zoning the matching/ats fixes rely on)."""
    resume = ResumeDocument.model_validate(
        {
            "additional": {"technicalSkills": []},
            "customSections": {
                "Cloud Skills": {
                    "sectionType": "stringList",
                    "strings": ["Terraform", "Kubernetes"],
                }
            },
        }
    )
    doc = project_scoredoc(resume, reference_date=_REF)
    skills = [s for s in doc.sections if s.zone == KeywordZone.SKILLS_LIST]
    assert skills and skills[0].name == "Cloud Skills"
    tokens = doc.zoned_index.zone_tokens[KeywordZone.SKILLS_LIST]
    assert normalize("Terraform") in tokens
    assert normalize("Kubernetes") in tokens


def test_custom_experience_section_maps_to_experience_zone() -> None:
    resume = ResumeDocument.model_validate(
        {
            "customSections": {
                "Consulting Experience": {
                    "sectionType": "itemList",
                    "items": [{"title": "Advisor", "description": ["Led migration."]}],
                }
            }
        }
    )
    doc = project_scoredoc(resume, reference_date=_REF)
    zones = {s.zone for s in doc.sections}
    assert KeywordZone.EXPERIENCE in zones
