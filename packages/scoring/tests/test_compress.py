"""Claim-gated compression candidate tests."""

from __future__ import annotations

from resume_kit_policy import (
    InformationalShapeBudgets,
    ResumeShapePolicy,
    default_shape_policy,
)
from resume_kit_schemas import Experience, PersonalInfo, ResumeDocument
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind
from resume_kit_scoring.compress import (
    CompressionCandidate,
    compress_bullet,
    compress_summary,
)


def _policy(
    *,
    max_summary_words: int | None = 8,
    max_bullet_words: int | None = 8,
) -> ResumeShapePolicy:
    budgets = InformationalShapeBudgets(
        max_summary_words=max_summary_words,
        max_bullet_words=max_bullet_words,
    )
    return default_shape_policy().model_copy(update={"informational_budgets": budgets})


def _resume(
    *,
    summary: str = "Builds reliable systems.",
    bullet: str = "Built reliable APIs.",
) -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Jane Engineer",
            email="jane@example.com",
        ),
        summary=summary,
        workExperience=[
            Experience(
                company="Acme",
                title="Staff Engineer",
                description=[bullet],
            )
        ],
    )


def _evidence(*records: CandidateEvidence) -> list[CandidateEvidence]:
    return list(records)


def _summary_evidence(text: str) -> CandidateEvidence:
    return CandidateEvidence(
        id="summary",
        kind=EvidenceKind.MASTER_RESUME,
        content=text,
        user_confirmed=True,
    )


def _work_evidence(text: str) -> CandidateEvidence:
    return CandidateEvidence(
        id="work",
        kind=EvidenceKind.WORK_HISTORY,
        content=text,
        tags=["Acme"],
        user_confirmed=True,
    )


def test_compress_summary_returns_claim_preserving_candidate() -> None:
    original = (
        "Successfully and effectively built Python APIs for Acme improving uptime 30% "
        "across platforms"
    )
    rewritten = "Built Python APIs for Acme improving uptime 30%"
    resume = _resume(summary=original)

    candidate = compress_summary(
        resume,
        _evidence(_summary_evidence(rewritten)),
        policy=_policy(max_summary_words=8),
        phrasing=lambda _text, _budget: rewritten,
    )

    assert isinstance(candidate, CompressionCandidate)
    assert candidate.path == "summary"
    assert candidate.claim_preserving is True
    assert len(candidate.rewritten.split()) <= 8
    assert "Python" in candidate.rewritten
    assert "Acme" in candidate.rewritten
    assert "30%" in candidate.rewritten


def test_compress_bullet_returns_false_when_rewrite_fails_truth_gate() -> None:
    original = (
        "Built Acme payment platform with Python reduced latency 35% and served "
        "2M users"
    )
    resume = _resume(bullet=original)

    candidate = compress_bullet(
        resume,
        _evidence(_work_evidence(original)),
        work_index=0,
        achievement_index=0,
        policy=_policy(max_bullet_words=3),
        phrasing=lambda _text, _budget: "Mentored interns",
    )

    assert isinstance(candidate, CompressionCandidate)
    assert candidate.path == "workExperience[0].description[0]"
    assert candidate.claim_preserving is False
    assert candidate.rewritten == "Mentored interns"
    assert "could not compress truthfully" in candidate.reason


def test_under_budget_summary_and_bullet_return_none() -> None:
    resume = _resume(summary="Builds APIs.", bullet="Built APIs.")
    policy = _policy(max_summary_words=3, max_bullet_words=3)

    assert compress_summary(resume, [], policy=policy) is None
    assert (
        compress_bullet(
            resume,
            [],
            work_index=0,
            achievement_index=0,
            policy=policy,
        )
        is None
    )


def test_max_bullet_words_none_returns_none() -> None:
    resume = _resume(bullet="one two three four five six")

    candidate = compress_bullet(
        resume,
        [],
        work_index=0,
        achievement_index=0,
        policy=_policy(max_bullet_words=None),
    )

    assert candidate is None


def test_compression_is_deterministic_with_same_phrasing() -> None:
    original = "Successfully built Python APIs for Acme improving uptime 30%"
    rewritten = "Built Python APIs for Acme improving uptime 30%"
    resume = _resume(summary=original)
    evidence = _evidence(_summary_evidence(rewritten))
    policy = _policy(max_summary_words=8)

    first = compress_summary(
        resume,
        evidence,
        policy=policy,
        phrasing=lambda _text, _budget: rewritten,
    )
    second = compress_summary(
        resume,
        evidence,
        policy=policy,
        phrasing=lambda _text, _budget: rewritten,
    )

    assert first is not None
    assert second is not None
    assert first.model_dump() == second.model_dump()
