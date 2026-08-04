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
import re
from typing import Any

from resume_kit_schemas import ATSScore, ATSSubScores
from resume_kit_schemas.job import JobDescription
from resume_kit_schemas.resume import ResumeDocument

logger = logging.getLogger(__name__)

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


def _keyword_in_text(keyword: str, text_lower: str) -> bool:
    """Whole-word match against pre-lowercased text to avoid false positives.

    Args:
        keyword: The keyword to search for (will be lowercased internally).
        text_lower: Full text that has already been lowercased by the caller.
    """
    escaped = re.escape(keyword.strip().lower())
    if not escaped:
        return False
    return bool(re.search(rf"(?<!\w){escaped}(?!\w)", text_lower))


def _compute_skills_coverage(
    resume: dict[str, Any],
    job_keywords: dict[str, Any],
) -> float:
    """Return skills coverage score (0–100).

    Checks how many required_skills / preferred_skills from the JD appear
    in the resume's technicalSkills list (falls back to full-text search).
    """
    jd_skills: list[str] = []
    jd_skills.extend(job_keywords.get("required_skills", []))
    jd_skills.extend(job_keywords.get("preferred_skills", []))

    if not jd_skills:
        return 0.0

    resume_skills: list[str] = (
        resume.get("additional", {}).get("technicalSkills", []) or []
    )
    resume_text = _extract_all_text(resume).lower()
    resume_skills_lower = {s.lower() for s in resume_skills if isinstance(s, str)}

    matched = 0
    for skill in jd_skills:
        if not isinstance(skill, str):
            continue
        skill_lower = skill.lower()
        # Direct skill list match or whole-word text match (resume_text is pre-lowercased)
        if skill_lower in resume_skills_lower or _keyword_in_text(skill, resume_text):
            matched += 1

    return min(100.0, (matched / len(jd_skills)) * 100)


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

_FORMATTING_RISK_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (
        re.compile(r"[^\x00-\x7F]"),
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
    sk_score = _compute_skills_coverage(resume_dict, job_dict)
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
