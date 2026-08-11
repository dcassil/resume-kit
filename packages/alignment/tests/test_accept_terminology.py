"""Tests for the accept-terminology path (RIT-T-0073).

Proves an accepted ``TerminologyAlignment`` is mapped to a surface-only
``replace`` change, routed through the existing policy/apply/truth gates at the
MINIMAL sufficient freedom, and reports a deterministic before/after score
delta — with no new truth/policy logic and no code path from a no-match keyword
to a change.

The engine supports in-place string ``replace`` only on the summary,
work/project description bullets, and education description (the policy
whitelist). Individual ``additional.technicalSkills`` *elements* are not an
editable target (only the whole list is, via reorder/add_skill), so an in-place
surface swap on a bare skill item is correctly rejected by the policy gate — a
truth-safety property (a skill claim is never silently dropped or duplicated).

Lexicon facts (packages/terms .../data/aliases.json):
- ``Kubernetes``: ["k8s"] -> k8s / Kubernetes match as ``alias`` (canon ``kubernet``).
"""

from __future__ import annotations

from resume_kit_alignment import (
    accept_terminology_alignment,
    build_terminology_change,
    minimal_freedom_for_path,
)
from resume_kit_evidence import build_candidate_evidence
from resume_kit_matching import analyze_terminology_alignment
from resume_kit_schemas import ResumeDocument, TerminologyAlignment
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.job import JobDescription, Requirement
from resume_kit_schemas.results import PolicyReasonCode
from resume_kit_schemas.resume import (
    AdditionalInfo,
    Experience,
    PersonalInfo,
)


def _resume_bullet() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(name="Sam Rivera"),
        summary="Platform engineer.",
        workExperience=[
            Experience(
                id=1,
                title="Platform Engineer",
                company="Northwind Ltd",
                years="2019-2024",
                description=["Ran workloads on Kubernetes across three regions."],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python", "Kubernetes"]),
    )


def _resume_summary() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(name="Sam Rivera"),
        summary="Platform engineer specializing in Kubernetes operations.",
        workExperience=[
            Experience(
                id=1,
                title="Platform Engineer",
                company="Northwind Ltd",
                years="2019-2024",
                description=["Operated production clusters."],
            )
        ],
        additional=AdditionalInfo(technicalSkills=["Python"]),
    )


def _job_k8s() -> JobDescription:
    return JobDescription(
        title="Platform Engineer",
        summary="Kubernetes platform role.",
        requirements=[Requirement(text="k8s", keywords=["k8s"])],
        keywords=["k8s"],
    )


def _evidence(resume: ResumeDocument) -> list[CandidateEvidence]:
    return build_candidate_evidence(resume)


class TestMapper:
    def test_replace_change_swaps_only_surface_term(self) -> None:
        sug = TerminologyAlignment(
            jd_keyword="k8s",
            current_wording="kubernetes",
            locations=["workExperience[0].description[0]"],
            canonical="kubernet",
        )
        bullet = "Ran workloads on Kubernetes across three regions."
        change = build_terminology_change(sug, "workExperience[0].description[0]", bullet)
        assert change.action == "replace"
        assert change.path == "workExperience[0].description[0]"
        # original == the FULL current field text (replace-verification gate).
        assert change.original == bullet
        # value == same text, only the surface token rewritten.
        assert change.value == "Ran workloads on k8s across three regions."
        assert "employer" in change.reason.lower()


class TestMinimalFreedom:
    def test_description_bullet_is_freedom_four(self) -> None:
        assert minimal_freedom_for_path("workExperience[0].description[0]") == 4

    def test_summary_is_freedom_six(self) -> None:
        assert minimal_freedom_for_path("summary") == 6

    def test_bare_skill_element_is_not_editable(self) -> None:
        # Only the whole additional.technicalSkills list is editable, not an
        # indexed element -> no in-place replace freedom exists.
        assert minimal_freedom_for_path("additional.technicalSkills[1]") is None

    def test_blocked_factual_field_has_no_freedom(self) -> None:
        assert minimal_freedom_for_path("workExperience[0].company") is None


class TestAcceptBulletTruthSafe:
    """NFR-1001 (a): an accepted swap changes only the surface term and
    validate_resume_truth still passes; REQ-1005 delta reported."""

    def test_accept_swap_passes_truth_and_reports_delta(self) -> None:
        resume = _resume_bullet()
        job = _job_k8s()
        evidence = _evidence(resume)

        sugs = analyze_terminology_alignment(job, resume)
        assert len(sugs) == 1
        sug = sugs[0]
        assert sug.jd_keyword == "k8s"
        location = "workExperience[0].description[0]"
        assert location in sug.locations

        result = accept_terminology_alignment(sug, location, resume, job, evidence)

        # Minimal freedom for a description bullet is F4.
        assert result.freedom == 4
        assert result.swap_applied
        assert result.applied and not result.rejected
        assert (
            result.resume.workExperience[0].description[0]
            == "Ran workloads on k8s across three regions."
        )
        # Truth still passes: the claim is unchanged, only the wording mirrored.
        assert result.truth_passed
        # Deterministic delta: score does not drop.
        assert result.delta.keyword_match_after >= result.delta.keyword_match_before
        assert result.delta.skills_coverage_after >= result.delta.skills_coverage_before
        # The mirrored literal term is now present in the resume.
        assert "k8s" in result.resume.workExperience[0].description[0]

    def test_summary_swap_freedom_six(self) -> None:
        resume = _resume_summary()
        job = _job_k8s()
        evidence = _evidence(resume)
        sug = next(
            s for s in analyze_terminology_alignment(job, resume) if "summary" in s.locations
        )
        result = accept_terminology_alignment(sug, "summary", resume, job, evidence)
        assert result.freedom == 6
        assert result.swap_applied
        assert result.resume.summary == "Platform engineer specializing in k8s operations."
        assert result.truth_passed

    def test_accept_is_deterministic(self) -> None:
        resume = _resume_bullet()
        job = _job_k8s()
        evidence = _evidence(resume)
        loc = "workExperience[0].description[0]"
        sug = next(s for s in analyze_terminology_alignment(job, resume) if loc in s.locations)
        a = accept_terminology_alignment(sug, loc, resume, job, evidence)
        b = accept_terminology_alignment(sug, loc, resume, job, evidence)
        assert a.change == b.change
        assert a.delta == b.delta
        assert a.resume == b.resume


class TestNoMatchKeywordCannotProduceChange:
    """NFR-1001 (b) / REQ-1003: a no-match keyword yields no suggestion, so the
    accept path has nothing to accept — a fabricated term can never be produced.
    """

    def test_absent_keyword_yields_no_suggestion(self) -> None:
        resume = _resume_bullet()
        job = JobDescription(
            title="Platform Engineer",
            summary="Terraform role.",
            requirements=[Requirement(text="Terraform", keywords=["Terraform"])],
            keywords=["Terraform"],
        )
        # No Terraform (or any alias of it) anywhere in the resume.
        sugs = analyze_terminology_alignment(job, resume)
        assert sugs == []
        # There is no TerminologyAlignment to accept -> the accept path is
        # structurally unreachable for a no-match keyword.


class TestUnsupportedAndBlockedLocationsRejected:
    """NFR-1001 (c): swaps whose location is a blocked factual field, or a
    non-editable skill element, are rejected by the policy gate and leave the
    resume unchanged."""

    def test_blocked_company_swap_rejected(self) -> None:
        resume = _resume_bullet()
        job = _job_k8s()
        evidence = _evidence(resume)
        # Adversarially point a suggestion at the employer field.
        sug = TerminologyAlignment(
            jd_keyword="k8s",
            current_wording="northwind",
            locations=["workExperience[0].company"],
            canonical="kubernet",
        )
        result = accept_terminology_alignment(
            sug, "workExperience[0].company", resume, job, evidence
        )
        assert result.applied == []
        assert result.rejected
        assert result.rejected[0].path == "workExperience[0].company"
        assert not result.swap_applied
        # Employer identity untouched.
        assert result.resume.workExperience[0].company == "Northwind Ltd"

    def test_truth_failed_swap_is_rejected_and_reverted(self) -> None:
        resume = ResumeDocument(
            personalInfo=PersonalInfo(name="Sam Rivera"),
            summary="Python",
        )
        job = JobDescription(
            title="Rust Engineer",
            summary="Rust role.",
            requirements=[Requirement(text="Rust", keywords=["Rust"])],
            keywords=["Rust"],
        )
        evidence = [
            *build_candidate_evidence(resume),
            CandidateEvidence(
                id="refute-rust",
                kind=EvidenceKind.USER_STATEMENT,
                content="Rust",
                tags=["refuted"],
                user_confirmed=True,
            ),
        ]
        sug = TerminologyAlignment(
            jd_keyword="Rust",
            current_wording="Python",
            locations=["summary"],
            canonical="adversarial",
        )

        result = accept_terminology_alignment(sug, "summary", resume, job, evidence)

        assert result.resume == resume
        assert result.applied == []
        assert result.rejected
        assert result.rejected[-1].reason_code is PolicyReasonCode.TRUTH_VALIDATION_FAILED
        assert result.swap_applied is False
        assert result.truth_passed is False
        assert result.field_after == "Python"

    def test_no_evidence_run_is_not_applied_with_explicit_reason(self) -> None:
        """RIT-T-0168 (1)+(2): with NO candidate evidence the truth gate cannot
        substantiate the new wording (passed=False). The swap must NOT be
        reported as applied, and the empty-evidence precondition must be surfaced
        as a named, actionable reason rather than a bare passed=False."""
        resume = _resume_bullet()
        job = _job_k8s()
        # Empty evidence: extract-evidence was never run.
        evidence: list[CandidateEvidence] = []

        sug = next(
            s
            for s in analyze_terminology_alignment(job, resume)
            if "workExperience[0].description[0]" in s.locations
        )
        result = accept_terminology_alignment(
            sug, "workExperience[0].description[0]", resume, job, evidence
        )

        # Contract: a truth-failed swap is never reported as applied.
        assert result.swap_applied is False
        assert result.applied == []
        assert result.truth_passed is False
        # Resume left untouched.
        assert result.resume == resume
        # The empty-evidence precondition is surfaced explicitly and points at
        # extract-evidence.
        assert "extract-evidence" in result.truth_reason
        assert result.rejected
        assert result.rejected[-1].reason_code is PolicyReasonCode.TRUTH_VALIDATION_FAILED

    def test_with_evidence_substantiating_swap_is_applied_and_passes(self) -> None:
        """RIT-T-0168 (b): with evidence that substantiates the (unchanged)
        claim, the swap is applied and truth passes."""
        resume = _resume_bullet()
        job = _job_k8s()
        evidence = _evidence(resume)

        sug = next(
            s
            for s in analyze_terminology_alignment(job, resume)
            if "workExperience[0].description[0]" in s.locations
        )
        result = accept_terminology_alignment(
            sug, "workExperience[0].description[0]", resume, job, evidence
        )

        assert result.swap_applied is True
        assert result.truth_passed is True
        assert result.applied and not result.rejected
        assert result.truth_reason == ""

    def test_applied_true_never_coexists_with_passed_false(self) -> None:
        """RIT-T-0168 (3): the two flags can never be swap_applied=True while
        truth_passed=False simultaneously, across the with/without-evidence and
        blocked-field scenarios."""
        resume = _resume_bullet()
        job = _job_k8s()
        loc = "workExperience[0].description[0]"
        sug = next(s for s in analyze_terminology_alignment(job, resume) if loc in s.locations)

        for evidence in ([], _evidence(resume)):
            result = accept_terminology_alignment(sug, loc, resume, job, evidence)
            assert not (result.swap_applied and not result.truth_passed)

    def test_bare_skill_element_swap_rejected(self) -> None:
        resume = _resume_bullet()
        job = _job_k8s()
        evidence = _evidence(resume)
        sug = next(
            s
            for s in analyze_terminology_alignment(job, resume)
            if "additional.technicalSkills[1]" in s.locations
        )
        result = accept_terminology_alignment(
            sug, "additional.technicalSkills[1]", resume, job, evidence
        )
        # Not an editable target -> rejected; the skill claim is preserved.
        assert result.applied == []
        assert result.rejected
        assert not result.swap_applied
        assert result.resume.additional.technicalSkills[1] == "Kubernetes"
