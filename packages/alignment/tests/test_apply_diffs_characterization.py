"""Characterization tests for the deterministic diff-application engine.

These reproduce the expected behavior of upstream
``apps/backend/tests/unit/test_apply_diffs.py`` against the ported
``resume_kit_alignment.apply.apply_diffs``, which delegates its path and skill
gates to ``resume_kit_policy``. The engine is called at ``freedom=10`` so the
full upstream allowed-path set is unlocked; the blocked factual-field gate must
still reject identity fields even at that maximum freedom.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest
from resume_kit_alignment.apply import apply_diffs
from resume_kit_schemas.change import ChangeProposal, ChangeSet
from resume_kit_schemas.results import PolicyReasonCode

FREEDOM_MAX = 10


@pytest.fixture
def sample_resume() -> dict[str, Any]:
    """A realistic resume dict matching the ResumeData schema (upstream parity)."""

    return {
        "personalInfo": {
            "name": "Jane Doe",
            "title": "Senior Backend Engineer",
            "email": "jane@example.com",
            "phone": "+1-555-0100",
            "location": "San Francisco, CA",
            "website": "https://janedoe.dev",
            "linkedin": "linkedin.com/in/janedoe",
            "github": "github.com/janedoe",
        },
        "summary": (
            "Backend engineer with 6 years of experience building scalable "
            "Python APIs and microservices."
        ),
        "workExperience": [
            {
                "id": 1,
                "title": "Senior Backend Engineer",
                "company": "Acme Corp",
                "location": "San Francisco, CA",
                "years": "Jan 2021 - Present",
                "description": [
                    "Built REST APIs serving 50K requests/day using Python and FastAPI",
                    "Led migration from monolith to microservices architecture",
                    "Mentored 3 junior developers on backend best practices",
                ],
            },
            {
                "id": 2,
                "title": "Software Engineer",
                "company": "StartupCo",
                "location": "New York, NY",
                "years": "Jun 2018 - Dec 2020",
                "description": [
                    "Developed payment processing system handling $2M monthly",
                    "Wrote unit and integration tests improving coverage from 40% to 85%",
                ],
            },
        ],
        "education": [
            {
                "id": 1,
                "institution": "MIT",
                "degree": "B.S. Computer Science",
                "years": "2014 - 2018",
                "description": "Graduated with honors, Dean's List",
            }
        ],
        "personalProjects": [
            {
                "id": 1,
                "name": "OpenAPI Generator",
                "role": "Creator & Maintainer",
                "years": "Mar 2021 - Present",
                "description": [
                    "CLI tool generating API clients from OpenAPI specs",
                    "500+ GitHub stars, used by 30+ companies",
                ],
            }
        ],
        "additional": {
            "technicalSkills": [
                "Python",
                "FastAPI",
                "Docker",
                "AWS",
                "PostgreSQL",
                "Redis",
            ],
            "languages": ["English (Native)", "Spanish (Conversational)"],
            "certificationsTraining": ["AWS Solutions Architect Associate"],
            "awards": ["Employee of the Year 2022"],
        },
        "customSections": {},
        "sectionMeta": [],
    }


def _apply(
    resume: dict[str, Any],
    changes: list[ChangeProposal],
    **kwargs: Any,
) -> tuple[dict[str, Any], list[ChangeProposal], list[Any]]:
    return apply_diffs(resume, changes, freedom=FREEDOM_MAX, **kwargs)


# ---------------------------------------------------------------------------
# replace
# ---------------------------------------------------------------------------


def test_replace_summary(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="summary",
            action="replace",
            original=sample_resume["summary"],
            value="Updated summary text.",
            reason="test",
        )
    ]
    result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 1
    assert len(rejected) == 0
    assert result["summary"] == "Updated summary text."


def test_replace_description_bullet(sample_resume: dict[str, Any]) -> None:
    original_bullet = sample_resume["workExperience"][0]["description"][1]
    changes = [
        ChangeProposal(
            path="workExperience[0].description[1]",
            action="replace",
            original=original_bullet,
            value="Architected microservices migration serving 100K users",
            reason="test",
        )
    ]
    result, applied, _ = _apply(sample_resume, changes)
    assert len(applied) == 1
    assert result["workExperience"][0]["description"][1] == changes[0].value


def test_replace_case_insensitive_original_match(
    sample_resume: dict[str, Any],
) -> None:
    original_bullet = sample_resume["workExperience"][0]["description"][0]
    changes = [
        ChangeProposal(
            path="workExperience[0].description[0]",
            action="replace",
            original=original_bullet.upper(),  # case difference
            value="New text",
            reason="test",
        )
    ]
    _result, applied, _ = _apply(sample_resume, changes)
    assert len(applied) == 1


def test_reject_original_text_mismatch(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="workExperience[0].description[0]",
            action="replace",
            original="This text does not exist anywhere in the resume",
            value="New text",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 0
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.ORIGINAL_MISMATCH


# ---------------------------------------------------------------------------
# _verify_original_matches parity
# ---------------------------------------------------------------------------


def test_verify_original_matches_parity() -> None:
    from resume_kit_alignment.apply import _verify_original_matches

    # Missing original passes.
    assert _verify_original_matches("anything", None) is True
    # Non-string expected fails (list original on a text-style check).
    assert _verify_original_matches("x", ["a", "b"]) is False
    # Non-string actual fails.
    assert _verify_original_matches(["a"], "a") is False
    # String comparison is stripped + casefolded.
    assert _verify_original_matches("  Hello WORLD ", "hello world") is True
    assert _verify_original_matches("Hello", "Goodbye") is False


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------


def test_append_bullet_to_experience(sample_resume: dict[str, Any]) -> None:
    original_count = len(sample_resume["workExperience"][0]["description"])
    changes = [
        ChangeProposal(
            path="workExperience[0].description",
            action="append",
            original=None,
            value="Implemented CI/CD pipelines with GitHub Actions",
            reason="test",
        )
    ]
    result, applied, _ = _apply(sample_resume, changes)
    assert len(applied) == 1
    assert (
        len(result["workExperience"][0]["description"]) == original_count + 1
    )
    assert result["workExperience"][0]["description"][-1] == changes[0].value


def test_append_to_non_list_rejected(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="summary",
            action="append",
            original=None,
            value="Extra text",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 0
    assert len(rejected) == 1


# ---------------------------------------------------------------------------
# reorder
# ---------------------------------------------------------------------------


def test_reorder_skills(sample_resume: dict[str, Any]) -> None:
    original_skills = sample_resume["additional"]["technicalSkills"]
    reordered = list(reversed(original_skills))
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="reorder",
            original=None,
            value=reordered,
            reason="Prioritized relevant skills",
        )
    ]
    result, applied, _ = _apply(sample_resume, changes)
    assert len(applied) == 1
    assert result["additional"]["technicalSkills"] == reordered


def test_reorder_case_insensitive_matching(
    sample_resume: dict[str, Any],
) -> None:
    original_skills = sample_resume["additional"]["technicalSkills"]
    reordered = [s.lower() for s in reversed(original_skills)]
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="reorder",
            original=None,
            value=reordered,
            reason="test",
        )
    ]
    _result, applied, _ = _apply(sample_resume, changes)
    assert len(applied) == 1


def test_reorder_accepts_list_original_and_applies(
    sample_resume: dict[str, Any],
) -> None:
    original_skills = sample_resume["additional"]["technicalSkills"]
    reordered = list(reversed(original_skills))
    change = ChangeProposal(
        path="additional.technicalSkills",
        action="reorder",
        original=original_skills,  # a LIST, exactly as the LLM sends it
        value=reordered,
        reason="prioritize JD-relevant skills",
    )
    assert change.original == original_skills
    result, applied, _ = _apply(sample_resume, [change])
    assert len(applied) == 1
    assert result["additional"]["technicalSkills"] == reordered


def test_reorder_non_list_rejected(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="summary",
            action="reorder",
            original=None,
            value=["a", "b"],
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 0
    assert len(rejected) == 1


# ---------------------------------------------------------------------------
# reorder salvage (issue #736)
# ---------------------------------------------------------------------------


def test_reorder_with_unverified_items_drops_them_keeps_originals(
    sample_resume: dict[str, Any],
) -> None:
    original = sample_resume["additional"]["technicalSkills"]
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="reorder",
            original=None,
            value=["Python", "Kubernetes", "Go"],  # new, no verified targets
            reason="test",
        )
    ]
    result, applied, rejected = _apply(sample_resume, changes)
    skills = result["additional"]["technicalSkills"]
    assert len(applied) == 1 and len(rejected) == 0
    assert "Kubernetes" not in skills and "Go" not in skills
    assert set(skills) == set(original)
    assert skills[0] == "Python"


def test_reorder_with_verified_new_skill_is_salvaged(
    sample_resume: dict[str, Any],
) -> None:
    original = sample_resume["additional"]["technicalSkills"]
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="reorder",
            original=None,
            value=[
                "FastAPI",
                "Python",
                "Docker",
                "AWS",
                "PostgreSQL",
                "Redis",
                "Kubernetes",
            ],
            reason="surface JD skills; Kubernetes is JD-required",
        )
    ]
    result, applied, rejected = _apply(
        sample_resume, changes, allowed_skill_targets=[{"skill": "Kubernetes"}]
    )
    skills = result["additional"]["technicalSkills"]
    assert len(applied) == 1 and len(rejected) == 0
    assert "Kubernetes" in skills  # verified new skill added
    assert set(original).issubset(set(skills))  # no original lost
    assert skills[0] == "FastAPI"  # LLM order honored


def test_reorder_omitting_original_skill_preserves_it(
    sample_resume: dict[str, Any],
) -> None:
    original = sample_resume["additional"]["technicalSkills"]
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="reorder",
            original=None,
            value=["Redis", "Python"],  # omits 4 originals
            reason="prioritize two skills",
        )
    ]
    result, applied, _ = _apply(sample_resume, changes)
    skills = result["additional"]["technicalSkills"]
    assert len(applied) == 1
    assert set(skills) == set(original)  # nothing lost
    assert skills[:2] == ["Redis", "Python"]  # requested order first


def test_reorder_languages_with_new_item_drops_it(
    sample_resume: dict[str, Any],
) -> None:
    original = sample_resume["additional"]["languages"]
    changes = [
        ChangeProposal(
            path="additional.languages",
            action="reorder",
            original=None,
            value=[
                "Spanish (Conversational)",
                "English (Native)",
                "French (Fluent)",
            ],
            reason="no verified-target gate for languages",
        )
    ]
    result, applied, _ = _apply(sample_resume, changes)
    langs = result["additional"]["languages"]
    assert len(applied) == 1
    assert "French (Fluent)" not in langs  # no fabrication
    assert set(langs) == set(original)


def test_salvage_preserves_case_duplicate_originals() -> None:
    resume = {"additional": {"technicalSkills": ["python", "Python", "Docker"]}}
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="reorder",
            original=None,
            value=["Docker", "python", "Go"],  # Go new+unverified
            reason="test dup handling",
        )
    ]
    result, applied, _ = apply_diffs(resume, changes, freedom=FREEDOM_MAX)
    skills = result["additional"]["technicalSkills"]
    assert len(applied) == 1
    assert sorted(skills) == sorted(["python", "Python", "Docker"])
    assert "Go" not in skills


# ---------------------------------------------------------------------------
# add_skill
# ---------------------------------------------------------------------------


def test_add_skill_to_technical_skills(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="add_skill",
            original=None,
            value="Kubernetes",
            reason="JD-required skill approved by verifier",
        )
    ]
    result, applied, rejected = _apply(
        sample_resume, changes, allowed_skill_targets=[{"skill": "Kubernetes"}]
    )
    assert len(applied) == 1
    assert len(rejected) == 0
    assert "Kubernetes" in result["additional"]["technicalSkills"]


def test_add_skill_list_value_expands_to_single_skill_changes(
    sample_resume: dict[str, Any],
) -> None:
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="add_skill",
            original=None,
            value=["Kubernetes", "Terraform"],
            reason="JD-required skills approved by verifier",
        )
    ]
    result, applied, rejected = _apply(
        sample_resume,
        changes,
        allowed_skill_targets=[{"skill": "Kubernetes"}, {"skill": "Terraform"}],
    )
    assert len(applied) == 2
    assert len(rejected) == 0
    assert [change.value for change in applied] == ["Kubernetes", "Terraform"]
    assert "Kubernetes" in result["additional"]["technicalSkills"]
    assert "Terraform" in result["additional"]["technicalSkills"]


def test_add_skill_rejects_unverified_skill(
    sample_resume: dict[str, Any],
) -> None:
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="add_skill",
            original=None,
            value="BananaDB",
            reason="Unsupported skill should not be appended",
        )
    ]
    result, applied, rejected = _apply(
        sample_resume, changes, allowed_skill_targets=[{"skill": "Kubernetes"}]
    )
    assert len(applied) == 0
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.UNSUPPORTED_SKILL
    assert "BananaDB" not in result["additional"]["technicalSkills"]


def test_add_skill_rejects_duplicate_case_insensitive(
    sample_resume: dict[str, Any],
) -> None:
    changes = [
        ChangeProposal(
            path="additional.technicalSkills",
            action="add_skill",
            original=None,
            value="python",
            reason="Duplicate skill should not be appended",
        )
    ]
    result, applied, rejected = _apply(
        sample_resume, changes, allowed_skill_targets=[{"skill": "Python"}]
    )
    assert len(applied) == 0
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.DUPLICATE_SKILL
    assert result["additional"]["technicalSkills"].count("Python") == 1


def test_add_skill_rejects_non_skill_path(
    sample_resume: dict[str, Any],
) -> None:
    changes = [
        ChangeProposal(
            path="summary",
            action="add_skill",
            original=None,
            value="Kubernetes",
            reason="Skill additions are only allowed in technical skills",
        )
    ]
    result, applied, rejected = _apply(
        sample_resume, changes, allowed_skill_targets=[{"skill": "Kubernetes"}]
    )
    assert len(applied) == 0
    assert len(rejected) == 1
    assert "Kubernetes" not in result["additional"]["technicalSkills"]


# ---------------------------------------------------------------------------
# path resolution + verification gates
# ---------------------------------------------------------------------------


def test_reject_out_of_bounds_index(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="workExperience[99].description[0]",
            action="replace",
            original="Nonexistent",
            value="New",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 0
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.MALFORMED_PATH


def test_reject_nonexistent_path(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="nonexistent.field",
            action="replace",
            original="x",
            value="y",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 0
    assert len(rejected) == 1


def test_empty_path_rejected(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="",
            action="replace",
            original="x",
            value="y",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 0
    assert len(rejected) == 1


# ---------------------------------------------------------------------------
# blocked / factual fields — including the freedom-10 case
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path,original_val",
    [
        ("personalInfo.name", "Jane Doe"),
        ("personalInfo.email", "jane@example.com"),
    ],
)
def test_reject_personal_info(
    sample_resume: dict[str, Any], path: str, original_val: str
) -> None:
    changes = [
        ChangeProposal(
            path=path,
            action="replace",
            original=original_val,
            value="X",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 0
    assert len(rejected) == 1


def test_factual_field_blocked_even_at_freedom_10(
    sample_resume: dict[str, Any],
) -> None:
    """A factual identity field is rejected VIA POLICY at max freedom, and the
    rejection is a blocked-field policy decision — not an accidental path-not-
    found failure."""

    changes = [
        ChangeProposal(
            path="workExperience[0].company",
            action="replace",
            original="Acme Corp",
            value="Google",
            reason="test",
        )
    ]
    _result, applied, rejected = apply_diffs(
        sample_resume, changes, freedom=FREEDOM_MAX
    )
    assert len(applied) == 0
    assert len(rejected) == 1
    # Blocked by the policy gate, NOT by a resolution/path failure.
    assert rejected[0].reason_code == PolicyReasonCode.BLOCKED_FIELD


def test_reject_date_change(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="workExperience[0].years",
            action="replace",
            original="Jan 2021 - Present",
            value="Jan 2019 - Present",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(rejected) == 1
    assert rejected[0].reason_code == PolicyReasonCode.BLOCKED_FIELD


def test_reject_education_degree_change(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="education[0].degree",
            action="replace",
            original="B.S. Computer Science",
            value="M.S. Computer Science",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(rejected) == 1


def test_reject_custom_sections(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="customSections.volunteer",
            action="replace",
            original=None,
            value="Volunteer work",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(rejected) == 1


# ---------------------------------------------------------------------------
# newly allowed paths (education description scalar; other lists)
# ---------------------------------------------------------------------------


def test_replace_education_description(sample_resume: dict[str, Any]) -> None:
    changes = [
        ChangeProposal(
            path="education[0].description",
            action="replace",
            original=sample_resume["education"][0]["description"],
            value="Graduated with honors; focus on distributed systems and APIs",
            reason="surface relevant coursework",
        )
    ]
    result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 1
    assert len(rejected) == 0
    assert result["education"][0]["description"] == changes[0].value


def test_reject_education_description_list_index(
    sample_resume: dict[str, Any],
) -> None:
    changes = [
        ChangeProposal(
            path="education[0].description[0]",
            action="replace",
            original="Graduated with honors, Dean's List",
            value="anything",
            reason="test",
        )
    ]
    _result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 0
    assert len(rejected) == 1


# ---------------------------------------------------------------------------
# integrity: deep-copy, partial rejection, ChangeSet input, empty
# ---------------------------------------------------------------------------


def test_does_not_mutate_original(sample_resume: dict[str, Any]) -> None:
    original_copy = copy.deepcopy(sample_resume)
    changes = [
        ChangeProposal(
            path="summary",
            action="replace",
            original=sample_resume["summary"],
            value="Changed",
            reason="test",
        )
    ]
    result, _, _ = _apply(sample_resume, changes)
    assert sample_resume == original_copy
    assert result["summary"] == "Changed"


def test_multiple_changes_partial_rejection(
    sample_resume: dict[str, Any],
) -> None:
    changes = [
        ChangeProposal(
            path="summary",
            action="replace",
            original=sample_resume["summary"],
            value="New summary",
            reason="good",
        ),
        ChangeProposal(
            path="personalInfo.name",
            action="replace",
            original="Jane Doe",
            value="Bad",
            reason="blocked",
        ),
        ChangeProposal(
            path="workExperience[0].description[0]",
            action="replace",
            original=sample_resume["workExperience"][0]["description"][0],
            value="Updated bullet",
            reason="good",
        ),
    ]
    result, applied, rejected = _apply(sample_resume, changes)
    assert len(applied) == 2
    assert len(rejected) == 1
    assert result["summary"] == "New summary"
    assert result["personalInfo"]["name"] == "Jane Doe"  # unchanged


def test_accepts_change_set_input(sample_resume: dict[str, Any]) -> None:
    change_set = ChangeSet(
        changes=[
            ChangeProposal(
                path="summary",
                action="replace",
                original=sample_resume["summary"],
                value="From a ChangeSet",
                reason="test",
            )
        ]
    )
    result, applied, rejected = apply_diffs(
        sample_resume, change_set, freedom=FREEDOM_MAX
    )
    assert len(applied) == 1
    assert len(rejected) == 0
    assert result["summary"] == "From a ChangeSet"


def test_empty_changes_list(sample_resume: dict[str, Any]) -> None:
    result, applied, rejected = _apply(sample_resume, [])
    assert len(applied) == 0
    assert len(rejected) == 0
    assert result == sample_resume
