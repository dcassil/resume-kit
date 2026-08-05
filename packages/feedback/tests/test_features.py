"""Tests for deterministic candidate-feature extraction."""

from __future__ import annotations

from resume_kit_feedback.features import (
    Candidate,
    FeatureContext,
    extract_features,
)
from resume_kit_schemas import (
    EditFeedback,
    JobDescription,
    ResumeDocument,
    UserPreferenceProfile,
)
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.job import Requirement

EMPTY_PROFILE = UserPreferenceProfile()


def _resume() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "summary": "Backend engineer with a decade of Python.",
            "workExperience": [
                {
                    "company": "Acme",
                    "title": "Senior Engineer",
                    "description": ["Built a payments API", "Led a team of four"],
                }
            ],
            "additional": {"technicalSkills": ["Python", "PostgreSQL"]},
        }
    )


def _job() -> JobDescription:
    return JobDescription(
        title="Staff Engineer",
        requirements=[Requirement(text="Kubernetes", keywords=["Kubernetes", "k8s"])],
        keywords=["Kubernetes", "Terraform"],
    )


def _evidence() -> list[CandidateEvidence]:
    return [
        CandidateEvidence(
            id="e1",
            kind=EvidenceKind.SKILL,
            content="Kubernetes",
            user_confirmed=True,
        ),
        CandidateEvidence(
            id="e2",
            kind=EvidenceKind.WORK_HISTORY,
            content="Led a team of four",
            user_confirmed=True,
        ),
    ]


def _context() -> FeatureContext:
    return FeatureContext(resume=_resume(), job=_job(), evidence=_evidence())


def _supported_candidate() -> Candidate:
    return Candidate(
        candidate_id="c-supported",
        section="skill",
        proposed_text="Kubernetes",
        edit_type="keyword_addition",
        target_terms=["Kubernetes"],
    )


def test_keyword_gain_positive_for_missing_job_keyword() -> None:
    features = extract_features(_supported_candidate(), _context(), profile=EMPTY_PROFILE)
    assert features.keyword_gain > 0.0


def test_ats_gain_computed() -> None:
    features = extract_features(_supported_candidate(), _context(), profile=EMPTY_PROFILE)
    # Adding a matching JD keyword should not decrease the ATS composite.
    assert features.ats_gain >= 0.0


def test_unsupported_claim_risk_low_for_supported() -> None:
    features = extract_features(_supported_candidate(), _context(), profile=EMPTY_PROFILE)
    assert features.unsupported_claim_risk < 1.0


def test_unsupported_claim_risk_low_for_project_alias(tmp_path) -> None:
    alias_file = tmp_path / "aliases.json"
    alias_file.write_text('{"version": 1, "aliases": {"quibblewidget": ["zorbulator"]}}')
    context = FeatureContext(
        resume=_resume(),
        job=_job(),
        evidence=[
            CandidateEvidence(
                id="alias-skill",
                kind=EvidenceKind.SKILL,
                content="quibblewidget",
                user_confirmed=True,
            )
        ],
        alias_file=str(alias_file),
    )
    candidate = Candidate(
        candidate_id="c-alias",
        section="skill",
        proposed_text="zorbulator",
    )
    features = extract_features(candidate, context, profile=EMPTY_PROFILE)
    assert features.unsupported_claim_risk < 1.0


def test_unsupported_claim_risk_hard_for_fabricated() -> None:
    fabricated = Candidate(
        candidate_id="c-fab",
        section="skill",
        proposed_text="Rocket Surgery Certification from Mars University",
    )
    features = extract_features(fabricated, _context(), profile=EMPTY_PROFILE)
    assert features.unsupported_claim_risk == 1.0


def test_length_delta_signed() -> None:
    candidate = Candidate(
        candidate_id="c-len",
        section="summary",
        proposed_text="Longer text here",
        original_text="Short",
    )
    features = extract_features(candidate, _context(), profile=EMPTY_PROFILE)
    assert features.length_delta == float(len("Longer text here") - len("Short"))


def test_specificity_rewards_numbers() -> None:
    with_number = Candidate(
        candidate_id="c-num",
        section="experience",
        proposed_text="Cut latency by 40 percent across services",
    )
    without_number = Candidate(
        candidate_id="c-plain",
        section="experience",
        proposed_text="Improved the overall system performance greatly",
    )
    high = extract_features(with_number, _context(), profile=EMPTY_PROFILE)
    low = extract_features(without_number, _context(), profile=EMPTY_PROFILE)
    assert high.specificity > low.specificity


def test_repetition_penalizes_repeats() -> None:
    repetitive = Candidate(
        candidate_id="c-rep",
        section="experience",
        proposed_text="team team team team team",
    )
    varied = Candidate(
        candidate_id="c-var",
        section="experience",
        proposed_text="Led a cross functional delivery team",
    )
    rep = extract_features(repetitive, _context(), profile=EMPTY_PROFILE)
    var = extract_features(varied, _context(), profile=EMPTY_PROFILE)
    assert rep.repetition > var.repetition


def test_section_fit_skill_short_beats_long() -> None:
    short = Candidate(candidate_id="s1", section="skill", proposed_text="Go")
    longform = Candidate(
        candidate_id="s2",
        section="skill",
        proposed_text="An extremely long winded description of a skill " * 4,
    )
    short_f = extract_features(short, _context(), profile=EMPTY_PROFILE)
    long_f = extract_features(longform, _context(), profile=EMPTY_PROFILE)
    assert short_f.section_fit > long_f.section_fit


def test_voice_match_rewards_accepted_phrase() -> None:
    profile = UserPreferenceProfile(accepted_phrases=["led a team"])
    candidate = Candidate(
        candidate_id="v1",
        section="experience",
        proposed_text="Led a team of engineers",
    )
    features = extract_features(candidate, _context(), profile=profile)
    assert features.voice_match > 0.5


def test_voice_match_penalizes_rejected_phrase() -> None:
    profile = UserPreferenceProfile(rejected_phrases=["synergy"])
    candidate = Candidate(
        candidate_id="v2",
        section="summary",
        proposed_text="Drove cross-team synergy",
    )
    features = extract_features(candidate, _context(), profile=profile)
    assert features.voice_match < 0.5


def test_historical_success_from_log() -> None:
    history = [
        EditFeedback(
            edit_id="h1",
            resume_id="r",
            job_id="j",
            section="skill",
            edit_type="keyword_addition",
            original_text="",
            proposed_text="Kubernetes",
            predicted_ats_gain=0.1,
            confidence=0.9,
            outcome="accepted",
            timestamp="2026-01-01T00:00:00Z",
        ),
        EditFeedback(
            edit_id="h2",
            resume_id="r",
            job_id="j",
            section="skill",
            edit_type="keyword_addition",
            original_text="",
            proposed_text="Terraform",
            predicted_ats_gain=0.1,
            confidence=0.9,
            outcome="rejected",
            timestamp="2026-01-02T00:00:00Z",
        ),
    ]
    context = FeatureContext(resume=_resume(), job=_job(), evidence=_evidence(), history=history)
    features = extract_features(_supported_candidate(), context, profile=EMPTY_PROFILE)
    assert features.historical_success == 0.5


def test_historical_success_neutral_without_history() -> None:
    features = extract_features(_supported_candidate(), _context(), profile=EMPTY_PROFILE)
    assert features.historical_success == 0.5


def test_deterministic_repeated_extraction() -> None:
    context = _context()
    candidate = _supported_candidate()
    first = extract_features(candidate, context, profile=EMPTY_PROFILE)
    second = extract_features(candidate, context, profile=EMPTY_PROFILE)
    assert first == second
