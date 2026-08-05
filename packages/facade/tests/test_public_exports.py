"""Smoke-test that all public symbols are importable from resume_kit_facade."""

from __future__ import annotations


def test_all_public_exports_importable() -> None:
    from resume_kit_facade import (
        REGISTRY,
        AddEvidenceRequest,
        AddEvidenceResult,
        AlignResumeRequest,
        AlignTerminologyRequest,
        AlignTerminologyResult,
        BuildCandidateEvidenceRequest,
        CapabilityOptions,
        CheckAtsStructureRequest,
        CheckResumeAtsRequest,
        CheckResumeJobMatchRequest,
        CompareResumeVersionsRequest,
        ExportResumeRequest,
        ExtractJobDescriptionRequest,
        ExtractResumeRequest,
        ExtractResumeTextRequest,
        IdentifyResumeGapsRequest,
        InitProjectRequest,
        ProjectConfig,
        RankEditCandidatesRequest,
        RankEditCandidatesResult,
        RecordEditFeedbackRequest,
        RecordEditFeedbackResult,
        RefreshPreferencesRequest,
        SelectBestResumeRequest,
        SetActiveRequest,
        SuggestTerminologyRequest,
        TerminologyAlignmentDelta,
        ValidateFaithfulnessRequest,
        ValidateResumeTruthRequest,
        add_evidence_capability,
        align_resume,
        align_terminology,
        build_candidate_evidence_capability,
        check_ats_structure,
        check_resume_ats,
        check_resume_job_match,
        compare_resume_versions,
        export_resume,
        extract_job_description,
        extract_resume,
        extract_resume_text_capability,
        identify_resume_gaps,
        init_project,
        init_project_capability,
        load_config,
        rank_edit_candidates_capability,
        record_edit_feedback_capability,
        refresh_preferences_capability,
        save_config,
        select_best_resume,
        set_active,
        set_active_capability,
        suggest_terminology,
        validate_faithfulness_capability,
        validate_resume_truth_capability,
    )

    assert isinstance(REGISTRY, dict)
    assert len(REGISTRY) == 22
    assert "validate-faithfulness" in REGISTRY
    assert "extract-resume-text" in REGISTRY
    assert "export-resume" in REGISTRY
    assert "check-ats-structure" in REGISTRY
    assert "suggest-terminology" in REGISTRY
    assert "align-terminology" in REGISTRY
    assert "init-project" in REGISTRY
    assert "set-active" in REGISTRY
    assert "record-edit-feedback" in REGISTRY
    assert "rank-edit-candidates" in REGISTRY
    assert "refresh-preferences" in REGISTRY
    assert "add-evidence" in REGISTRY

    assert callable(init_project_capability)
    assert callable(add_evidence_capability)
    assert callable(record_edit_feedback_capability)
    assert callable(rank_edit_candidates_capability)
    assert callable(refresh_preferences_capability)
    assert callable(set_active_capability)
    assert callable(init_project)
    assert callable(load_config)
    assert callable(save_config)
    assert callable(set_active)
    assert ProjectConfig is not None
    assert InitProjectRequest is not None
    assert AddEvidenceRequest is not None
    assert RecordEditFeedbackRequest is not None
    assert RankEditCandidatesRequest is not None
    assert RefreshPreferencesRequest is not None
    assert SetActiveRequest is not None

    assert callable(suggest_terminology)
    assert callable(align_terminology)
    assert AlignTerminologyRequest is not None
    assert SuggestTerminologyRequest is not None
    assert AlignTerminologyResult is not None
    assert TerminologyAlignmentDelta is not None

    assert callable(align_resume)
    assert callable(build_candidate_evidence_capability)
    assert callable(check_ats_structure)
    assert callable(check_resume_ats)
    assert callable(check_resume_job_match)
    assert callable(compare_resume_versions)
    assert callable(export_resume)
    assert callable(extract_job_description)
    assert callable(extract_resume)
    assert callable(extract_resume_text_capability)
    assert callable(identify_resume_gaps)
    assert callable(select_best_resume)
    assert callable(validate_resume_truth_capability)
    assert callable(validate_faithfulness_capability)
    assert ValidateFaithfulnessRequest is not None
    assert AddEvidenceResult is not None
    assert RecordEditFeedbackResult is not None
    assert RankEditCandidatesResult is not None

    assert CapabilityOptions is not None
    assert AlignResumeRequest is not None
    assert BuildCandidateEvidenceRequest is not None
    assert CheckAtsStructureRequest is not None
    assert CheckResumeAtsRequest is not None
    assert CheckResumeJobMatchRequest is not None
    assert CompareResumeVersionsRequest is not None
    assert ExportResumeRequest is not None
    assert ExtractJobDescriptionRequest is not None
    assert ExtractResumeRequest is not None
    assert ExtractResumeTextRequest is not None
    assert IdentifyResumeGapsRequest is not None
    assert SelectBestResumeRequest is not None
    assert ValidateResumeTruthRequest is not None


def test_all_names_in_dunder_all() -> None:
    import resume_kit_facade

    assert hasattr(resume_kit_facade, "__all__")
    all_names = resume_kit_facade.__all__
    assert "REGISTRY" in all_names
    assert "CapabilityOptions" in all_names
    assert "ExportResumeRequest" in all_names
    assert "export_resume" in all_names
    assert "extract_resume" in all_names
