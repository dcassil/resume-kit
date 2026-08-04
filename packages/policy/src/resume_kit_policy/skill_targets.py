"""Deterministic verified-skill-target gate for controlled alignment.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/services/improver.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc  Apache-2.0
# Modified: Extracted _normalize_skill_key, _extract_skill_index,
#   _skill_mentioned_in_text, _build_allowed_skill_target_keys,
#   _extract_jd_skill_index, _skill_present_in_resume_text, and
#   verify_skill_target_plan into a provider-free policy module. Replaced
#   upstream dict return values with SkillTargetPlan / SkillTarget /
#   SkillTargetRejection schemas, added evidence-backed support, and records
#   duplicate targets as deterministic rejections. No LLM, no app.* imports.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence

from resume_kit_schemas.evidence import CandidateEvidence
from resume_kit_schemas.job import JobDescription, Requirement
from resume_kit_schemas.results import (
    PolicyReasonCode,
    SkillTarget,
    SkillTargetPlan,
    SkillTargetRejection,
    SkillTargetSource,
)
from resume_kit_schemas.resume import ResumeDocument

__all__ = [
    "AllowedSkillTargetInput",
    "JobKeywordsInput",
    "PlannerOutput",
    "ResumeInput",
    "build_allowed_skill_target_keys",
    "verify_skill_target_plan",
]

PlannerOutput = Mapping[str, object]
ResumeInput = ResumeDocument | Mapping[str, object]
JobKeywordsInput = JobDescription | Mapping[str, object]
EvidenceInput = CandidateEvidence | Mapping[str, object]
AllowedSkillTargetInput = SkillTarget | Mapping[str, object] | str


def _normalize_skill_key(skill: str) -> str:
    """Normalize a skill for case-insensitive comparison."""

    return re.sub(r"\s+", " ", skill.strip()).casefold()


def _extract_skill_index(items: object) -> dict[str, str]:
    """Build a normalized skill index from a string list."""

    if not isinstance(items, list):
        return {}
    index: dict[str, str] = {}
    for item in items:
        if not isinstance(item, str):
            continue
        skill = item.strip()
        if skill:
            index.setdefault(_normalize_skill_key(skill), skill)
    return index


def _skill_mentioned_in_text(skill: str, text: str) -> bool:
    """Return True when a skill phrase appears as a whole term in text."""

    escaped = re.escape(skill.strip().lower())
    if not escaped:
        return False
    return bool(re.search(rf"(?<!\w){escaped}(?!\w)", text.lower()))


def _skill_from_allowed_target(target: AllowedSkillTargetInput) -> str:
    if isinstance(target, str):
        return target
    if isinstance(target, SkillTarget):
        return target.display_skill or target.normalized_skill

    skill_value = target.get("skill")
    if isinstance(skill_value, str):
        return skill_value
    display_skill_value = target.get("display_skill")
    if isinstance(display_skill_value, str):
        return display_skill_value
    normalized_skill_value = target.get("normalized_skill")
    if isinstance(normalized_skill_value, str):
        return normalized_skill_value
    return ""


def _build_allowed_skill_target_keys(
    allowed_skill_targets: SkillTargetPlan | Sequence[AllowedSkillTargetInput] | None,
) -> set[str]:
    """Build normalized keys for skills approved by the planning verifier."""

    if allowed_skill_targets is None:
        return set()
    if isinstance(allowed_skill_targets, SkillTargetPlan):
        targets: Sequence[AllowedSkillTargetInput] = allowed_skill_targets.accepted_targets
    else:
        targets = allowed_skill_targets

    keys: set[str] = set()
    for target in targets:
        skill = _skill_from_allowed_target(target)
        if skill.strip():
            keys.add(_normalize_skill_key(skill))
    return keys


def build_allowed_skill_target_keys(
    allowed_skill_targets: SkillTargetPlan | Sequence[AllowedSkillTargetInput] | None,
) -> set[str]:
    """Return normalized skill keys accepted by the verifier.

    This is the public helper the alignment apply engine can call without
    importing from any alignment package. It accepts the upstream
    string/dict-list shape plus the canonical ``SkillTargetPlan`` schema.
    """

    return _build_allowed_skill_target_keys(allowed_skill_targets)


def _as_mapping(value: object) -> Mapping[str, object]:
    if isinstance(value, Mapping):
        return value
    return {}


def _requirement_terms(requirements: Sequence[Requirement]) -> list[str]:
    terms: list[str] = []
    for requirement in requirements:
        terms.append(requirement.text)
        terms.extend(requirement.keywords)
    return terms


def _to_resume_dict(resume: ResumeInput) -> dict[str, object]:
    if isinstance(resume, ResumeDocument):
        return resume.model_dump()
    return dict(resume)


def _job_text_from_schema(job: JobDescription) -> str:
    parts: list[str] = [job.raw_text, job.summary]
    parts.extend(requirement.text for requirement in job.requirements)
    for requirement in job.requirements:
        parts.extend(requirement.keywords)
    parts.extend(requirement.text for requirement in job.qualifications)
    for requirement in job.qualifications:
        parts.extend(requirement.keywords)
    parts.extend(job.keywords)
    return " ".join(part for part in parts if part)


def _job_text_from_mapping(job: Mapping[str, object]) -> str | None:
    for key in ("job_description", "description", "raw_text", "summary"):
        value = job.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return None


def _to_job_keywords_dict(job_keywords: JobKeywordsInput) -> dict[str, object]:
    if isinstance(job_keywords, JobDescription):
        return {
            "required_skills": _requirement_terms(job_keywords.requirements),
            "preferred_skills": _requirement_terms(job_keywords.qualifications),
            "keywords": list(job_keywords.keywords),
        }
    return dict(job_keywords)


def _resolve_job_description(
    job_keywords: JobKeywordsInput, job_description: str | None
) -> str | None:
    if job_description is not None:
        return job_description
    if isinstance(job_keywords, JobDescription):
        text = _job_text_from_schema(job_keywords)
        return text if text else None
    return _job_text_from_mapping(job_keywords)


def _extract_jd_skill_index(
    job_keywords: JobKeywordsInput,
    job_description: str | None = None,
) -> dict[str, str]:
    """Build a normalized index of explicit JD skills."""

    keywords = _to_job_keywords_dict(job_keywords)
    description = _resolve_job_description(job_keywords, job_description)
    index: dict[str, str] = {}
    for field in ("required_skills", "preferred_skills"):
        values = keywords.get(field, [])
        if not isinstance(values, list):
            continue
        for value in values:
            if not isinstance(value, str):
                continue
            skill = value.strip()
            if skill and (
                description is None or _skill_mentioned_in_text(skill, description)
            ):
                index.setdefault(_normalize_skill_key(skill), skill)
    return index


def _skill_present_in_resume_text(skill: str, resume_data: Mapping[str, object]) -> bool:
    """Return True when a skill phrase already appears in the resume text."""

    text = json.dumps(resume_data, ensure_ascii=False, default=str)
    return _skill_mentioned_in_text(skill, text)


def _technical_skills_from_resume(resume_data: Mapping[str, object]) -> object:
    additional = _as_mapping(resume_data.get("additional"))
    return additional.get("technicalSkills", [])


def _candidate_evidence_from_inputs(
    candidate_evidence: Sequence[EvidenceInput] | None,
) -> list[CandidateEvidence]:
    evidence: list[CandidateEvidence] = []
    for item in candidate_evidence or []:
        if isinstance(item, CandidateEvidence):
            evidence.append(item)
        elif isinstance(item, Mapping):
            evidence.append(CandidateEvidence.model_validate(item))
    return evidence


def _evidence_supports_skill(
    skill: str, candidate_evidence: Sequence[CandidateEvidence]
) -> list[CandidateEvidence]:
    skill_key = _normalize_skill_key(skill)
    matches: list[CandidateEvidence] = []
    for evidence in candidate_evidence:
        tag_keys = {_normalize_skill_key(tag) for tag in evidence.tags if tag.strip()}
        if skill_key in tag_keys and _skill_mentioned_in_text(skill, evidence.content):
            matches.append(evidence)
    return matches


def _extract_target_skill_and_reason(target: object) -> tuple[str, str] | None:
    if isinstance(target, str):
        return target.strip(), ""
    if isinstance(target, Mapping):
        skill_value = target.get("skill", "")
        reason_value = target.get("reason", "")
        skill = skill_value if isinstance(skill_value, str) else str(skill_value)
        reason = reason_value if isinstance(reason_value, str) else str(reason_value)
        return skill.strip(), reason.strip()
    return None


def _raw_targets(raw_plan: PlannerOutput) -> list[object]:
    targets = raw_plan.get("target_skills", [])
    if not isinstance(targets, list):
        return []
    return targets


def _target_rejection(
    skill: str,
    reason_code: PolicyReasonCode,
    reason: str,
) -> SkillTargetRejection:
    return SkillTargetRejection(
        normalized_skill=_normalize_skill_key(skill),
        display_skill=skill,
        reason_code=reason_code,
        reason=reason,
    )


def verify_skill_target_plan(
    raw_plan: PlannerOutput,
    original_resume: ResumeInput,
    job_keywords: JobKeywordsInput,
    job_description: str | None = None,
    candidate_evidence: Sequence[EvidenceInput] | None = None,
) -> SkillTargetPlan:
    """Filter and classify planner-proposed skill targets before diff generation.

    Existing resume skills are accepted as low-risk targets. Required and
    preferred JD skills are accepted as explicit JD-added targets for user
    review. Other skills are accepted only when they already appear in the
    resume text or have unambiguous candidate-evidence support.
    """

    resume_data = _to_resume_dict(original_resume)
    original_skills = _extract_skill_index(_technical_skills_from_resume(resume_data))
    jd_skills = _extract_jd_skill_index(job_keywords, job_description)
    evidence = _candidate_evidence_from_inputs(candidate_evidence)

    proposed: list[str] = []
    accepted: list[SkillTarget] = []
    rejected: list[SkillTargetRejection] = []
    seen: set[str] = set()

    for raw_target in _raw_targets(raw_plan):
        extracted = _extract_target_skill_and_reason(raw_target)
        if extracted is None:
            continue
        skill, raw_reason = extracted
        if not skill:
            continue

        proposed.append(skill)
        skill_key = _normalize_skill_key(skill)
        if skill_key in seen:
            rejected.append(
                _target_rejection(
                    skill=skill,
                    reason_code=PolicyReasonCode.DUPLICATE_SKILL,
                    reason="Duplicate skill target already evaluated",
                )
            )
            continue
        seen.add(skill_key)

        if skill_key in original_skills:
            accepted.append(
                SkillTarget(
                    normalized_skill=skill_key,
                    display_skill=original_skills[skill_key],
                    source=SkillTargetSource.EXISTING,
                    reason=raw_reason or "Already present in resume skills",
                )
            )
            continue

        if skill_key in jd_skills:
            accepted.append(
                SkillTarget(
                    normalized_skill=skill_key,
                    display_skill=jd_skills[skill_key],
                    source=SkillTargetSource.JD_ADDED,
                    reason=raw_reason or "Required or preferred by the job description",
                )
            )
            continue

        if _skill_present_in_resume_text(skill, resume_data):
            accepted.append(
                SkillTarget(
                    normalized_skill=skill_key,
                    display_skill=skill,
                    source=SkillTargetSource.SUPPORTED_BY_RESUME,
                    reason=raw_reason or "Appears in the existing resume content",
                )
            )
            continue

        supporting_evidence = _evidence_supports_skill(skill, evidence)
        if supporting_evidence:
            accepted.append(
                SkillTarget(
                    normalized_skill=skill_key,
                    display_skill=skill,
                    source=SkillTargetSource.EVIDENCE_BACKED,
                    reason=raw_reason or "Supported by candidate evidence",
                    evidence_ids=[item.id for item in supporting_evidence],
                    evidence_kinds=[item.kind for item in supporting_evidence],
                )
            )
            continue

        rejected.append(
            _target_rejection(
                skill=skill,
                reason_code=PolicyReasonCode.UNSUPPORTED_SKILL,
                reason=raw_reason or "Not found in resume, job keywords, or evidence",
            )
        )

    return SkillTargetPlan(
        proposed_skills=proposed,
        accepted_targets=accepted,
        rejected_targets=rejected,
        supporting_evidence=evidence,
        job=job_keywords if isinstance(job_keywords, JobDescription) else None,
    )
