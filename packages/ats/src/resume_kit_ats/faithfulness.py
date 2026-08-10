"""Deterministic faithfulness gate: source text vs. ``ResumeDocument`` (RIT-T-0092).

A pure, LLM-free, network-free checker that compares an agent-produced
:class:`~resume_kit_schemas.ResumeDocument` against the ORIGINAL source document
(the raw extracted text) and reports drift as a
:class:`~resume_kit_schemas.FaithfulnessReport`. This is the machine gate that
turns the skill's prose "count the bullets and confirm they match" self-check
into a real hard-fail: a caller maps ``passed=False`` to a non-zero exit.

Design (finalized, human-approved tolerance rules):

NORMALIZATION — every token comparison runs through
:func:`resume_kit_terms.surface_form`, which ascii-folds unicode punctuation
(middots, curly quotes, en/em dashes, non-breaking spaces), casefolds, and
collapses/trims whitespace. Stemming is intentionally OFF (repo policy — stem
over-collapses ``python``/``pythonic``), so ``surface_form`` (not ``normalize``)
is the shared normalizer used here.

CHECKS and severity:
* ``BULLET_COUNT_MISMATCH`` — total description-bullet count (workExperience +
  personalProjects) source-vs-JSON differs → error.
* ``SECTION_COUNT_MISMATCH`` — detected source section count vs JSON section
  count differs → WARNING. Source section detection is heuristic/best-effort
  (header-keyword scan over the raw text); because that heuristic is unreliable
  on free-form résumés, this is emitted as a warning (never an error and never a
  crash) rather than a hard-fail, so a mis-detected header cannot reject a
  faithful conversion.
* ``DROPPED_SPANS`` — a run of >= 2 consecutive content tokens present in the
  normalized source but absent from the normalized JSON → error.
* ``DROPPED_TOKENS`` — a single content token in the source absent from the JSON
  → WARNING (incidental single words must not hard-fail a faithful conversion).
* ``ALTERED_FIELD`` — a high-signal factual field (employer/company, job title,
  date-range) present in the JSON but whose normalized value is NOT a verbatim
  substring of the normalized source → error.
* ``ADDED_TOKENS`` — content tokens in the JSON absent from the source (possible
  fabrication / rephrase) → WARNING.
* ``NON_ASCII`` — non-ASCII characters anywhere in the JSON → WARNING (reuses the
  ATS-engine non-ASCII scan rather than reimplementing it).

``passed`` is ``False`` iff any error-severity finding exists.
"""

from __future__ import annotations

import re
from typing import Any

from resume_kit_schemas import (
    FaithfulnessCode,
    FaithfulnessFinding,
    FaithfulnessReport,
    ResumeDocument,
)
from resume_kit_terms import surface_form

from resume_kit_ats.engine import _NON_ASCII_PATTERN, _extract_all_text

# Whole-word token boundary over an already surface-folded string (surface_form
# leaves only lowercase ``[a-z0-9]`` runs separated by single spaces).
_TOKEN_RE: re.Pattern[str] = re.compile(r"[a-z0-9]+")

# Leading bullet markers used to detect bullet lines in raw source text. Curly
# and unicode variants are covered because surface-folding happens per line.
_BULLET_PREFIX_RE: re.Pattern[str] = re.compile(r"^\s*(?:[-*+•‣◦⁃∙·]|•)\s+")

# Heuristic source section-header keywords (best-effort; see module docstring).
_SECTION_HEADER_KEYWORDS: tuple[str, ...] = (
    "summary",
    "objective",
    "profile",
    "experience",
    "employment",
    "work history",
    "education",
    "skills",
    "technologies",
    "projects",
    "certifications",
    "awards",
    "languages",
)


def _tokens(text: str) -> list[str]:
    """Return in-order surface-folded content tokens of *text* (no stemming)."""
    return _TOKEN_RE.findall(surface_form(text))


def _token_set(text: str) -> set[str]:
    """Return the set of surface-folded content tokens of *text*."""
    return set(_tokens(text))


def _json_bullet_texts(resume: ResumeDocument) -> list[str]:
    """Return every description bullet across workExperience + personalProjects."""
    bullets: list[str] = []
    for entry in resume.workExperience:
        bullets.extend(entry.description)
    for project in resume.personalProjects:
        bullets.extend(project.description)
    return bullets


def _source_bullet_count(source_text: str) -> int:
    """Count bullet-prefixed lines in the raw source (heuristic, best-effort)."""
    count = 0
    for line in source_text.splitlines():
        if _BULLET_PREFIX_RE.match(line):
            count += 1
    return count


def _source_section_count(source_text: str) -> int:
    """Count detected source section headers (heuristic; see module docstring)."""
    found: set[str] = set()
    for raw_line in source_text.splitlines():
        folded = surface_form(raw_line)
        if not folded or len(folded.split(" ")) > 4:
            # Section headers are short; skip prose lines to reduce false hits.
            continue
        for keyword in _SECTION_HEADER_KEYWORDS:
            if keyword in folded:
                found.add(keyword)
    return len(found)


def _json_section_count(resume: ResumeDocument) -> int:
    """Count populated top-level JSON sections (summary/experience/etc.)."""
    count = 0
    if resume.summary.strip():
        count += 1
    if resume.workExperience:
        count += 1
    if resume.education:
        count += 1
    if resume.personalProjects:
        count += 1
    additional = resume.additional
    if (
        additional.technicalSkills
        or additional.languages
        or additional.certificationsTraining
        or additional.awards
    ):
        count += 1
    return count


def _json_flat_text(resume: ResumeDocument) -> str:
    """Flatten every string value of the resume into one text block."""
    data: dict[str, Any] = resume.model_dump()
    return _extract_all_text(data)


def _high_signal_fields(resume: ResumeDocument) -> list[tuple[str, str]]:
    """Return ``(label, value)`` pairs for verbatim source-presence spot checks.

    High-signal factual fields only: employer/company, job title, and date
    ranges from work experience, plus education institution/degree/years. Empty
    values are skipped — an absent field cannot be "altered".
    """
    fields: list[tuple[str, str]] = []
    for entry in resume.workExperience:
        if entry.company.strip():
            fields.append(("company", entry.company))
        if entry.title.strip():
            fields.append(("title", entry.title))
        if entry.years.strip():
            fields.append(("dates", entry.years))
    for edu in resume.education:
        if edu.institution.strip():
            fields.append(("institution", edu.institution))
        if edu.degree.strip():
            fields.append(("degree", edu.degree))
        if edu.years.strip():
            fields.append(("dates", edu.years))
    return fields


def _contains_subsequence(haystack: list[str], needle: list[str]) -> bool:
    """Return True if *needle* appears as a contiguous run inside *haystack*."""
    if not needle:
        return True
    n, m = len(haystack), len(needle)
    return any(
        haystack[start : start + m] == needle for start in range(0, n - m + 1)
    )


def check_faithfulness(
    source_text: str,
    resume: ResumeDocument,
) -> FaithfulnessReport:
    """Compare *source_text* against *resume* and return a faithfulness report.

    Pure and deterministic: identical inputs always yield an identical report.
    Performs no I/O, no LLM call, and no network access. See the module
    docstring for the finding codes and their severities.

    Args:
        source_text: The ORIGINAL source document as raw extracted text.
        resume: The agent-produced structured resume to check against it.

    Returns:
        A :class:`~resume_kit_schemas.FaithfulnessReport` whose ``passed`` is
        ``False`` iff any error-severity finding exists.
    """
    findings: list[FaithfulnessFinding] = []

    source_tokens = _tokens(source_text)
    source_token_set = set(source_tokens)
    json_flat = _json_flat_text(resume)
    json_tokens = _tokens(json_flat)
    json_token_set = set(json_tokens)

    # --- BULLET_COUNT_MISMATCH (error) ---
    source_bullets = _source_bullet_count(source_text)
    json_bullets = len(_json_bullet_texts(resume))
    if source_bullets != json_bullets:
        findings.append(
            FaithfulnessFinding(
                code=FaithfulnessCode.BULLET_COUNT_MISMATCH,
                severity="error",
                message=(
                    f"Source has {source_bullets} bullet(s) but JSON has "
                    f"{json_bullets}."
                ),
                items=[f"source={source_bullets}", f"json={json_bullets}"],
            )
        )

    # --- SECTION_COUNT_MISMATCH (warning — heuristic source detection) ---
    source_sections = _source_section_count(source_text)
    json_sections = _json_section_count(resume)
    if source_sections != json_sections:
        findings.append(
            FaithfulnessFinding(
                code=FaithfulnessCode.SECTION_COUNT_MISMATCH,
                severity="warning",
                message=(
                    "Heuristic source section count "
                    f"({source_sections}) differs from JSON section count "
                    f"({json_sections}). Source detection is best-effort; "
                    "review manually."
                ),
                items=[f"source={source_sections}", f"json={json_sections}"],
            )
        )

    # --- DROPPED_SPANS (error) / DROPPED_TOKENS (warning) ---
    # A content token missing from the JSON is a candidate drop. Group missing
    # tokens into maximal contiguous runs in source order: a run of >= 2 is a
    # DROPPED_SPANS hard-fail; isolated single drops fall to DROPPED_TOKENS warn.
    dropped_spans: list[str] = []
    single_dropped: list[str] = []
    run: list[str] = []

    def _flush(current: list[str]) -> None:
        if len(current) >= 2:
            dropped_spans.append(" ".join(current))
        elif len(current) == 1:
            single_dropped.append(current[0])

    for token in source_tokens:
        if token not in json_token_set:
            run.append(token)
        else:
            _flush(run)
            run = []
    _flush(run)

    if dropped_spans:
        findings.append(
            FaithfulnessFinding(
                code=FaithfulnessCode.DROPPED_SPANS,
                severity="error",
                message=(
                    f"{len(dropped_spans)} multi-word span(s) present in the "
                    "source are absent from the JSON."
                ),
                items=dropped_spans,
            )
        )
    if single_dropped:
        findings.append(
            FaithfulnessFinding(
                code=FaithfulnessCode.DROPPED_TOKENS,
                severity="warning",
                message=(
                    f"{len(single_dropped)} single source token(s) are absent "
                    "from the JSON (possible incidental omission)."
                ),
                items=single_dropped,
            )
        )

    # --- ALTERED_FIELD (error) ---
    # High-signal fields must appear verbatim (normalized) in the source: the
    # field's token run must be a contiguous subsequence of the source tokens.
    altered: list[str] = []
    for label, value in _high_signal_fields(resume):
        needle = _tokens(value)
        if not needle:
            continue
        if not _contains_subsequence(source_tokens, needle):
            altered.append(f"{label}: {value}")
    if altered:
        findings.append(
            FaithfulnessFinding(
                code=FaithfulnessCode.ALTERED_FIELD,
                severity="error",
                message=(
                    f"{len(altered)} high-signal field(s) in the JSON are not "
                    "found verbatim in the source (changed or fabricated)."
                ),
                items=altered,
            )
        )

    # --- ADDED_TOKENS (warning) ---
    added = sorted(json_token_set - source_token_set)
    if added:
        findings.append(
            FaithfulnessFinding(
                code=FaithfulnessCode.ADDED_TOKENS,
                severity="warning",
                message=(
                    f"{len(added)} content token(s) in the JSON are absent from "
                    "the source (possible fabrication or rephrase)."
                ),
                items=added,
            )
        )

    # --- NON_ASCII (warning — reuses the ATS-engine scan) ---
    non_ascii = sorted(set(_NON_ASCII_PATTERN.findall(json_flat)))
    if non_ascii:
        findings.append(
            FaithfulnessFinding(
                code=FaithfulnessCode.NON_ASCII,
                severity="warning",
                message=(
                    "Non-ASCII character(s) detected in the JSON — some ATS "
                    "systems may mis-parse them. This is informational for a "
                    "faithful -original.json: preserve the characters verbatim "
                    "and normalize at export, not here."
                ),
                items=non_ascii,
            )
        )

    return FaithfulnessReport(findings=findings)
