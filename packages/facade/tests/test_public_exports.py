"""Smoke-test that all public symbols are importable from resume_kit_facade."""

from __future__ import annotations


def test_all_public_exports_importable() -> None:
    from resume_kit_facade import (
        REGISTRY,
        AlignResumeRequest,
        BuildCandidateEvidenceRequest,
        CapabilityOptions,
        CheckResumeAtsRequest,
        CheckResumeJobMatchRequest,
        CompareResumeVersionsRequest,
        ExtractJobDescriptionRequest,
        ExtractResumeRequest,
        IdentifyResumeGapsRequest,
        SelectBestResumeRequest,
        ValidateResumeTruthRequest,
        align_resume,
        build_candidate_evidence_capability,
        check_resume_ats,
        check_resume_job_match,
        compare_resume_versions,
        extract_job_description,
        extract_resume,
        identify_resume_gaps,
        select_best_resume,
        validate_resume_truth_capability,
    )

    assert isinstance(REGISTRY, dict)
    assert len(REGISTRY) == 11

    assert callable(align_resume)
    assert callable(build_candidate_evidence_capability)
    assert callable(check_resume_ats)
    assert callable(check_resume_job_match)
    assert callable(compare_resume_versions)
    assert callable(extract_job_description)
    assert callable(extract_resume)
    assert callable(identify_resume_gaps)
    assert callable(select_best_resume)
    assert callable(validate_resume_truth_capability)

    assert CapabilityOptions is not None
    assert AlignResumeRequest is not None
    assert BuildCandidateEvidenceRequest is not None
    assert CheckResumeAtsRequest is not None
    assert CheckResumeJobMatchRequest is not None
    assert CompareResumeVersionsRequest is not None
    assert ExtractJobDescriptionRequest is not None
    assert ExtractResumeRequest is not None
    assert IdentifyResumeGapsRequest is not None
    assert SelectBestResumeRequest is not None
    assert ValidateResumeTruthRequest is not None


def test_all_names_in_dunder_all() -> None:
    import resume_kit_facade

    assert hasattr(resume_kit_facade, "__all__")
    all_names = resume_kit_facade.__all__
    assert "REGISTRY" in all_names
    assert "CapabilityOptions" in all_names
    assert "extract_resume" in all_names
