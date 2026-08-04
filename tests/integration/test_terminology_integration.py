"""End-to-end integration tests for terminology-alignment (RIT-I-0010).

Proves the initiative end-to-end: alias-satisfied JD keywords become
truth-gated surface-mirroring suggestions, applying them preserves the
underlying claim (truth passes) with a deterministic delta, and no-match
keywords stay gaps and can never be rewritten.

Fixture design:
  - Resume carries ALIAS surface forms in description bullets and summary.
  - JD carries the CANONICAL / alternative wording (the employer's exact term).

Alias pairs used (verified against packages/terms/.../aliases.json):

  JD keyword   | Resume alias  | canonical stem
  -------------|---------------|----------------
  "Kubernetes" | "k8s"         | "kubernet"
  "linting"    | "eslint"      | "lint"

A no-match term ("Terraform") is absent from the resume entirely, so it must
remain a gap and never produce a suggestion.

An exact-match term ("React") appears verbatim in both the resume and JD, so
it must NOT produce a terminology suggestion (already mirrored).

The ``additional.technicalSkills`` list is intentionally NOT used as a
suggestion target path: policy blocks bare skills-list element replacements.
All alias terms appear in description bullets and summary so the accept path
can fire (F4 / F6 freedom gate).

Docstring lines in this module do NOT start with 'from <word>' (boundary
rule enforced by the venv regex guard).
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest
from resume_kit_alignment import accept_terminology_alignment
from resume_kit_evidence import build_candidate_evidence
from resume_kit_facade import (
    AlignTerminologyRequest,
    AlignTerminologyResult,
    SuggestTerminologyRequest,
    align_terminology,
    suggest_terminology,
)
from resume_kit_facade.models import CapabilityOptions
from resume_kit_matching import analyze_keyword_gaps, analyze_terminology_alignment
from resume_kit_schemas import JobDescription, ResumeDocument, TerminologyAlignment

# ---------------------------------------------------------------------------
# Canonical stems (verified against aliases.json)
# ---------------------------------------------------------------------------

_CANONICAL_KUBERNETES = "kubernet"
_CANONICAL_LINT = "lint"

# ---------------------------------------------------------------------------
# Synthetic fixture: resume uses alias surface forms, JD uses canonical/other
# ---------------------------------------------------------------------------


def _terminology_resume_dict() -> dict[str, Any]:
    """Resume with alias surface forms in description bullets and summary.

    "k8s" (alias for Kubernetes) in bullet + summary.
    "eslint" (alias for linting) in bullet.
    "React" exact-matches the JD — no suggestion expected.
    No mention of Terraform — stays a gap.
    """
    return {
        "personalInfo": {
            "name": "Alex Alias",
            "email": "alex@example.com",
            "phone": "555-0200",
        },
        "summary": (
            "Platform engineer with deep k8s experience, shipping React "
            "applications and enforcing code quality through eslint."
        ),
        "workExperience": [
            {
                "title": "Senior Platform Engineer",
                "company": "Acme Corp",
                "years": "2021 - Present",
                "description": [
                    "Managed production clusters on k8s across three regions.",
                    "Integrated eslint into the CI pipeline to enforce code standards.",
                    "Delivered React front-ends aligned with design-system tokens.",
                ],
            }
        ],
        "education": [
            {"degree": "BS Computer Science", "institution": "State University"}
        ],
        "additional": {
            "technicalSkills": [
                "React",
                "TypeScript",
                "k8s",
                "eslint",
            ]
        },
    }


def _terminology_resume() -> ResumeDocument:
    """Pydantic-validated resume built from the alias-surface fixture dict."""
    return ResumeDocument.model_validate(_terminology_resume_dict())


def _terminology_job_dict() -> dict[str, Any]:
    """JD with canonical/employer wording for each alias pair.

    "Kubernetes" (resume: k8s), "linting" (resume: eslint) — alias hits.
    "React" — exact hit; must NOT produce a suggestion.
    "Terraform" — absent; must NOT produce a suggestion, must be a gap.
    """
    return {
        "title": "Senior Platform Engineer",
        "company": "TechCo",
        "required_skills": ["Kubernetes", "linting", "React", "Terraform"],
        "preferred_skills": [],
        "keywords": ["Kubernetes", "linting", "React", "Terraform"],
        "description": (
            "We are looking for a Kubernetes expert comfortable with linting "
            "pipelines, React front-ends, and Terraform-managed infrastructure."
        ),
    }


def _terminology_job() -> Any:
    """Return the JD fixture as a plain dict (accepted by the engine)."""
    return _terminology_job_dict()


def _terminology_job_model() -> JobDescription:
    """Return the JD fixture as a validated JobDescription model.

    Required by accept_terminology_alignment which calls job.model_dump() internally.
    """
    return JobDescription.model_validate(_terminology_job_dict())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _suggestion_for(
    suggestions: list[TerminologyAlignment], jd_keyword: str
) -> TerminologyAlignment | None:
    """Return the first suggestion matching *jd_keyword*, or None."""
    for s in suggestions:
        if s.jd_keyword.lower() == jd_keyword.lower():
            return s
    return None


def _run(coro: Any) -> Any:
    """Run a top-level coroutine synchronously via a fresh event loop."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# 1. Analyze: correct suggestions arise for alias pairs; none for exact/absent
# ---------------------------------------------------------------------------


def test_analyze_yields_suggestion_for_kubernetes_alias() -> None:
    """k8s (resume) vs Kubernetes (JD) must produce a TerminologyAlignment."""
    job = _terminology_job()
    resume = _terminology_resume_dict()

    suggestions = analyze_terminology_alignment(job, resume)

    k8s_sugg = _suggestion_for(suggestions, "Kubernetes")
    assert k8s_sugg is not None, "Expected a Kubernetes/k8s suggestion"
    assert k8s_sugg.jd_keyword == "Kubernetes"
    assert k8s_sugg.current_wording == "k8s"
    assert k8s_sugg.canonical == _CANONICAL_KUBERNETES
    assert k8s_sugg.match_kind == "alias"
    # The alias appears in the summary and two description bullets — at minimum
    # both the summary path and at least one description path must be reported.
    assert len(k8s_sugg.locations) >= 2, k8s_sugg.locations


def test_analyze_yields_suggestion_for_eslint_alias() -> None:
    """eslint (resume) vs linting (JD) must produce a TerminologyAlignment."""
    job = _terminology_job()
    resume = _terminology_resume_dict()

    suggestions = analyze_terminology_alignment(job, resume)

    lint_sugg = _suggestion_for(suggestions, "linting")
    assert lint_sugg is not None, "Expected a linting/eslint suggestion"
    assert lint_sugg.jd_keyword == "linting"
    assert lint_sugg.current_wording == "eslint"
    assert lint_sugg.canonical == _CANONICAL_LINT
    assert lint_sugg.match_kind == "alias"
    assert len(lint_sugg.locations) >= 1


def test_analyze_no_suggestion_for_exact_match() -> None:
    """React (exact hit) must NOT produce a terminology suggestion."""
    job = _terminology_job()
    resume = _terminology_resume_dict()

    suggestions = analyze_terminology_alignment(job, resume)

    react_sugg = _suggestion_for(suggestions, "React")
    assert react_sugg is None, "React is already exact — no suggestion expected"


def test_analyze_no_suggestion_for_absent_term() -> None:
    """Terraform (absent from resume) must produce NO suggestion and stay a gap."""
    job = _terminology_job()
    resume = _terminology_resume_dict()

    suggestions = analyze_terminology_alignment(job, resume)

    terraform_sugg = _suggestion_for(suggestions, "Terraform")
    assert terraform_sugg is None, "Absent Terraform must not produce a suggestion"

    # Confirm it stays a gap via keyword analysis.
    gaps = analyze_keyword_gaps(job, resume, resume)
    missing_lower = {m.lower() for m in gaps.missing_keywords}
    assert "terraform" in missing_lower, "Terraform must remain a gap"


def test_analyze_suggestion_locations_point_at_description_bullets() -> None:
    """Suggestion locations for k8s must include a workExperience description path."""
    job = _terminology_job()
    resume = _terminology_resume_dict()

    suggestions = analyze_terminology_alignment(job, resume)

    k8s_sugg = _suggestion_for(suggestions, "Kubernetes")
    assert k8s_sugg is not None
    desc_paths = [loc for loc in k8s_sugg.locations if "description" in loc]
    assert len(desc_paths) >= 1, (
        "At least one location must be a description bullet path"
    )


# ---------------------------------------------------------------------------
# 2. Accept/apply: swap happens, truth passes, delta is non-negative
# ---------------------------------------------------------------------------


def test_accept_swaps_surface_term_in_description_bullet() -> None:
    """Accepting a k8s suggestion replaces k8s with Kubernetes in the bullet."""
    job_dict = _terminology_job()
    job_model = _terminology_job_model()
    resume_doc = _terminology_resume()
    original_resume = _terminology_resume()

    suggestions = analyze_terminology_alignment(job_dict, resume_doc.model_dump())
    k8s_sugg = _suggestion_for(suggestions, "Kubernetes")
    assert k8s_sugg is not None

    # Pick the first description-bullet path so policy (F4) can unlock it.
    desc_locations = [
        loc for loc in k8s_sugg.locations if "workExperience" in loc and "description" in loc
    ]
    assert desc_locations, "Need at least one workExperience.description location"
    location = desc_locations[0]

    evidence = build_candidate_evidence(original_resume)

    result = accept_terminology_alignment(
        k8s_sugg, location, resume_doc, job_model, evidence
    )

    assert result.swap_applied, "Swap must be applied for a valid description bullet"
    assert "Kubernetes" in result.field_after, (
        f"Employer wording 'Kubernetes' must appear after swap; got: {result.field_after!r}"
    )
    assert "k8s" not in result.field_after, (
        f"Alias 'k8s' must be gone after swap; got: {result.field_after!r}"
    )


def test_accept_truth_passes_after_swap() -> None:
    """After accepting a surface-only swap, truth validation must still pass."""
    job_dict = _terminology_job()
    job_model = _terminology_job_model()
    resume_doc = _terminology_resume()
    original_resume = _terminology_resume()

    suggestions = analyze_terminology_alignment(job_dict, resume_doc.model_dump())
    k8s_sugg = _suggestion_for(suggestions, "Kubernetes")
    assert k8s_sugg is not None

    desc_locations = [
        loc for loc in k8s_sugg.locations if "workExperience" in loc and "description" in loc
    ]
    location = desc_locations[0]
    evidence = build_candidate_evidence(original_resume)

    result = accept_terminology_alignment(
        k8s_sugg, location, resume_doc, job_model, evidence
    )

    assert result.truth_passed, (
        "Truth must pass after a surface-only alias swap — the claim is unchanged"
    )


def test_accept_score_does_not_drop() -> None:
    """keyword_match score must not drop after an alias swap (direction only)."""
    job_dict = _terminology_job()
    job_model = _terminology_job_model()
    resume_doc = _terminology_resume()
    original_resume = _terminology_resume()

    suggestions = analyze_terminology_alignment(job_dict, resume_doc.model_dump())
    k8s_sugg = _suggestion_for(suggestions, "Kubernetes")
    assert k8s_sugg is not None

    desc_locations = [
        loc for loc in k8s_sugg.locations if "workExperience" in loc and "description" in loc
    ]
    location = desc_locations[0]
    evidence = build_candidate_evidence(original_resume)

    result = accept_terminology_alignment(
        k8s_sugg, location, resume_doc, job_model, evidence
    )

    assert result.delta.keyword_match_after >= result.delta.keyword_match_before, (
        "keyword_match must not drop after a surface alias swap"
    )
    assert result.delta.skills_coverage_after >= result.delta.skills_coverage_before, (
        "skills_coverage must not drop after a surface alias swap"
    )


# ---------------------------------------------------------------------------
# 3. Adversarial (NFR-1001): blocked paths and absent keywords cannot fire
# ---------------------------------------------------------------------------


def test_adversarial_absent_term_never_becomes_a_suggestion() -> None:
    """Terraform is absent — it must never reach accept, because analyze returns nothing."""
    job = _terminology_job()
    resume = _terminology_resume_dict()

    suggestions = analyze_terminology_alignment(job, resume)

    terraform_sugg = _suggestion_for(suggestions, "Terraform")
    assert terraform_sugg is None, (
        "No-match keyword must never produce a TerminologyAlignment; "
        "accept cannot be called without a suggestion"
    )


def test_adversarial_blocked_field_is_not_applied() -> None:
    """Swapping a suggestion into a blocked factual field (company name) is rejected."""
    job_dict = _terminology_job()
    job_model = _terminology_job_model()
    resume_doc = _terminology_resume()
    original_resume = _terminology_resume()

    suggestions = analyze_terminology_alignment(job_dict, resume_doc.model_dump())
    k8s_sugg = _suggestion_for(suggestions, "Kubernetes")
    assert k8s_sugg is not None

    # Use a blocked identity-style path that policy never unlocks.
    # 'workExperience[0].company' is a factual field (employer name) — always blocked.
    blocked_location = "workExperience[0].company"

    evidence = build_candidate_evidence(original_resume)

    result = accept_terminology_alignment(
        k8s_sugg, blocked_location, resume_doc, job_model, evidence
    )

    # Policy must reject this — the resume must be unchanged.
    assert not result.swap_applied, "A blocked field must never have the swap applied"
    assert result.rejected, "Policy must record a rejection for the blocked path"
    # Resume is structurally unchanged (company name unmodified).
    assert (
        result.resume.workExperience[0].company
        == original_resume.workExperience[0].company
    ), "Company name must be untouched after a rejected swap"


def test_adversarial_exact_match_produces_no_suggestion() -> None:
    """React (already exact in both JD and resume) must never generate a suggestion."""
    job = _terminology_job()
    resume = _terminology_resume_dict()

    suggestions = analyze_terminology_alignment(job, resume)

    react_sugg = _suggestion_for(suggestions, "React")
    assert react_sugg is None, (
        "An exact-match keyword can never become a terminology suggestion"
    )


# ---------------------------------------------------------------------------
# 4. Surface parity: facade produces the same suggestions as the direct analyzer
# ---------------------------------------------------------------------------


def test_facade_suggest_terminology_matches_direct_analyzer() -> None:
    """suggest_terminology facade must return the same suggestions as the direct analyzer."""
    resume_doc = _terminology_resume()
    job_doc = _terminology_job()

    # Direct analyzer (plain dict input accepted by the engine).
    direct_suggestions = analyze_terminology_alignment(job_doc, resume_doc.model_dump())

    # Facade path (async, uses Pydantic request model).
    pydantic_job = JobDescription.model_validate(job_doc)
    request = SuggestTerminologyRequest(resume=resume_doc, job=pydantic_job)
    options = CapabilityOptions(no_llm=True)
    response = _run(suggest_terminology(request, options))

    assert not response.errors, f"Facade errors: {response.errors}"
    facade_suggestions: list[TerminologyAlignment] = response.data
    assert isinstance(facade_suggestions, list)

    # Sort both by (jd_keyword, current_wording) for stable comparison.
    def _sort_key(s: TerminologyAlignment) -> tuple[str, str]:
        return (s.jd_keyword, s.current_wording)

    direct_sorted = sorted(direct_suggestions, key=_sort_key)
    facade_sorted = sorted(facade_suggestions, key=_sort_key)

    assert len(facade_sorted) == len(direct_sorted), (
        f"Facade returned {len(facade_sorted)} suggestions; "
        f"direct returned {len(direct_sorted)}"
    )
    for facade_s, direct_s in zip(facade_sorted, direct_sorted, strict=True):
        assert facade_s.jd_keyword == direct_s.jd_keyword
        assert facade_s.current_wording == direct_s.current_wording
        assert facade_s.canonical == direct_s.canonical
        assert facade_s.match_kind == direct_s.match_kind
        assert facade_s.locations == direct_s.locations


def test_facade_align_terminology_applies_and_returns_result() -> None:
    """align_terminology facade must apply the swap and return an AlignTerminologyResult."""
    resume_doc = _terminology_resume()
    original_resume = _terminology_resume()
    pydantic_job = JobDescription.model_validate(_terminology_job())

    direct_suggestions = analyze_terminology_alignment(
        _terminology_job(), resume_doc.model_dump()
    )
    k8s_sugg = _suggestion_for(direct_suggestions, "Kubernetes")
    assert k8s_sugg is not None

    desc_locations = [
        loc for loc in k8s_sugg.locations if "workExperience" in loc and "description" in loc
    ]
    location = desc_locations[0]
    evidence = build_candidate_evidence(original_resume)

    request = AlignTerminologyRequest(
        suggestion=k8s_sugg,
        location=location,
        resume=resume_doc,
        job=pydantic_job,
        evidence=tuple(evidence),
    )
    options = CapabilityOptions(no_llm=True)
    response = _run(align_terminology(request, options))

    assert not response.errors, f"Facade errors: {response.errors}"
    result: AlignTerminologyResult = response.data
    assert isinstance(result, AlignTerminologyResult)
    assert result.swap_applied
    assert result.truth_passed
    assert "Kubernetes" in result.field_after


# ---------------------------------------------------------------------------
# 5. Exports: all required public symbols are importable from their package roots
# ---------------------------------------------------------------------------


def test_exports_terminology_alignment_importable() -> None:
    """TerminologyAlignment must be importable directly from resume_kit_schemas."""
    from resume_kit_schemas import TerminologyAlignment as _TA  # noqa: F401

    assert _TA is TerminologyAlignment


def test_exports_analyze_terminology_alignment_importable() -> None:
    """analyze_terminology_alignment must be importable from resume_kit_matching."""
    from resume_kit_matching import (  # noqa: F401
        analyze_terminology_alignment as _ata,
    )

    assert _ata is analyze_terminology_alignment


def test_exports_accept_terminology_alignment_importable() -> None:
    """accept_terminology_alignment must be importable from resume_kit_alignment."""
    from resume_kit_alignment import (  # noqa: F401
        accept_terminology_alignment as _accept,
    )

    assert _accept is accept_terminology_alignment


def test_exports_facade_suggest_and_align_importable() -> None:
    """suggest_terminology and align_terminology must be importable from resume_kit_facade."""
    from resume_kit_facade import (  # noqa: F401
        align_terminology as _at,
    )
    from resume_kit_facade import (
        suggest_terminology as _st,
    )

    assert _st is suggest_terminology
    assert _at is align_terminology


# ---------------------------------------------------------------------------
# 6. Determinism: identical inputs produce identical suggestions and delta
# ---------------------------------------------------------------------------


def test_determinism_analyze_same_inputs_same_suggestions() -> None:
    """analyze_terminology_alignment must return identical output on two runs."""
    job = _terminology_job()
    resume = _terminology_resume_dict()

    first = analyze_terminology_alignment(job, resume)
    second = analyze_terminology_alignment(job, resume)

    assert len(first) == len(second)
    for s1, s2 in zip(first, second, strict=True):
        assert s1.jd_keyword == s2.jd_keyword
        assert s1.current_wording == s2.current_wording
        assert s1.canonical == s2.canonical
        assert s1.locations == s2.locations
        assert s1.match_kind == s2.match_kind


def test_determinism_accept_same_delta_on_two_runs() -> None:
    """accept_terminology_alignment must produce the same score delta on two calls."""
    job_dict = _terminology_job()
    job_model = _terminology_job_model()
    resume_doc = _terminology_resume()
    original_resume = _terminology_resume()

    suggestions = analyze_terminology_alignment(job_dict, resume_doc.model_dump())
    k8s_sugg = _suggestion_for(suggestions, "Kubernetes")
    assert k8s_sugg is not None

    desc_locations = [
        loc for loc in k8s_sugg.locations if "workExperience" in loc and "description" in loc
    ]
    location = desc_locations[0]
    evidence = build_candidate_evidence(original_resume)

    result_a = accept_terminology_alignment(
        k8s_sugg, location, resume_doc, job_model, evidence
    )
    result_b = accept_terminology_alignment(
        k8s_sugg, location, resume_doc, job_model, evidence
    )

    assert result_a.delta.keyword_match_before == pytest.approx(
        result_b.delta.keyword_match_before
    )
    assert result_a.delta.keyword_match_after == pytest.approx(
        result_b.delta.keyword_match_after
    )
    assert result_a.delta.skills_coverage_before == pytest.approx(
        result_b.delta.skills_coverage_before
    )
    assert result_a.delta.skills_coverage_after == pytest.approx(
        result_b.delta.skills_coverage_after
    )
    assert result_a.swap_applied == result_b.swap_applied
    assert result_a.truth_passed == result_b.truth_passed
    assert result_a.field_after == result_b.field_after
