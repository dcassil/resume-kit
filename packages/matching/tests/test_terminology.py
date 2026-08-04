"""Tests for the deterministic terminology-alignment analyzer (RIT-T-0072).

Proves ``analyze_terminology_alignment`` emits a mirror suggestion ONLY for JD
keywords the resume satisfies through the curated alias lexicon (an ``alias``
hit), never for exact hits or no-match keywords, locates the current wording by
whole-term match across resume fields, and returns a deterministic list.

Lexicon facts these tests rely on (packages/terms .../data/aliases.json):

- ``Kubernetes``: ["k8s"]        -> k8s / Kubernetes match as ``alias`` (canonical ``kubernet``).
- ``mentoring``:  ["mentorship"] -> mentorship / mentoring match as ``alias`` (canon ``mentor``).
- ``linting``:    ["eslint"]     -> eslint / linting match as ``alias`` (canonical ``lint``).
"""

from __future__ import annotations

from typing import Any

from resume_kit_matching import analyze_terminology_alignment


def _resume_dict(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": "",
        "workExperience": [],
        "education": [],
        "personalProjects": [],
        "additional": {},
        "customSections": {},
    }
    base.update(overrides)
    return base


def _jd(
    *,
    required: list[str] | None = None,
    preferred: list[str] | None = None,
    keywords: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "required_skills": required or [],
        "preferred_skills": preferred or [],
        "keywords": keywords or [],
    }


class TestAliasHitProducesSuggestion:
    def test_alias_hit_fields(self) -> None:
        # JD wants 'k8s'; resume says 'Kubernetes' -> mirror suggestion.
        resume = _resume_dict(summary="ran workloads on Kubernetes clusters")
        jd = _jd(required=["k8s"])
        result = analyze_terminology_alignment(jd, resume)
        assert len(result) == 1
        sug = result[0]
        assert sug.jd_keyword == "k8s"
        assert sug.current_wording == "kubernetes"
        assert sug.canonical == "kubernet"
        assert sug.match_kind == "alias"
        assert sug.locations == ["summary"]

    def test_alias_hit_in_work_experience_path(self) -> None:
        resume = _resume_dict(
            workExperience=[
                {"title": "Eng", "company": "Acme", "description": ["led mentoring efforts"]}
            ]
        )
        jd = _jd(required=["mentorship"])
        result = analyze_terminology_alignment(jd, resume)
        assert len(result) == 1
        sug = result[0]
        assert sug.jd_keyword == "mentorship"
        assert sug.current_wording == "mentoring"
        assert sug.canonical == "mentor"
        assert sug.locations == ["workExperience[0].description[0]"]


class TestExactAndNoMatchProduceNothing:
    def test_exact_hit_no_suggestion(self) -> None:
        # Resume already uses the JD's exact wording -> nothing to mirror.
        resume = _resume_dict(summary="deployed on k8s daily")
        jd = _jd(required=["k8s"])
        assert analyze_terminology_alignment(jd, resume) == []

    def test_no_match_no_suggestion(self) -> None:
        # 'graphql' absent entirely -> stays a gap, never a suggestion.
        resume = _resume_dict(summary="built REST APIs in python")
        jd = _jd(required=["graphql"])
        assert analyze_terminology_alignment(jd, resume) == []

    def test_already_mirrored_no_suggestion(self) -> None:
        # Case/space differences are exact surface matches, not aliases.
        resume = _resume_dict(summary="worked with K8S at scale")
        jd = _jd(required=["k8s"])
        assert analyze_terminology_alignment(jd, resume) == []


class TestMultiLocation:
    def test_same_wording_across_fields_grouped(self) -> None:
        resume = _resume_dict(
            summary="Kubernetes expert",
            workExperience=[
                {"title": "SRE", "company": "Acme", "description": ["scaled Kubernetes clusters"]}
            ],
            additional={"technicalSkills": ["Kubernetes"]},
        )
        jd = _jd(required=["k8s"])
        result = analyze_terminology_alignment(jd, resume)
        assert len(result) == 1
        assert result[0].locations == [
            "additional.technicalSkills[0]",
            "summary",
            "workExperience[0].description[0]",
        ]


class TestDeterminism:
    def test_identical_inputs_identical_output(self) -> None:
        resume = _resume_dict(
            summary="Kubernetes and mentoring and linting",
        )
        jd = _jd(required=["mentorship", "k8s"], keywords=["eslint"])
        first = analyze_terminology_alignment(jd, resume)
        second = analyze_terminology_alignment(jd, resume)
        assert [s.model_dump() for s in first] == [s.model_dump() for s in second]
        # Sorted by jd_keyword.
        assert [s.jd_keyword for s in first] == ["eslint", "k8s", "mentorship"]

    def test_multiple_suggestions_sorted(self) -> None:
        resume = _resume_dict(summary="mentoring juniors and running Kubernetes")
        jd = _jd(required=["k8s", "mentorship"])
        result = analyze_terminology_alignment(jd, resume)
        keys = [(s.jd_keyword, s.current_wording) for s in result]
        assert keys == sorted(keys)
