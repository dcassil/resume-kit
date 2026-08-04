"""Accept a terminology-alignment suggestion into a truth-safe applied change.

Bridges the synonym-aware terminology analyzer (RIT-I-0010, which emits
:class:`resume_kit_schemas.TerminologyAlignment` records) to the Phase-4
alignment/policy/evidence gates. An accepted suggestion is mapped to a single
``replace`` :class:`resume_kit_schemas.ChangeProposal` that swaps ONLY the
employer-mirrored surface term inside one resume field, routed through the
existing :func:`resume_kit_alignment.apply.apply_diffs` policy gate at the
MINIMAL sufficient freedom, and re-validated with
:func:`resume_kit_evidence.validate_resume_truth`.

Truth-safety invariants (NFR-1001), held by construction:

- The ONLY input is a ``TerminologyAlignment`` (REQ-1003). Those records exist
  only for alias hits (RIT-T-0072); there is no code path from a raw / no-match
  keyword to a change here.
- The swap is surface-only: the ``original`` text is preserved verbatim except
  that each whole token whose folded surface form equals the suggestion's
  current wording is rewritten to the employer's exact wording. The claim is
  unchanged, so truth validation still passes.
- Identity / employer / date / name / degree fields are never editable — the
  policy gate rejects those paths at every freedom level. This module adds NO
  new truth or policy logic (NFR-1003); it reuses the existing gates.

Deterministic: no LLM, no provider, stable ordering; the swap is a pure
token substitution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from resume_kit_ats.engine import _compute_skills_coverage
from resume_kit_evidence.truth import validate_resume_truth
from resume_kit_matching.keywords import calculate_keyword_match
from resume_kit_policy.path_policy import (
    FREEDOM_MIN,
    is_path_allowed_at_freedom,
    is_path_blocked,
)
from resume_kit_schemas import ResumeDocument, TerminologyAlignment
from resume_kit_schemas.change import ChangeProposal
from resume_kit_schemas.evidence import CandidateEvidence
from resume_kit_schemas.job import JobDescription
from resume_kit_schemas.results import PolicyRejection
from resume_kit_terms import surface_form

from .apply import _resolve_path, apply_diffs

__all__ = [
    "ScoreDelta",
    "AcceptResult",
    "build_terminology_change",
    "minimal_freedom_for_path",
    "accept_terminology_alignment",
]

# Whole-token splitter mirroring the analyzer's ``\w+`` tokenisation so the swap
# targets exactly the tokens the analyzer located, leaving separators intact.
_TOKEN_RE = re.compile(r"\w+")

_MIRROR_REASON = (
    "Mirror the employer's exact terminology: the resume already demonstrates "
    "this via an equivalent term, so the surface wording is aligned to the job "
    "description without altering the underlying claim."
)


@dataclass(frozen=True)
class ScoreDelta:
    """Deterministic before/after keyword-match and skills-coverage scores."""

    keyword_match_before: float
    keyword_match_after: float
    skills_coverage_before: float
    skills_coverage_after: float

    @property
    def keyword_match_delta(self) -> float:
        return self.keyword_match_after - self.keyword_match_before

    @property
    def skills_coverage_delta(self) -> float:
        return self.skills_coverage_after - self.skills_coverage_before


@dataclass(frozen=True)
class AcceptResult:
    """Outcome of accepting one terminology-alignment suggestion.

    ``applied`` is empty and ``resume`` is byte-identical to the input when the
    policy gate rejects the change (e.g. a blocked factual field); the rejection
    detail is then carried in ``rejected``.
    """

    resume: ResumeDocument
    change: ChangeProposal
    applied: list[ChangeProposal]
    rejected: list[PolicyRejection]
    freedom: int
    delta: ScoreDelta
    truth_passed: bool
    swap_applied: bool
    location: str
    field_before: str = ""
    field_after: str = ""


def _swap_surface_term(text: str, current_wording: str, jd_keyword: str) -> str:
    """Rewrite each whole token in *text* whose surface form equals the current
    wording to *jd_keyword*, preserving every other character (separators,
    casing of untouched tokens, punctuation).

    The comparison folds via :func:`resume_kit_terms.surface_form`, matching the
    analyzer's own token-level comparison, so exactly the tokens the analyzer
    located as the current wording are the ones rewritten.
    """

    target = surface_form(current_wording)

    def _replace(m: re.Match[str]) -> str:
        token = m.group(0)
        if surface_form(token) == target:
            return jd_keyword
        return token

    return _TOKEN_RE.sub(_replace, text)


def minimal_freedom_for_path(path: str) -> int | None:
    """Return the lowest freedom level (0-10) at which *path* is editable.

    Returns ``None`` when *path* is a blocked factual field (identity / date /
    employer / degree / institution / URL / id) or is not an editable target at
    any level — the accept path then cannot fire a swap there.
    """

    if is_path_blocked(path):
        return None
    for level in range(FREEDOM_MIN, 11):
        if is_path_allowed_at_freedom(path, level):
            return level
    return None


def build_terminology_change(
    suggestion: TerminologyAlignment,
    location: str,
    original_field_text: str,
) -> ChangeProposal:
    """Map an accepted suggestion + one location to a ``replace`` change.

    Args:
        suggestion: The accepted alias-backed suggestion (REQ-1003: the only
            accepted input; a raw keyword can never reach this function).
        location: One resume path drawn from ``suggestion.locations`` — the
            whole-field path whose text is being surface-swapped.
        original_field_text: The FULL current text at ``location``. It becomes
            the change's ``original`` (for the replace-verification gate); the
            ``value`` is that same text with only the current wording tokens
            rewritten to the employer's exact wording.

    Returns:
        A ``ChangeProposal`` with ``action="replace"``, ``path=location``,
        ``original`` = the current field text, ``value`` = the surface-swapped
        field text, and the mirror-terminology rationale.
    """

    value = _swap_surface_term(
        original_field_text,
        suggestion.current_wording,
        suggestion.jd_keyword,
    )
    return ChangeProposal(
        path=location,
        action="replace",
        original=original_field_text,
        value=value,
        reason=_MIRROR_REASON,
    )


def _score(
    resume: ResumeDocument, job: JobDescription
) -> tuple[float, float]:
    keyword_match = calculate_keyword_match(resume, job)
    skills_coverage, _matched = _compute_skills_coverage(
        resume.model_dump(), job.model_dump()
    )
    return keyword_match, skills_coverage


def accept_terminology_alignment(
    suggestion: TerminologyAlignment,
    location: str,
    resume: ResumeDocument,
    job: JobDescription,
    evidence: list[CandidateEvidence],
    *,
    freedom: int | None = None,
) -> AcceptResult:
    """Accept one terminology suggestion and route it through the Phase-4 gates.

    Pipeline (reuses existing gates only — NFR-1003):

    1. Map ``suggestion`` + ``location`` to a ``replace`` ``ChangeProposal``
       (:func:`build_terminology_change`) that swaps only the surface term.
    2. Choose the MINIMAL freedom that unlocks ``location`` (description bullets
       → F4; summary → F6; education description → F8) unless the caller
       overrides it. A blocked factual field, or a non-editable target such as a
       bare ``additional.technicalSkills`` element, yields ``None`` freedom → the
       change is still submitted so the policy gate records the rejection, and
       nothing mutates.
    3. Run :func:`resume_kit_alignment.apply_diffs` — the policy gate rejects
       blocked paths (identity / date / employer) at every level.
    4. Re-validate the result with
       :func:`resume_kit_evidence.validate_resume_truth`; a surface-only swap
       keeps every claim, so a passing resume stays passing.
    5. Report the deterministic before/after keyword-match + skills-coverage
       delta (REQ-1005).

    Args:
        suggestion: The accepted alias-backed suggestion (REQ-1003).
        location: A path from ``suggestion.locations``.
        resume: The resume to edit (never mutated; a new document is returned).
        job: The target job description, for the score delta.
        evidence: Ground-truth candidate evidence for truth validation.
        freedom: Optional explicit freedom level; defaults to the minimal
            sufficient level for ``location``.

    Returns:
        An :class:`AcceptResult` with the updated resume (or the untouched
        resume on rejection), the change, applied/rejected records, the freedom
        used, the score delta, whether truth still passed, and whether the swap
        was actually applied.
    """

    actual_value, resolved = _resolve_path(resume.model_dump(), location)
    original_field_text = actual_value if isinstance(actual_value, str) else ""

    change = build_terminology_change(suggestion, location, original_field_text)

    if freedom is None:
        minimal = minimal_freedom_for_path(location)
        # A blocked / non-editable path has no unlocking level; submit at the
        # minimum so apply_diffs' policy gate records the rejection explicitly.
        effective_freedom = minimal if minimal is not None else FREEDOM_MIN
    else:
        effective_freedom = freedom

    km_before, sc_before = _score(resume, job)

    result_dict, applied, rejected = apply_diffs(
        resume,
        [change],
        freedom=effective_freedom,
    )
    updated = ResumeDocument.model_validate(result_dict)

    truth = validate_resume_truth(updated, evidence)

    km_after, sc_after = _score(updated, job)

    swap_applied = bool(applied) and resolved and value_changed(change)

    updated_field, _ = _resolve_path(result_dict, location)
    field_after = updated_field if isinstance(updated_field, str) else ""

    return AcceptResult(
        resume=updated,
        change=change,
        applied=applied,
        rejected=rejected,
        freedom=effective_freedom,
        delta=ScoreDelta(
            keyword_match_before=km_before,
            keyword_match_after=km_after,
            skills_coverage_before=sc_before,
            skills_coverage_after=sc_after,
        ),
        truth_passed=truth.passed,
        swap_applied=swap_applied,
        location=location,
        field_before=original_field_text,
        field_after=field_after,
    )


def value_changed(change: ChangeProposal) -> bool:
    """Whether the change's ``value`` differs from its ``original`` text."""

    return change.original != change.value
