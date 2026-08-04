"""Smoke-test that all public symbols are importable from resume_kit_job_hunter_bridge."""

from __future__ import annotations


def test_all_public_exports_importable() -> None:
    from resume_kit_job_hunter_bridge import (
        ResumeJobAnalysis,
        align_resume_for_job,
        align_resume_for_job_sync,
        analyze_resume_for_job,
        analyze_resume_for_job_sync,
        build_evidence,
        build_evidence_sync,
        validate_truth,
        validate_truth_sync,
    )

    assert ResumeJobAnalysis is not None
    assert callable(analyze_resume_for_job)
    assert callable(align_resume_for_job)
    assert callable(validate_truth)
    assert callable(build_evidence)
    assert callable(analyze_resume_for_job_sync)
    assert callable(align_resume_for_job_sync)
    assert callable(validate_truth_sync)
    assert callable(build_evidence_sync)


def test_all_names_in_dunder_all() -> None:
    import resume_kit_job_hunter_bridge

    assert hasattr(resume_kit_job_hunter_bridge, "__all__")
    all_names = resume_kit_job_hunter_bridge.__all__
    assert "ResumeJobAnalysis" in all_names
    assert "analyze_resume_for_job" in all_names
    assert "align_resume_for_job" in all_names
    assert "validate_truth" in all_names
    assert "build_evidence" in all_names
