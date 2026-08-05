"""ATS score computation engine.

Derived from ``apps/backend/app/services/ats.py``
@ SHA ``116f9cc3b00e1ac91734a6c2679bf41ea64a0edc``, Apache-2.0.

Calculates an ATS-style breakdown score from already-processed resume and job
data:
  - keyword_match: final keyword match % from the refinement pipeline
  - skills_coverage: overlap between resume technical skills and JD required skills
  - section_completeness: presence of essential resume sections (local, no LLM)

The overall_score is a weighted composite of the three sub-scores.
Expanded deterministic checks enrich ``recommendations`` without altering the
seed composite score contract.
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from resume_kit_schemas import (
    ATSScore,
    AtsStructureReport,
    ATSSubScores,
    MatchedKeyword,
)
from resume_kit_schemas.job import JobDescription
from resume_kit_schemas.resume import ResumeDocument
from resume_kit_terms import (
    AliasIndex,
    MatchResult,
    load_effective_alias_index,
    match,
    surface_form,
)
from resume_kit_terms.aliases import PROJECT_ALIAS_ENV_VAR

logger = logging.getLogger(__name__)


@lru_cache(maxsize=8)
def _effective_alias_index(project_key: str | None) -> AliasIndex:
    """Build (and cache) the effective seed+project index for *project_key*.

    Keyed on the resolved project-file path string (``None`` for seed-only) so a
    changed ``RESUME_KIT_ALIAS_FILE`` produces a fresh index instead of a stale
    one — deterministic for a FIXED path, invalidatable across paths.
    """
    project_path = Path(project_key) if project_key is not None else None
    return load_effective_alias_index(project_path)


def _alias_index() -> AliasIndex:
    """Return the effective (seed + optional project) :class:`AliasIndex`.

    Resolves the project-alias path from ``RESUME_KIT_ALIAS_FILE`` (set by a
    surface; RIT-T-0069) and delegates to the path-keyed cache. Seed-only when
    the env var is unset / empty. The ``ats`` and ``matching`` engines share the
    identical loader so they never diverge — the "no divergent matching"
    guarantee.
    """
    env_value = os.environ.get(PROJECT_ALIAS_ENV_VAR)
    project_key = env_value if env_value and env_value.strip() else None
    return _effective_alias_index(project_key)

# ---------------------------------------------------------------------------
# Weights — MUST match the upstream seed contract (sum = 1.0).
# ---------------------------------------------------------------------------
_WEIGHTS: dict[str, float] = {
    "keyword_match": 0.55,
    "skills_coverage": 0.25,
    "section_completeness": 0.20,
}

# Patterns to detect resume section headings (used in text-fallback path).
_SECTION_PATTERNS: dict[str, list[str]] = {
    "summary": ["summary", "objective", "profile", "about"],
    "experience": ["experience", "work history", "employment"],
    "education": ["education", "academic", "degree"],
    "skills": ["skills", "technologies", "competencies", "technical"],
}

# ---------------------------------------------------------------------------
# Helpers (ported verbatim from upstream, zero app.* imports)
# ---------------------------------------------------------------------------


def _extract_all_text(data: dict[str, Any]) -> str:
    """Flatten all string values from a resume dict into a single text block."""
    parts: list[str] = []

    def _walk(obj: Any) -> None:
        if isinstance(obj, str):
            parts.append(obj)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)
        elif isinstance(obj, dict):
            for v in obj.values():
                _walk(v)

    _walk(data)
    return " ".join(parts)


# Word boundary for tokenizing free text into surface tokens (mirrors the
# alphanumeric-only splitting used by ``resume_kit_terms.surface_form``).
_WORD_RE: re.Pattern[str] = re.compile(r"[a-z0-9]+")


def _surface_tokens(text: str) -> list[str]:
    """Tokenize *text* into lowercase alphanumeric surface tokens, in order."""
    return _WORD_RE.findall(surface_form(text))


def _keyword_match_in_candidates(
    keyword: str,
    candidate_terms: list[str],
    token_windows: dict[int, set[str]],
) -> MatchResult:
    """Return the best :class:`MatchResult` for *keyword* against a resume.

    The keyword is compared — via the shared ``resume_kit_terms.match`` (with the
    curated :class:`AliasIndex`) — against two sources of resume "whole terms":

    * ``candidate_terms`` — discrete listed skills (e.g. ``technicalSkills``),
      each compared as a whole term (no substring containment).
    * ``token_windows`` — contiguous whole-word n-grams drawn from the resume
      free text, keyed by n-gram length, so a multi-word keyword like
      ``row-level security`` matches only a run of whole words, never a
      substring of a larger word.

    Matching stays deterministic: candidates are iterated in the given order and
    each window set is scanned sorted, with exact > alias precedence honored by
    returning immediately on an exact hit (stemming is disabled — see the
    ``allow_stem=False`` calls below).
    """
    if not surface_form(keyword):
        return MatchResult(matched=False)

    index = _alias_index()

    # Discrete listed skills first (already deterministic input order).
    # allow_stem=False: exact + curated-alias only, no Snowball stemming — the
    # single policy shared with the ``matching`` engine so the two never diverge
    # (RIT-I-0008; stem over-collapses python/pythonic, go/going).
    best: MatchResult | None = None
    for candidate in candidate_terms:
        result = match(keyword, candidate, alias_index=index, allow_stem=False)
        if result.matched:
            if result.kind == "exact":
                return result
            if best is None:
                best = result

    # Free-text n-gram windows sized to the keyword's whole-word length.
    kw_len = len(surface_form(keyword).split(" "))
    for window in sorted(token_windows.get(kw_len, set())):
        result = match(keyword, window, alias_index=index, allow_stem=False)
        if result.matched:
            if result.kind == "exact":
                return result
            if best is None:
                best = result

    return best if best is not None else MatchResult(matched=False)


def _build_token_windows(text: str, max_len: int) -> dict[int, set[str]]:
    """Return contiguous whole-word n-grams of *text*, keyed by length (1..max_len).

    Windows are built from surface tokens so comparisons are whole-term, never
    substring — ``lint`` will not match inside ``linting`` unless the shared
    normalizer says so.
    """
    tokens = _surface_tokens(text)
    windows: dict[int, set[str]] = {}
    for size in range(1, max(1, max_len) + 1):
        grams: set[str] = set()
        for start in range(0, len(tokens) - size + 1):
            grams.add(" ".join(tokens[start : start + size]))
        if grams:
            windows[size] = grams
    return windows


def _compute_skills_coverage(
    resume: dict[str, Any],
    job_keywords: dict[str, Any],
) -> tuple[float, list[MatchedKeyword]]:
    """Return ``(skills_coverage_score, matched_keywords)``.

    Checks how many required_skills / preferred_skills from the JD appear in the
    resume's technicalSkills list (falling back to whole-word text n-grams).
    Comparison routes through the shared ``resume_kit_terms`` matcher so the
    score is synonym-aware and consistent with the ``matching`` package. Every
    JD skill found present yields a :class:`MatchedKeyword` carrying the match
    ``kind`` (and ``canonical`` for alias hits).
    """
    jd_skills: list[str] = []
    jd_skills.extend(job_keywords.get("required_skills", []))
    jd_skills.extend(job_keywords.get("preferred_skills", []))

    jd_skills = [s for s in jd_skills if isinstance(s, str)]
    if not jd_skills:
        return 0.0, []

    resume_skills: list[str] = [
        s
        for s in (resume.get("additional", {}).get("technicalSkills", []) or [])
        if isinstance(s, str)
    ]
    resume_text = _extract_all_text(resume)

    # Size the free-text n-gram windows to the longest JD skill (in whole words)
    # so multi-word skills can match a run of whole words.
    max_kw_len = max(
        (len(surface_form(s).split(" ")) for s in jd_skills if surface_form(s)),
        default=1,
    )
    token_windows = _build_token_windows(resume_text, max_kw_len)

    matched_keywords: list[MatchedKeyword] = []
    for skill in jd_skills:
        result = _keyword_match_in_candidates(skill, resume_skills, token_windows)
        if result.matched and result.kind is not None:
            matched_keywords.append(
                MatchedKeyword(
                    keyword=skill,
                    kind=result.kind,
                    canonical=result.canonical,
                )
            )

    score = min(100.0, (len(matched_keywords) / len(jd_skills)) * 100)
    return score, matched_keywords


def _compute_section_completeness(resume: dict[str, Any]) -> float:
    """Return section completeness score (0–100).

    Checks the structured resume dict for the presence of key sections.
    If no structured sections are detected, falls back to scanning all
    extracted text for common section heading keywords.
    """
    found = 0

    # Structured-data fast path
    if resume.get("summary"):
        found += 1
    if resume.get("workExperience"):
        found += 1
    if resume.get("education"):
        found += 1
    skills = resume.get("additional", {}).get("technicalSkills", [])
    if skills:
        found += 1

    # If none of the structured checks fired, fall back to text scanning
    if found == 0:
        text = _extract_all_text(resume).lower()
        for patterns in _SECTION_PATTERNS.values():
            if any(p in text for p in patterns):
                found += 1

    total = len(_SECTION_PATTERNS)  # 4
    return (found / total) * 100


def _generate_recommendations(
    keyword_score: float,
    skills_score: float,
    section_score: float,
    missing_keywords: list[str],
    injectable_keywords: list[str],
) -> list[str]:
    """Generate seed recommendations (upstream-ported, deterministic)."""
    tips: list[str] = []

    if keyword_score < 60 and missing_keywords:
        top = ", ".join(missing_keywords[:5])
        tips.append(f"Add these high-priority missing keywords: {top}.")

    if injectable_keywords:
        top_injectable = ", ".join(injectable_keywords[:5])
        tips.append(
            f"The following skills are in your master resume but not in this tailored"
            f" version — consider adding them: {top_injectable}."
        )

    if skills_score < 60:
        tips.append(
            "Expand your Skills section to include more of the tools and technologies"
            " listed in the job description."
        )

    if section_score < 75:
        tips.append(
            "Make sure your resume includes all key sections: Summary, Work Experience,"
            " Education, and Skills."
        )

    if keyword_score >= 80 and skills_score >= 80:
        tips.append(
            "Strong keyword and skills alignment. Consider quantifying your achievements"
            " with metrics and numbers."
        )

    if not tips:
        tips.append(
            "Your resume is well-aligned with the job description. Review for any niche"
            " certifications or tools to add."
        )

    return tips


# ---------------------------------------------------------------------------
# Expanded deterministic checks (new, do not touch the composite score)
# ---------------------------------------------------------------------------

_DATE_PATTERN: re.Pattern[str] = re.compile(
    r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?"
    r"|jul(?:y)?|aug(?:ust)?|sep(?:tember)?|oct(?:ober)?|nov(?:ember)?"
    r"|dec(?:ember)?|\d{4}|present|current)\b",
    re.IGNORECASE,
)

# Single source of truth for the non-ASCII scan, reused by the faithfulness
# gate (RIT-T-0092) so the two never diverge on what counts as non-ASCII.
_NON_ASCII_PATTERN: re.Pattern[str] = re.compile(r"[^\x00-\x7F]")

_FORMATTING_RISK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        _NON_ASCII_PATTERN,
        "Non-ASCII characters detected — some ATS systems may mis-parse them.",
    ),
    (
        re.compile(r"\t"),
        "Tab characters detected — prefer spaces for ATS compatibility.",
    ),
    (
        re.compile(r"(?:[•‣◦⁃∙])"),
        "Unicode bullet characters detected — plain hyphens or dashes are safer for ATS.",
    ),
]


#: Prohibited / discouraged personal-information patterns (industry guidance:
#: no SSN, DOB, marital status, full street address, or "references available").
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
        "A Social Security number appears in the resume — never include SSNs or"
        " government IDs; remove it.",
    ),
    (
        re.compile(r"\b(date of birth|d\.?o\.?b\.?|birthdate)\b", re.IGNORECASE),
        "Date of birth detected — omit age/DOB unless a specific country/application"
        " requires it.",
    ),
    (
        re.compile(r"\bmarital status\b", re.IGNORECASE),
        "Marital status detected — remove it; it is not relevant and invites bias.",
    ),
    (
        re.compile(r"references\s+available\s+upon\s+request", re.IGNORECASE),
        "'References available upon request' detected — it wastes space; remove it.",
    ),
    (
        re.compile(
            r"\b\d{1,5}\s+([A-Za-z0-9.]+\s){1,4}"
            r"(street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr|court|ct)\b",
            re.IGNORECASE,
        ),
        "A full street address appears present — a city and state/metro is enough;"
        " a full street address is usually unnecessary.",
    ),
]

#: Placeholder / leftover-AI-prompt markers that must never ship in a resume.
_PLACEHOLDER_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"lorem ipsum|\bTODO\b|\[[^\]]*(placeholder|your name|insert)[^\]]*\]", re.IGNORECASE),
        "Placeholder/template text detected — remove all placeholder text before"
        " submitting.",
    ),
    (
        re.compile(r"as an ai|as a language model|i cannot|i'm sorry, but", re.IGNORECASE),
        "Text that looks like leftover AI-assistant output detected — rewrite it in"
        " your own voice; never leave AI prompt/response fragments.",
    ),
]

#: Conventional section-name keywords; a custom section whose title matches none
#: of these reads as a non-standard heading to an ATS/recruiter.
_CONVENTIONAL_SECTION_KEYWORDS: tuple[str, ...] = (
    "summary", "objective", "profile", "about",
    "experience", "employment", "work", "history",
    "education", "academic",
    "skill", "technical", "competenc",
    "certification", "license", "credential",
    "project", "portfolio",
    "publication", "award", "honor", "achievement",
    "volunteer", "leadership", "activit",
    "language", "interest", "reference",
)

_MONTH_TOKEN_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)", re.IGNORECASE
)


def _has_month(text: str) -> bool:
    return bool(_MONTH_TOKEN_RE.search(text))


def _has_year(text: str) -> bool:
    return bool(re.search(r"(19|20)\d{2}", text))


def _expanded_recommendations(resume: dict[str, Any]) -> list[str]:
    """Deterministic structural checks that enrich recommendations.

    These checks inspect the raw resume dict for common ATS failure modes:
    contact-info presence, required section presence, date presence, and
    basic formatting risks. They NEVER alter the composite score.
    """
    tips: list[str] = []

    # --- Contact-info checks ---
    personal: dict[str, Any] = resume.get("personalInfo", {}) or {}
    if not personal.get("email"):
        tips.append(
            "No email address detected — add a professional email to your contact"
            " information."
        )
    if not personal.get("phone"):
        tips.append(
            "No phone number detected — most ATS systems expect a contact phone number."
        )
    if not personal.get("name"):
        tips.append(
            "No name detected in personalInfo — ensure your full name is at the top of"
            " your resume."
        )

    # --- Section presence checks ---
    if not resume.get("summary"):
        tips.append(
            "No summary or objective section found — a 2-3 sentence summary helps ATS"
            " context-match your profile."
        )
    if not resume.get("workExperience"):
        tips.append(
            "No work experience section found — ensure your positions are structured"
            " under a Work Experience heading."
        )
    if not resume.get("education"):
        tips.append(
            "No education section found — include your highest degree even if it is"
            " older."
        )
    additional: dict[str, Any] = resume.get("additional", {}) or {}
    if not additional.get("technicalSkills"):
        tips.append(
            "No technical skills listed — a dedicated Skills section significantly"
            " improves ATS keyword matching."
        )

    # --- Date presence checks ---
    work_exp: list[Any] = resume.get("workExperience", []) or []
    entries_without_dates = [
        e for e in work_exp if isinstance(e, dict) and not e.get("years")
    ]
    if entries_without_dates:
        count = len(entries_without_dates)
        noun = "entry" if count == 1 else "entries"
        verb = "is" if count == 1 else "are"
        tips.append(
            f"{count} work experience {noun} {verb} missing date ranges"
            f" — add start/end years for each position."
        )

    full_text = _extract_all_text(resume)
    if work_exp and not _DATE_PATTERN.search(full_text):
        tips.append(
            "No date references detected in resume text — ensure each position includes"
            " date ranges (e.g. 'Jan 2020 – Present')."
        )

    # --- Date-format consistency across work experience ---
    dated = [
        str(e.get("years", ""))
        for e in work_exp
        if isinstance(e, dict) and e.get("years")
    ]
    month_level = [d for d in dated if _has_month(d)]
    year_only = [d for d in dated if _has_year(d) and not _has_month(d)]
    if month_level and year_only:
        tips.append(
            "Inconsistent date formats across positions — some use month-level dates"
            " and others year-only; use one consistent date format throughout."
        )

    # --- Non-standard section headings ---
    custom_sections: dict[str, Any] = resume.get("customSections", {}) or {}
    nonstandard = [
        name
        for name in custom_sections
        if not any(kw in name.lower() for kw in _CONVENTIONAL_SECTION_KEYWORDS)
    ]
    if nonstandard:
        shown = ", ".join(f"'{n}'" for n in nonstandard[:3])
        tips.append(
            f"Non-standard section heading(s) detected ({shown}) — use conventional"
            " names (Summary, Experience, Skills, Education, Certifications, Projects)"
            " so an ATS can categorize them."
        )

    # --- Prohibited personal information ---
    for pattern, message in _PII_PATTERNS:
        if pattern.search(full_text):
            tips.append(message)

    # --- Placeholder / leftover-AI text ---
    for pattern, message in _PLACEHOLDER_PATTERNS:
        if pattern.search(full_text):
            tips.append(message)

    # --- Basic formatting risk checks ---
    for pattern, message in _FORMATTING_RISK_PATTERNS:
        if pattern.search(full_text):
            tips.append(message)

    return tips


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def compute_ats_score(
    refined_resume: dict[str, Any] | ResumeDocument,
    job_keywords: dict[str, Any] | JobDescription,
    keyword_match_percentage: float,
    missing_keywords: list[str],
    injectable_keywords: list[str],
) -> ATSScore:
    """Compute the ATS score breakdown and return an :class:`ATSScore`.

    The seed composite (weights 0.55/0.25/0.20) and rounding are preserved
    exactly from the upstream implementation. Expanded deterministic checks
    append additional recommendations without modifying the numeric scores.

    Args:
        refined_resume: The fully refined resume data — either a
            :class:`~resume_kit_schemas.ResumeDocument` instance or a plain
            dict in the upstream shape.
        job_keywords: Extracted JD keywords — either a
            :class:`~resume_kit_schemas.JobDescription` instance or a plain
            dict with ``required_skills`` / ``preferred_skills`` keys.
        keyword_match_percentage: Final keyword match % (0–100).
        missing_keywords: Keywords absent from the tailored resume
            (non-injectable).
        injectable_keywords: Keywords absent but present in the master resume.

    Returns:
        :class:`~resume_kit_schemas.ATSScore` with overall score, sub-scores,
        keyword lists, and recommendations (seed + expanded checks).
    """
    # Normalise inputs: accept both Pydantic models and plain dicts.
    resume_dict: dict[str, Any] = (
        refined_resume.model_dump()
        if isinstance(refined_resume, ResumeDocument)
        else refined_resume
    )
    job_dict: dict[str, Any] = (
        _job_description_to_keywords(job_keywords)
        if isinstance(job_keywords, JobDescription)
        else job_keywords
    )

    # --- Seed composite (upstream-compatible) ---
    kw_score = min(100.0, max(0.0, keyword_match_percentage))
    sk_score, matched_keywords = _compute_skills_coverage(resume_dict, job_dict)
    sec_score = _compute_section_completeness(resume_dict)

    overall = (
        kw_score * _WEIGHTS["keyword_match"]
        + sk_score * _WEIGHTS["skills_coverage"]
        + sec_score * _WEIGHTS["section_completeness"]
    )

    # --- Recommendations: seed + expanded ---
    seed_tips = _generate_recommendations(
        kw_score,
        sk_score,
        sec_score,
        missing_keywords,
        injectable_keywords,
    )
    expanded_tips = _expanded_recommendations(resume_dict)
    all_tips = seed_tips + [t for t in expanded_tips if t not in seed_tips]

    return ATSScore(
        overall_score=round(overall, 1),
        sub_scores=ATSSubScores(
            keyword_match=round(kw_score, 1),
            skills_coverage=round(sk_score, 1),
            section_completeness=round(sec_score, 1),
        ),
        missing_keywords=missing_keywords[:10],
        injectable_keywords=injectable_keywords[:10],
        recommendations=all_tips,
        matched_keywords=matched_keywords,
    )


def check_ats_structure(
    resume: ResumeDocument | dict[str, Any],
) -> AtsStructureReport:
    """Run the RESUME-ONLY structural ATS check and return a minimal report.

    Job-independent: inspects only the resume for structural ATS signal —
    section presence (``_compute_section_completeness``) and deterministic
    structural recommendations (``_expanded_recommendations``: contact info,
    section presence, date presence, formatting risks). Returns ONLY
    ``section_completeness`` + ``recommendations``; no keyword match, no skills
    coverage, no composite overall score (those require a job and live on
    :class:`~resume_kit_schemas.ATSScore`).

    Reuses the exact private helpers that ``compute_ats_score`` calls, so the
    two never diverge and no scoring math is duplicated or changed.

    Args:
        resume: The resume — either a
            :class:`~resume_kit_schemas.ResumeDocument` instance or a plain
            dict in the upstream shape.

    Returns:
        :class:`~resume_kit_schemas.AtsStructureReport` with section
        completeness (0–100) and structural recommendations.
    """
    resume_dict: dict[str, Any] = (
        resume.model_dump() if isinstance(resume, ResumeDocument) else resume
    )

    section_score = _compute_section_completeness(resume_dict)
    recommendations = _expanded_recommendations(resume_dict)

    return AtsStructureReport(
        section_completeness=round(section_score, 1),
        recommendations=recommendations,
    )


def _job_description_to_keywords(jd: JobDescription) -> dict[str, Any]:
    """Convert a :class:`JobDescription` to the upstream keyword dict shape."""
    from resume_kit_schemas.job import RequirementKind

    required: list[str] = []
    preferred: list[str] = []

    for req in jd.requirements:
        required.extend(req.keywords)
        if req.text and not req.keywords:
            required.append(req.text)

    for qual in jd.qualifications:
        if qual.kind == RequirementKind.PREFERRED:
            preferred.extend(qual.keywords)
            if qual.text and not qual.keywords:
                preferred.append(qual.text)
        else:
            required.extend(qual.keywords)

    # Fall back to the flat keyword list if structured lists are empty.
    if not required and not preferred:
        required = list(jd.keywords)

    return {
        "required_skills": required,
        "preferred_skills": preferred,
    }
