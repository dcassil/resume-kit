"""Deterministic candidate-feature extraction for the preference ranker.

Given a proposed candidate edit and its context, :func:`extract_features`
produces a :class:`~resume_kit_schemas.CandidateFeatures` record by CALLING the
existing deterministic scorers — it never reimplements or alters their math:

- ATS gain / keyword gain: :mod:`resume_kit_ats` + :mod:`resume_kit_matching`
  scored on the resume WITH the candidate applied versus the original resume.
- Unsupported-claim risk: :func:`resume_kit_evidence.validate_resume_truth`
  run over a minimal resume carrying only the candidate's text, so a fabricated
  claim surfaces as a truth-gate failure regardless of surrounding content.
- Voice / preference match: the candidate text compared against the learned
  :class:`~resume_kit_schemas.UserPreferenceProfile` (accepted / rejected
  phrases, tone, length preference).
- length_delta / specificity / repetition / section_fit: pure text signals.
- historical_success: acceptance rate of prior similar edits from the log
  records the caller supplies (never read from disk here).

Everything is pure and deterministic: no clock, no network, no LLM, no random.
All context is DATA passed in by the caller.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from resume_kit_ats import compute_ats_score
from resume_kit_evidence import validate_resume_truth
from resume_kit_matching import analyze_keyword_gaps, calculate_keyword_match
from resume_kit_schemas import (
    CandidateFeatures,
    EditFeedback,
    JobDescription,
    ResumeDocument,
    UserPreferenceProfile,
)
from resume_kit_schemas.evidence import CandidateEvidence
from resume_kit_schemas.provenance import ProvenanceStatus

# Resume sections a candidate edit may target. Bullet-list sections carry the
# candidate text as a description entry; scalar sections carry it inline.
CandidateSection = Literal[
    "summary",
    "experience",
    "project",
    "skill",
    "certification",
]

_TOKEN_RE = re.compile(r"[a-z0-9]+")
# Digits, %, and units read as concrete, quantified detail (specificity signal).
_NUMBER_RE = re.compile(r"\d")


class Candidate(BaseModel):
    """A single proposed edit to be scored and ranked.

    Immutable. ``proposed_text`` is the text the system wants to introduce;
    ``original_text`` is what it would replace (empty for a pure addition).
    ``section`` decides how the text is projected into a resume for the ATS /
    truth scorers. ``target_terms`` and ``edit_type`` are used for
    historical-success matching against prior log outcomes.
    """

    model_config = ConfigDict(frozen=True)

    candidate_id: str = Field(description="Stable identifier for this candidate edit.")
    section: CandidateSection = Field(description="Resume section the edit targets.")
    proposed_text: str = Field(description="Text the system proposes to introduce.")
    original_text: str = Field(
        default="", description="Text being replaced; empty for a pure addition."
    )
    edit_type: str = Field(
        default="", description="Edit strategy label, e.g. 'keyword_substitution'."
    )
    target_terms: list[str] = Field(
        default_factory=list, description="Terms the edit is trying to surface."
    )


class FeatureContext(BaseModel):
    """Deterministic, caller-supplied context for scoring a batch of candidates.

    Immutable. Carries the base resume the candidates edit, the target job, the
    ground-truth evidence set the truth gate validates against, and any prior
    edit-feedback records used for the historical-success signal. Nothing here is
    read from disk, the clock, or the network by the feature extractor.
    """

    model_config = ConfigDict(frozen=True)

    resume: ResumeDocument = Field(
        default_factory=ResumeDocument,
        description="Base resume the candidate edits are applied against.",
    )
    job: JobDescription = Field(
        default_factory=JobDescription, description="Target job the edits tailor for."
    )
    evidence: list[CandidateEvidence] = Field(
        default_factory=list, description="Ground-truth evidence for truth validation."
    )
    history: list[EditFeedback] = Field(
        default_factory=list, description="Prior edit-feedback records for the log signal."
    )


def _tokens(text: str) -> list[str]:
    """Lowercase alphanumeric tokens, in order (duplicates preserved)."""
    return _TOKEN_RE.findall(text.lower())


def _apply_candidate(resume: ResumeDocument, candidate: Candidate) -> ResumeDocument:
    """Return a copy of ``resume`` with the candidate's text applied to its section.

    Additive and non-destructive: the candidate text is appended to bullet-list
    sections and appended (space-joined) to scalar sections. This yields the
    "with candidate" resume the ATS / keyword scorers grade against the base.
    """
    data = resume.model_dump()
    text = candidate.proposed_text.strip()
    if not text:
        return resume.model_copy(deep=True)

    if candidate.section == "summary":
        summary = str(data.get("summary", "")).strip()
        data["summary"] = f"{summary} {text}".strip()
    elif candidate.section == "experience":
        experience = data.get("workExperience") or []
        if not experience:
            experience = [{"description": []}]
        experience[0].setdefault("description", []).append(text)
        data["workExperience"] = experience
    elif candidate.section == "project":
        projects = data.get("personalProjects") or []
        if not projects:
            projects = [{"description": []}]
        projects[0].setdefault("description", []).append(text)
        data["personalProjects"] = projects
    elif candidate.section == "skill":
        data.setdefault("additional", {}).setdefault("technicalSkills", []).append(text)
    elif candidate.section == "certification":
        data.setdefault("additional", {}).setdefault("certificationsTraining", []).append(text)

    return ResumeDocument.model_validate(data)


def _candidate_only_resume(candidate: Candidate) -> ResumeDocument:
    """Build a minimal resume carrying ONLY the candidate text in its section.

    Used for the per-candidate truth gate: validating a resume that contains
    nothing but the candidate's claim isolates whether THIS candidate is
    supported by the evidence, so surrounding (already-supported) content can
    never mask a fabricated candidate.
    """
    return _apply_candidate(ResumeDocument(), candidate)


def _ats_gain(context: FeatureContext, applied: ResumeDocument) -> float:
    """ATS overall-score delta (0..100 scale) from applying the candidate.

    Scores the base resume and the with-candidate resume through the SAME
    ``compute_ats_score`` engine (keyword %, gap lists computed via the matching
    engine) and returns the difference. No ATS math is reimplemented here.
    """
    base_score = _ats_overall(context.resume, context.job)
    applied_score = _ats_overall(applied, context.job)
    return applied_score - base_score


def _ats_overall(resume: ResumeDocument, job: JobDescription) -> float:
    match_pct = calculate_keyword_match(resume, job)
    gaps = analyze_keyword_gaps(job, resume, resume)
    score = compute_ats_score(
        resume,
        job,
        match_pct,
        gaps.non_injectable_keywords,
        gaps.injectable_keywords,
    )
    return score.overall_score


def _keyword_gain(context: FeatureContext, applied: ResumeDocument) -> float:
    """Job-keyword match-percentage delta (0..100 scale) from the candidate."""
    base = calculate_keyword_match(context.resume, context.job)
    after = calculate_keyword_match(applied, context.job)
    return after - base


def _unsupported_claim_risk(candidate: Candidate, evidence: list[CandidateEvidence]) -> float:
    """Risk in ``[0, 1]`` that the candidate introduces an unsupported claim.

    Runs :func:`validate_resume_truth` over a candidate-only resume. Returns
    ``1.0`` when the truth report flags any unsupported/contradicted claim (a
    hard truth-gate failure the ranker treats as a HARD BLOCK), otherwise the
    fraction of the candidate's claims that are not fully supported (0.0 when
    every claim is supported). Skill/certification sections with no evidence are
    inherently claims about the candidate, so an empty evidence set yields 1.0.
    """
    resume = _candidate_only_resume(candidate)
    report = validate_resume_truth(resume, evidence)
    if report.has_unsupported_or_contradicted:
        return 1.0
    total = len(report.claims)
    if total == 0:
        return 0.0
    # No hard failure: measure soft uncertainty (ambiguous / partially supported).
    uncertain = sum(
        1
        for claim in report.claims
        if claim.status
        in (ProvenanceStatus.AMBIGUOUS, ProvenanceStatus.PARTIALLY_SUPPORTED)
    )
    return uncertain / total


def _voice_match(candidate: Candidate, profile: UserPreferenceProfile) -> float:
    """How well the candidate matches the learned voice profile, in ``[0, 1]``.

    Starts neutral (0.5) and adjusts by transparent signals: rewards containing
    an accepted phrase, penalizes containing a rejected phrase or disliked
    pattern, and nudges toward the preferred length. Deterministic; clamped.
    """
    text = candidate.proposed_text.lower()
    score = 0.5

    for phrase in profile.accepted_phrases:
        if phrase.lower() in text:
            score += 0.2
    for phrase in profile.rejected_phrases:
        if phrase.lower() in text:
            score -= 0.3
    for pattern in profile.disliked_patterns:
        if pattern.lower() in text:
            score -= 0.2

    if profile.preferred_length is not None:
        delta = len(candidate.proposed_text) - len(candidate.original_text)
        wants_shorter = profile.preferred_length == "shorter" and delta <= 0
        wants_longer = profile.preferred_length in ("detailed", "longer") and delta > 0
        if wants_shorter or wants_longer:
            score += 0.1

    return max(0.0, min(1.0, score))


def _length_delta(candidate: Candidate) -> float:
    """Signed character-count change of proposed versus original text."""
    return float(len(candidate.proposed_text) - len(candidate.original_text))


def _specificity(candidate: Candidate) -> float:
    """Specificity signal in ``[0, 1]``: density of quantified, concrete detail.

    Higher when the text contains numbers/metrics and a richer vocabulary
    (unique tokens per total tokens), which correlate with concrete achievement
    statements over vague filler. Deterministic and bounded.
    """
    tokens = _tokens(candidate.proposed_text)
    if not tokens:
        return 0.0
    number_ratio = 1.0 if _NUMBER_RE.search(candidate.proposed_text) else 0.0
    unique_ratio = len(set(tokens)) / len(tokens)
    return max(0.0, min(1.0, 0.5 * number_ratio + 0.5 * unique_ratio))


def _repetition(candidate: Candidate) -> float:
    """Repetition penalty in ``[0, 1]``: how much the text repeats its own tokens.

    ``0.0`` for all-unique tokens; approaches ``1.0`` as tokens repeat. Higher
    is worse (the ranker weights this negatively).
    """
    tokens = _tokens(candidate.proposed_text)
    if len(tokens) <= 1:
        return 0.0
    unique = len(set(tokens))
    return max(0.0, min(1.0, 1.0 - unique / len(tokens)))


def _section_fit(candidate: Candidate) -> float:
    """How well the candidate's shape fits its section, in ``[0, 1]``.

    A deterministic length-appropriateness heuristic: skills/certifications read
    best as short phrases, summary/experience/project bullets as fuller
    sentences. Returns a bounded fit score centered on the section's ideal
    length band.
    """
    length = len(candidate.proposed_text.strip())
    if length == 0:
        return 0.0
    if candidate.section in ("skill", "certification"):
        # Short phrases fit best; long prose fits poorly.
        return max(0.0, min(1.0, 1.0 - max(0, length - 40) / 80.0))
    # Bullet-style sections: reward a substantive-but-not-bloated sentence.
    if length < 20:
        return max(0.0, min(1.0, length / 20.0))
    return max(0.0, min(1.0, 1.0 - max(0, length - 200) / 200.0))


def _historical_success(candidate: Candidate, history: list[EditFeedback]) -> float:
    """Acceptance rate of prior similar edits, in ``[0, 1]`` (0.5 when unknown).

    "Similar" = same ``edit_type`` when set, else same targeted section. An edit
    is counted a success when its outcome is ``accepted`` or ``accepted_modified``.
    Returns the neutral prior 0.5 when there is no comparable history, so an
    unseen edit type is neither rewarded nor punished.
    """
    accepted_outcomes = {"accepted", "accepted_modified"}
    relevant = [
        record
        for record in history
        if (
            record.edit_type == candidate.edit_type
            if candidate.edit_type
            else record.section == candidate.section
        )
    ]
    if not relevant:
        return 0.5
    successes = sum(1 for record in relevant if record.outcome in accepted_outcomes)
    return successes / len(relevant)


def extract_features(
    candidate: Candidate,
    context: FeatureContext,
    *,
    profile: UserPreferenceProfile,
) -> CandidateFeatures:
    """Extract a deterministic :class:`CandidateFeatures` record for ``candidate``.

    Reuses the existing scorers (ATS / matching / evidence-truth) and the learned
    preference profile; every value is a pure function of the inputs. See the
    module docstring for how each feature maps to its source scorer.

    Args:
        candidate: The proposed edit to score.
        context: Base resume, job, evidence, and prior log records (all data).
        profile: The learned :class:`UserPreferenceProfile` (type only; supply
            an empty profile when none is available).

    Returns:
        A fully populated :class:`CandidateFeatures`.
    """
    applied = _apply_candidate(context.resume, candidate)
    return CandidateFeatures(
        ats_gain=_ats_gain(context, applied),
        keyword_gain=_keyword_gain(context, applied),
        unsupported_claim_risk=_unsupported_claim_risk(candidate, context.evidence),
        voice_match=_voice_match(candidate, profile),
        length_delta=_length_delta(candidate),
        specificity=_specificity(candidate),
        repetition=_repetition(candidate),
        section_fit=_section_fit(candidate),
        historical_success=_historical_success(candidate, context.history),
    )
