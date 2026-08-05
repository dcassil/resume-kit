"""End-to-end integration test for the preference-learning loop (RIT-I-0013).

Drives the deterministic, offline loop the plugin skills orchestrate
(``rank-edits`` + ``log-edit-feedback``) directly over the
``resume_kit_feedback`` package:

    fixed synthetic feedback log
        -> derive_preferences (fixed ``now``)
        -> retrieve_preference_context
        -> HeuristicRanker.rank (small candidate set, incl. a fabricated one)
        -> append_edit_feedback (log an outcome)
        -> re-derive preferences

Everything is pinned to DATA — a fixed log and a fixed ``now`` — so the package
never reads the clock, the network, or an LLM. The test asserts:

* Reproducibility — two independent runs over the same inputs produce identical
  rankings, identical reason strings, and identical derived preferences.
* Truth hard-block — a fabricated candidate (unsupported claim, no evidence) is
  NEVER ranked, regardless of its other signals.
* Deterministic preference update — logging an outcome changes the derived
  preferences in a fixed, reproducible way.

The working directory is an isolated ``tmp_path``; no clock or randomness is
used (``now`` is passed explicitly everywhere).

Docstring lines in this module do NOT start with 'from <word>' (boundary rule
enforced by the venv regex guard).
"""

from __future__ import annotations

from pathlib import Path

from resume_kit_feedback import (
    Candidate,
    FeatureContext,
    HeuristicRanker,
    RankedCandidate,
    append_edit_feedback,
    derive_preferences,
    read_edit_feedback,
    retrieve_preference_context,
)
from resume_kit_feedback.retrieval import EditContext
from resume_kit_schemas import (
    EditFeedback,
    JobDescription,
    ResumeDocument,
    UserPreferenceProfile,
)
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind

# ---------------------------------------------------------------------------
# Fixed clock (DATA, never read from a wall clock)
# ---------------------------------------------------------------------------

_NOW = "2026-08-05T00:00:00+00:00"

# ---------------------------------------------------------------------------
# Fixed synthetic fixtures
# ---------------------------------------------------------------------------


def _resume() -> ResumeDocument:
    """A small, fixed resume the candidate edits are scored against."""
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "Pat Prefer", "email": "pat@example.com"},
            "summary": "Backend engineer focused on reliable services.",
            "workExperience": [
                {
                    "title": "Senior Engineer",
                    "company": "Acme",
                    "years": "2020 - Present",
                    "description": [
                        "Operated production Kubernetes clusters across regions.",
                        "Built Python services for high-throughput pipelines.",
                    ],
                }
            ],
            "additional": {"technicalSkills": ["Python", "Docker"]},
        }
    )


def _job() -> JobDescription:
    """A fixed job whose keywords the candidate edits try to surface."""
    return JobDescription.model_validate(
        {
            "title": "Platform Engineer",
            "company": "TechCo",
            "required_skills": ["Python", "Kubernetes", "Terraform"],
            "preferred_skills": [],
            "keywords": ["Python", "Kubernetes", "Terraform"],
            "description": (
                "Seeking a platform engineer with Python, Kubernetes, and "
                "Terraform experience."
            ),
        }
    )


def _evidence() -> list[CandidateEvidence]:
    """Ground-truth evidence: the candidate genuinely has Kubernetes."""
    return [
        CandidateEvidence(
            id="ev-k8s",
            kind=EvidenceKind.SKILL,
            content="Kubernetes cluster administration in production across regions.",
            tags=["Kubernetes"],
            user_confirmed=True,
        )
    ]


def _synthetic_log() -> list[EditFeedback]:
    """A FIXED synthetic feedback log used to derive preferences.

    Three recent accepted keyword-injection edits corroborate an acceptance
    signal for that edit type/section; one rejected edit corroborates a negative
    signal. All timestamps predate ``_NOW`` so decay is well-defined.
    """
    records: list[EditFeedback] = []
    for index in range(3):
        records.append(
            EditFeedback(
                edit_id=f"hist-accept-{index}",
                resume_id="resume-1",
                job_id="job-1",
                section="skill",
                edit_type="keyword_injection",
                original_text="",
                proposed_text="Kubernetes",
                final_text="Kubernetes",
                target_terms=["Kubernetes"],
                predicted_ats_gain=2.0,
                confidence=0.8,
                outcome="accepted",
                timestamp="2026-08-01T00:00:00+00:00",
            )
        )
    records.append(
        EditFeedback(
            edit_id="hist-reject-0",
            resume_id="resume-1",
            job_id="job-1",
            section="summary",
            edit_type="buzzword_padding",
            original_text="Backend engineer.",
            proposed_text="Synergistic backend engineer.",
            final_text=None,
            target_terms=["synergistic"],
            predicted_ats_gain=0.0,
            confidence=0.2,
            outcome="rejected",
            rejection_reason="buzzword",
            timestamp="2026-08-01T00:00:00+00:00",
        )
    )
    return records


def _candidates() -> list[Candidate]:
    """A small candidate set including one fabricated (unsupported) candidate.

    - ``cand-k8s`` — truthful: Kubernetes, backed by evidence (risk 0.0).
    - ``cand-fabricated`` — an unsupported skill claim with NO evidence backing
      it, so the per-candidate truth gate fails and it must be hard-blocked.
    """
    return [
        Candidate(
            candidate_id="cand-k8s",
            section="skill",
            proposed_text="Kubernetes",
            edit_type="keyword_injection",
            target_terms=["Kubernetes"],
        ),
        Candidate(
            candidate_id="cand-fabricated",
            section="skill",
            proposed_text="Quantum teleportation of distributed blockchains",
            edit_type="keyword_injection",
            target_terms=["Quantum teleportation"],
        ),
    ]


def _edit_context() -> EditContext:
    """The pending edit context used for Preference-RAG retrieval."""
    return EditContext(
        section="skill",
        target_terms=["Kubernetes"],
        edit_type="keyword_injection",
        aggressiveness="minimal",
    )


# ---------------------------------------------------------------------------
# One full pass of the loop, over an isolated working dir
# ---------------------------------------------------------------------------


def _run_loop(
    base_path: Path,
) -> tuple[UserPreferenceProfile, list[RankedCandidate], str]:
    """Run derive -> retrieve -> rank over the fixed log; return the results.

    Returns the derived profile, the ranked candidates, and the retrieved
    preference summary. Deterministic: all inputs are fixed DATA.
    """
    records = _synthetic_log()
    profile = derive_preferences(records, now=_NOW, base_path=base_path)
    retrieved = retrieve_preference_context(
        _edit_context(), records, profile, k=3
    )
    feature_context = FeatureContext(
        resume=_resume(), job=_job(), evidence=_evidence(), history=records
    )
    ranked = HeuristicRanker().rank(
        _candidates(), feature_context, profile=profile
    )
    return profile, ranked, retrieved.summary


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_truth_hard_block_excludes_fabricated_candidate(tmp_path: Path) -> None:
    """The fabricated, unsupported candidate must NEVER appear in the ranking."""
    _profile, ranked, _summary = _run_loop(tmp_path)

    ranked_ids = {rc.candidate.candidate_id for rc in ranked}
    assert "cand-fabricated" not in ranked_ids, (
        "A truth-failing candidate must be hard-blocked, never ranked"
    )
    assert "cand-k8s" in ranked_ids, (
        "The truthful, evidence-backed candidate must survive the truth gate"
    )
    # The fabricated candidate carries a full unsupported-claim risk; the
    # surviving one does not.
    (survivor,) = ranked
    assert survivor.candidate.candidate_id == "cand-k8s"
    assert survivor.features.unsupported_claim_risk == 0.0


def test_loop_is_reproducible(tmp_path: Path) -> None:
    """Two independent runs produce identical rankings, reasons, and preferences."""
    run_a = tmp_path / "run_a"
    run_b = tmp_path / "run_b"
    run_a.mkdir()
    run_b.mkdir()

    profile_a, ranked_a, summary_a = _run_loop(run_a)
    profile_b, ranked_b, summary_b = _run_loop(run_b)

    # Identical derived preferences.
    assert profile_a == profile_b

    # Identical retrieved summary.
    assert summary_a == summary_b

    # Identical ranking: same order, ids, scores, and reason strings.
    assert len(ranked_a) == len(ranked_b)
    for rc_a, rc_b in zip(ranked_a, ranked_b, strict=True):
        assert rc_a.candidate.candidate_id == rc_b.candidate.candidate_id
        assert rc_a.score == rc_b.score
        assert rc_a.reason == rc_b.reason
        assert rc_a.features == rc_b.features


def test_logging_outcome_updates_preferences_deterministically(
    tmp_path: Path,
) -> None:
    """Appending an outcome to the log changes the re-derived preferences.

    The update is deterministic: re-deriving over the appended log twice (with
    the same ``now``) yields identical profiles, and the new accepted phrase the
    outcome corroborates crosses into the derived profile.
    """
    base_path = tmp_path

    # Baseline: derive over the fixed log and persist it.
    records = _synthetic_log()
    for record in records:
        append_edit_feedback(record, base_path=base_path)
    baseline = derive_preferences(
        read_edit_feedback(base_path=base_path), now=_NOW, base_path=base_path
    )
    # "terraform" is not yet corroborated as an accepted phrase.
    assert "terraform" not in baseline.accepted_phrases

    # Log three accepted Terraform injections (the outcome the user just made),
    # enough corroboration to clear the MODERATE confidence tier.
    for index in range(3):
        append_edit_feedback(
            EditFeedback(
                edit_id=f"new-accept-terraform-{index}",
                resume_id="resume-1",
                job_id="job-1",
                section="skill",
                edit_type="keyword_injection",
                original_text="",
                proposed_text="Terraform",
                final_text="Terraform",
                target_terms=["Terraform"],
                predicted_ats_gain=2.0,
                confidence=0.8,
                outcome="accepted",
                timestamp=_NOW,
            ),
            base_path=base_path,
        )

    updated = derive_preferences(
        read_edit_feedback(base_path=base_path), now=_NOW, base_path=base_path
    )

    # The outcome changed the derived preferences deterministically.
    assert updated != baseline
    assert "terraform" in updated.accepted_phrases, (
        "Logging accepted Terraform injections must surface it as an accepted phrase"
    )

    # Re-deriving the same appended log with the same ``now`` is identical.
    again = derive_preferences(
        read_edit_feedback(base_path=base_path), now=_NOW, base_path=base_path
    )
    assert again == updated
