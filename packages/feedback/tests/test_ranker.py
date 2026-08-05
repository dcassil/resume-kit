"""Tests for the pluggable heuristic ranker + truth hard-block."""

from __future__ import annotations

from resume_kit_feedback.features import Candidate, FeatureContext
from resume_kit_feedback.ranker import (
    DEFAULT_WEIGHTS,
    HeuristicRanker,
    RankedCandidate,
    Ranker,
)
from resume_kit_schemas import (
    JobDescription,
    ResumeDocument,
    UserPreferenceProfile,
)
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_schemas.job import Requirement

EMPTY_PROFILE = UserPreferenceProfile()


def _context() -> FeatureContext:
    resume = ResumeDocument.model_validate(
        {
            "summary": "Backend engineer with a decade of Python.",
            "workExperience": [
                {
                    "company": "Acme",
                    "title": "Senior Engineer",
                    "description": ["Led a team of four"],
                }
            ],
            "additional": {"technicalSkills": ["Python"]},
        }
    )
    job = JobDescription(
        requirements=[Requirement(text="Kubernetes", keywords=["Kubernetes"])],
        keywords=["Kubernetes", "Terraform"],
    )
    evidence = [
        CandidateEvidence(
            id="e1", kind=EvidenceKind.SKILL, content="Kubernetes", user_confirmed=True
        ),
        CandidateEvidence(
            id="e2", kind=EvidenceKind.SKILL, content="Terraform", user_confirmed=True
        ),
    ]
    return FeatureContext(resume=resume, job=job, evidence=evidence)


def _supported() -> Candidate:
    return Candidate(
        candidate_id="c-kube",
        section="skill",
        proposed_text="Kubernetes",
        edit_type="keyword_addition",
    )


def _fabricated() -> Candidate:
    return Candidate(
        candidate_id="c-fake",
        section="certification",
        proposed_text="Nobel Prize in Distributed Systems 2019",
    )


def test_heuristic_ranker_satisfies_protocol() -> None:
    assert isinstance(HeuristicRanker(), Ranker)


def test_rank_returns_ranked_candidates() -> None:
    result = HeuristicRanker().rank([_supported()], _context(), profile=EMPTY_PROFILE)
    assert len(result) == 1
    assert isinstance(result[0], RankedCandidate)
    assert result[0].reason


def test_truth_hard_block_excludes_fabricated() -> None:
    result = HeuristicRanker().rank(
        [_supported(), _fabricated()], _context(), profile=EMPTY_PROFILE
    )
    ids = [rc.candidate.candidate_id for rc in result]
    assert "c-fake" not in ids
    assert "c-kube" in ids


def test_truth_hard_block_excludes_even_with_forced_high_features() -> None:
    """A fabricated candidate is dropped regardless of otherwise-strong signals."""
    # Give the fabricated candidate an edit_type with a perfect historical record
    # and rich specificity — it must STILL be excluded by the hard block.
    fabricated = _fabricated().model_copy(
        update={"proposed_text": "Nobel Prize in Distributed Systems 2019 with 99% impact"}
    )
    result = HeuristicRanker().rank([fabricated], _context(), profile=EMPTY_PROFILE)
    assert result == []


def test_ordering_is_by_score_desc() -> None:
    strong = _supported()
    weak = Candidate(
        candidate_id="c-weak",
        section="skill",
        proposed_text="Terraform Terraform Terraform",
        edit_type="keyword_addition",
    )
    result = HeuristicRanker().rank([weak, strong], _context(), profile=EMPTY_PROFILE)
    scores = [rc.score for rc in result]
    assert scores == sorted(scores, reverse=True)


def test_tie_break_is_stable_by_id() -> None:
    a = Candidate(candidate_id="c-b", section="skill", proposed_text="Kubernetes")
    b = Candidate(candidate_id="c-a", section="skill", proposed_text="Kubernetes")
    result = HeuristicRanker().rank([a, b], _context(), profile=EMPTY_PROFILE)
    # Identical features → identical score → id tie-break puts "c-a" first.
    assert [rc.candidate.candidate_id for rc in result] == ["c-a", "c-b"]


def test_reason_names_contributors() -> None:
    result = HeuristicRanker().rank([_supported()], _context(), profile=EMPTY_PROFILE)
    reason = result[0].reason
    assert "boosted by" in reason or "reduced by" in reason


def test_multi_objective_weights_documented_and_balanced() -> None:
    # Acceptance is present but not the sole positive objective.
    positives = {k for k, v in DEFAULT_WEIGHTS.items() if v > 0}
    assert "acceptance" in positives
    assert positives - {"acceptance"}  # other upside objectives exist
    assert DEFAULT_WEIGHTS["fact"] < 0  # fact-support is a guardrail


def test_determinism_repeated_ranking() -> None:
    candidates = [_supported(), _fabricated()]
    first = HeuristicRanker().rank(candidates, _context(), profile=EMPTY_PROFILE)
    second = HeuristicRanker().rank(candidates, _context(), profile=EMPTY_PROFILE)
    assert [(rc.candidate.candidate_id, rc.score, rc.reason) for rc in first] == [
        (rc.candidate.candidate_id, rc.score, rc.reason) for rc in second
    ]


def test_custom_weights_override() -> None:
    ranker = HeuristicRanker(weights={**DEFAULT_WEIGHTS, "acceptance": 0.9})
    result = ranker.rank([_supported()], _context(), profile=EMPTY_PROFILE)
    assert len(result) == 1
