"""Claim-gated compression candidates for canonical resume content."""

from __future__ import annotations

import inspect
import re
from collections.abc import Callable
from typing import cast

from pydantic import BaseModel
from resume_kit_evidence import validate_resume_truth
from resume_kit_policy import ResumeShapePolicy
from resume_kit_schemas.canonical import Resume
from resume_kit_schemas.evidence import CandidateEvidence
from resume_kit_schemas.provenance import ProvenanceStatus
from resume_kit_schemas.results import TruthReport
from resume_kit_terms import AliasIndex, load_effective_alias_index

from .best_practices import summary_too_long
from .projection import project_builddoc_from_canonical

Phrasing = Callable[[str, int], str]

_SUMMARY_PATH = "basics.summary"
_SUMMARY_TRUTH_PATH = "summary"
_FAILURE_STATUSES = frozenset(
    {
        ProvenanceStatus.UNSUPPORTED,
        ProvenanceStatus.CONTRADICTED,
    }
)
_FILLER_WORDS = (
    "very",
    "really",
    "successfully",
    "effectively",
    "highly",
    "proven",
    "seasoned",
    "results-driven",
    "detail-oriented",
)
_WHITESPACE_RE = re.compile(r"\s+")
_VALIDATE_ACCEPTS_ALIAS_INDEX = (
    "alias_index" in inspect.signature(validate_resume_truth).parameters
)


class CompressionCandidate(BaseModel):
    path: str
    original: str
    rewritten: str
    claim_preserving: bool
    reason: str


def compress_summary(
    resume: Resume,
    evidence: list[CandidateEvidence],
    *,
    policy: ResumeShapePolicy,
    alias_index: AliasIndex | None = None,
    phrasing: Phrasing | None = None,
) -> CompressionCandidate | None:
    """Return a truth-gated shorter summary candidate, if the summary is over budget."""

    word_limit = policy.informational_budgets.max_summary_words
    summary = resume.basics.summary
    if word_limit is None or summary is None or not summary_too_long(summary, word_limit):
        return None

    rewritten = _rewrite(summary, word_limit, phrasing)
    candidate_resume = resume.model_copy(
        update={"basics": resume.basics.model_copy(update={"summary": rewritten})},
        deep=True,
    )
    return _candidate(
        path=_SUMMARY_PATH,
        truth_path=_SUMMARY_TRUTH_PATH,
        original=summary,
        rewritten=rewritten,
        word_limit=word_limit,
        candidate_resume=candidate_resume,
        evidence=evidence,
        alias_index=alias_index,
    )


def compress_bullet(
    resume: Resume,
    evidence: list[CandidateEvidence],
    *,
    work_index: int,
    achievement_index: int,
    policy: ResumeShapePolicy,
    alias_index: AliasIndex | None = None,
    phrasing: Phrasing | None = None,
) -> CompressionCandidate | None:
    """Return a truth-gated shorter achievement candidate, if the bullet is over budget."""

    word_limit = policy.informational_budgets.max_bullet_words
    if word_limit is None:
        return None

    achievement = resume.work[work_index].achievements[achievement_index]
    original = achievement.text
    if _word_count(original) <= word_limit:
        return None

    rewritten = _rewrite(original, word_limit, phrasing)
    candidate_resume = _with_rewritten_bullet(
        resume,
        work_index=work_index,
        achievement_index=achievement_index,
        rewritten=rewritten,
    )
    path = f"work[{work_index}].achievements[{achievement_index}]"
    truth_path = f"workExperience[{work_index}].description[{achievement_index}]"
    return _candidate(
        path=path,
        truth_path=truth_path,
        original=original,
        rewritten=rewritten,
        word_limit=word_limit,
        candidate_resume=candidate_resume,
        evidence=evidence,
        alias_index=alias_index,
    )


def _rewrite(text: str, word_limit: int, phrasing: Phrasing | None) -> str:
    if phrasing is not None:
        return _normalize_spacing(phrasing(text, word_limit))
    return _default_phrasing(text, word_limit)


def _default_phrasing(text: str, _word_limit: int) -> str:
    """Conservatively remove filler without cutting words or claim-bearing tokens."""

    rewritten = _normalize_spacing(text)
    for filler in _FILLER_WORDS:
        rewritten = re.sub(
            rf"(?<![\w-]){re.escape(filler)}(?![\w-])",
            "",
            rewritten,
            flags=re.IGNORECASE,
        )
    return _normalize_spacing(rewritten).strip(" ,;")


def _candidate(
    *,
    path: str,
    truth_path: str,
    original: str,
    rewritten: str,
    word_limit: int,
    candidate_resume: Resume,
    evidence: list[CandidateEvidence],
    alias_index: AliasIndex | None,
) -> CompressionCandidate:
    report = _validate_candidate(candidate_resume, evidence, alias_index)
    truth_failure = _truth_failure_reason(report, truth_path)
    under_budget = _word_count(rewritten) <= word_limit
    changed = rewritten != original
    claim_preserving = truth_failure is None and under_budget and changed

    if truth_failure is not None:
        reason = f"could not compress truthfully: {truth_failure}"
    elif not changed:
        reason = "could not compress truthfully: no shorter claim-preserving rewrite found"
    elif not under_budget:
        reason = (
            "could not compress truthfully: rewrite still exceeds "
            f"{word_limit} word budget"
        )
    else:
        reason = f"claim-preserving rewrite fits {word_limit} word budget"

    return CompressionCandidate(
        path=path,
        original=original,
        rewritten=rewritten,
        claim_preserving=claim_preserving,
        reason=reason,
    )


def _validate_candidate(
    resume: Resume,
    evidence: list[CandidateEvidence],
    alias_index: AliasIndex | None,
) -> TruthReport:
    builddoc = project_builddoc_from_canonical(resume)
    if _VALIDATE_ACCEPTS_ALIAS_INDEX:
        effective_alias_index = (
            alias_index if alias_index is not None else load_effective_alias_index()
        )
        validator = cast(Callable[..., TruthReport], validate_resume_truth)
        return validator(builddoc, evidence, alias_index=effective_alias_index)
    return validate_resume_truth(builddoc, evidence)


def _truth_failure_reason(report: TruthReport, truth_path: str) -> str | None:
    matching_claims = [claim for claim in report.claims if claim.field_path == truth_path]
    if not matching_claims:
        return f"rewrite removed the claim at {truth_path}"

    failures = [claim for claim in matching_claims if claim.status in _FAILURE_STATUSES]
    if not failures:
        return None

    details = ", ".join(
        f"{claim.status.value}"
        + (f" ({claim.rationale})" if claim.rationale is not None else "")
        for claim in failures
    )
    return f"{truth_path} failed the truth gate: {details}"


def _with_rewritten_bullet(
    resume: Resume,
    *,
    work_index: int,
    achievement_index: int,
    rewritten: str,
) -> Resume:
    work = list(resume.work)
    experience = work[work_index]
    achievements = list(experience.achievements)
    achievements[achievement_index] = achievements[achievement_index].model_copy(
        update={"text": rewritten}
    )
    work[work_index] = experience.model_copy(update={"achievements": achievements})
    return resume.model_copy(update={"work": work}, deep=True)


def _normalize_spacing(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", text).strip()


def _word_count(text: str) -> int:
    return len([word for word in text.split() if word])
