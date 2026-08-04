"""Characterization tests for the deterministic skill-target verifier."""

from __future__ import annotations

from resume_kit_policy.skill_targets import (
    build_allowed_skill_target_keys,
    verify_skill_target_plan,
)
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.job import JobDescription, Requirement, RequirementKind
from resume_kit_schemas.results import PolicyReasonCode, SkillTargetSource
from resume_kit_schemas.resume import AdditionalInfo, ResumeDocument


def _resume() -> dict[str, object]:
    return {
        "summary": "Platform engineer who built CI/CD automation.",
        "workExperience": [
            {
                "title": "Software Engineer",
                "company": "Example",
                "description": [
                    "Built production services in Go and deployed observability tooling.",
                    "Maintained .NET services written in C#.",
                ],
            }
        ],
        "personalProjects": [
            {
                "name": "Systems tools",
                "description": ["Implemented parsers with C++."],
            }
        ],
        "additional": {
            "technicalSkills": ["Python", "Docker"],
        },
    }


def _job_keywords() -> dict[str, object]:
    return {
        "required_skills": ["Kubernetes", "Terraform", "C++"],
        "preferred_skills": ["C#"],
        "keywords": ["CI/CD"],
    }


def _job_description() -> str:
    return (
        "We require Kubernetes, Terraform, and C++ experience. "
        "C# experience is preferred."
    )


def test_accepts_existing_and_explicit_jd_required_or_preferred_skills() -> None:
    plan = verify_skill_target_plan(
        {
            "target_skills": [
                {"skill": "python", "reason": "Already in resume"},
                {"skill": "Kubernetes", "reason": "JD required"},
                {"skill": "C#", "reason": "JD preferred"},
            ]
        },
        original_resume=_resume(),
        job_keywords=_job_keywords(),
        job_description=_job_description(),
    )

    assert plan.verified_skills == ["Python", "Kubernetes", "C#"]
    assert [target.source for target in plan.accepted_targets] == [
        SkillTargetSource.EXISTING,
        SkillTargetSource.JD_ADDED,
        SkillTargetSource.JD_ADDED,
    ]
    assert plan.accepted_targets[0].normalized_skill == "python"
    assert plan.accepted_targets[0].reason == "Already in resume"


def test_accepts_skills_supported_by_resume_text_but_not_skill_list_or_jd() -> None:
    plan = verify_skill_target_plan(
        {"target_skills": [{"skill": "Go", "reason": ""}]},
        original_resume=_resume(),
        job_keywords=_job_keywords(),
        job_description=_job_description(),
    )

    assert plan.verified_skills == ["Go"]
    assert plan.accepted_targets[0].source is SkillTargetSource.SUPPORTED_BY_RESUME
    assert plan.rejected_targets == []


def test_accepts_skills_backed_by_unambiguous_candidate_evidence() -> None:
    evidence = CandidateEvidence(
        id="ev-terraform",
        kind=EvidenceKind.PROJECT,
        content="Candidate built Terraform modules for cloud infrastructure.",
        tags=["Terraform"],
    )

    plan = verify_skill_target_plan(
        {"target_skills": ["Terraform"]},
        original_resume={"additional": {"technicalSkills": []}},
        job_keywords={"required_skills": [], "preferred_skills": []},
        candidate_evidence=[evidence],
    )

    assert plan.verified_skills == ["Terraform"]
    assert plan.accepted_targets[0].source is SkillTargetSource.EVIDENCE_BACKED
    assert plan.accepted_targets[0].evidence_ids == ["ev-terraform"]
    assert plan.accepted_targets[0].evidence_kinds == [EvidenceKind.PROJECT]


def test_rejects_ambiguous_evidence_support() -> None:
    evidence = CandidateEvidence(
        id="ev-cloud",
        kind=EvidenceKind.OTHER,
        content="Candidate built infrastructure automation.",
        tags=["Terraform"],
    )

    plan = verify_skill_target_plan(
        {"target_skills": ["Terraform"]},
        original_resume={"additional": {"technicalSkills": []}},
        job_keywords={"required_skills": [], "preferred_skills": []},
        candidate_evidence=[evidence],
    )

    assert plan.verified_skills == []
    assert plan.rejected_targets[0].reason_code is PolicyReasonCode.UNSUPPORTED_SKILL


def test_rejects_unsupported_skills_and_does_not_accept_generic_keywords() -> None:
    plan = verify_skill_target_plan(
        {
            "target_skills": [
                {"skill": "CI/CD", "reason": "Generic keyword, not skill field"},
                {"skill": "BananaDB", "reason": "Unsupported"},
            ]
        },
        original_resume={"additional": {"technicalSkills": []}},
        job_keywords=_job_keywords(),
        job_description=_job_description(),
    )

    assert plan.verified_skills == []
    assert [target.display_skill for target in plan.rejected_targets] == [
        "CI/CD",
        "BananaDB",
    ]
    assert [target.reason_code for target in plan.rejected_targets] == [
        PolicyReasonCode.UNSUPPORTED_SKILL,
        PolicyReasonCode.UNSUPPORTED_SKILL,
    ]


def test_duplicate_targets_are_collapsed_case_insensitively_and_rejected() -> None:
    plan = verify_skill_target_plan(
        {"target_skills": ["Python", " python ", {"skill": "PYTHON"}]},
        original_resume=_resume(),
        job_keywords=_job_keywords(),
        job_description=_job_description(),
    )

    assert plan.verified_skills == ["Python"]
    assert [target.display_skill for target in plan.rejected_targets] == [
        "python",
        "PYTHON",
    ]
    assert all(
        target.reason_code is PolicyReasonCode.DUPLICATE_SKILL
        for target in plan.rejected_targets
    )


def test_malformed_target_lists_match_upstream_empty_behavior() -> None:
    plan = verify_skill_target_plan(
        {"target_skills": {"skill": "Python"}},
        original_resume=_resume(),
        job_keywords=_job_keywords(),
        job_description=_job_description(),
    )

    assert plan.proposed_skills == []
    assert plan.accepted_targets == []
    assert plan.rejected_targets == []


def test_skips_malformed_entries_inside_target_list() -> None:
    plan = verify_skill_target_plan(
        {"target_skills": [None, 12, {"skill": ""}, "Docker"]},
        original_resume=_resume(),
        job_keywords=_job_keywords(),
        job_description=_job_description(),
    )

    assert plan.proposed_skills == ["Docker"]
    assert plan.verified_skills == ["Docker"]
    assert plan.rejected_targets == []


def test_punctuated_skills_are_matched_as_whole_terms() -> None:
    plan = verify_skill_target_plan(
        {"target_skills": ["C++", "C#"]},
        original_resume={"additional": {"technicalSkills": []}},
        job_keywords=_job_keywords(),
        job_description=_job_description(),
    )

    assert plan.verified_skills == ["C++", "C#"]
    assert [target.normalized_skill for target in plan.accepted_targets] == ["c++", "c#"]


def test_schema_inputs_are_supported_for_resume_and_job_description() -> None:
    resume = ResumeDocument(additional=AdditionalInfo(technicalSkills=["Docker"]))
    job = JobDescription(
        raw_text="Kubernetes is required. Go is preferred.",
        requirements=[
            Requirement(text="Kubernetes", kind=RequirementKind.REQUIRED),
        ],
        qualifications=[
            Requirement(text="Go", kind=RequirementKind.PREFERRED),
        ],
    )

    plan = verify_skill_target_plan(
        {"target_skills": ["Docker", "Kubernetes", "Go"]},
        original_resume=resume,
        job_keywords=job,
    )

    assert plan.verified_skills == ["Docker", "Kubernetes", "Go"]
    assert plan.job == job


def test_build_allowed_skill_target_keys_accepts_plan_schema_and_upstream_shapes() -> None:
    plan = verify_skill_target_plan(
        {"target_skills": ["Python", "Kubernetes"]},
        original_resume=_resume(),
        job_keywords=_job_keywords(),
        job_description=_job_description(),
    )

    assert build_allowed_skill_target_keys(plan) == {"python", "kubernetes"}
    assert build_allowed_skill_target_keys(
        ["Docker", {"skill": "C++"}, {"display_skill": "C#"}]
    ) == {"docker", "c++", "c#"}
