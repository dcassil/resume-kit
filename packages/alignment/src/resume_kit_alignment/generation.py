"""Provider-injected proposal generation for controlled alignment.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/services/improver.py
#   (generate_resume_diffs, generate_skill_target_plan,
#    _prepare_keywords_for_prompt, _prepare_skill_targets_for_prompt)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Replaced upstream app-level complete_json usage with the injected
#   StructuredCompletionProvider boundary. This module parses proposals only:
#   it never returns, applies, stores, or mutates a final resume document.
#   Skill targets are passed through resume_kit_policy.skill_targets'
#   deterministic verifier before returning SkillTargetPlan.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence

from pydantic import ValidationError
from resume_kit_core.providers import (
    MessageParam,
    StructuredCompletionProvider,
    StructuredCompletionRequest,
)
from resume_kit_policy.sanitizer import sanitize_user_input
from resume_kit_policy.skill_targets import verify_skill_target_plan
from resume_kit_schemas.change import ChangeProposal, ChangeSet
from resume_kit_schemas.common import Warning
from resume_kit_schemas.evidence import CandidateEvidence
from resume_kit_schemas.job import JobDescription
from resume_kit_schemas.results import SkillTarget, SkillTargetPlan
from resume_kit_schemas.resume import ResumeDocument

from resume_kit_alignment.prompts import (
    CRITICAL_TRUTHFULNESS_RULES,
    DEFAULT_IMPROVE_PROMPT_ID,
    DIFF_IMPROVE_PROMPT,
    DIFF_STRATEGY_INSTRUCTIONS,
    SKILL_TARGET_PLAN_PROMPT,
    get_language_name,
)

ResumeInput = ResumeDocument | Mapping[str, object]
JobKeywordsInput = JobDescription | Mapping[str, object]
SkillTargetInput = SkillTarget | Mapping[str, object] | str
EvidenceInput = CandidateEvidence | Mapping[str, object]

__all__ = ["generate_change_proposals", "generate_skill_target_plan"]


def _warning(message: str, *, code: str, field_path: str | None = None) -> Warning:
    return Warning(message=message, code=code, field_path=field_path)


def _warning_from_exception(
    message: str,
    exception: Exception,
    *,
    code: str,
) -> Warning:
    return _warning(
        f"{message}: {exception}",
        code=code,
    )


def _json_for_prompt(value: object) -> str:
    return sanitize_user_input(json.dumps(value, ensure_ascii=False, default=str))


def _resume_for_prompt(
    original_resume: str,
    original_resume_data: ResumeInput | None,
) -> str:
    if original_resume_data is None:
        return sanitize_user_input(original_resume)
    if isinstance(original_resume_data, ResumeDocument):
        return _json_for_prompt(original_resume_data.model_dump())
    return _json_for_prompt(dict(original_resume_data))


def _existing_skills_for_prompt(original_resume_data: ResumeInput) -> str:
    data: Mapping[str, object]
    if isinstance(original_resume_data, ResumeDocument):
        data = original_resume_data.model_dump()
    else:
        data = original_resume_data
    additional = data.get("additional")
    if not isinstance(additional, Mapping):
        return "[]"
    skills = additional.get("technicalSkills", [])
    return _json_for_prompt(skills)


def _string_items(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [sanitize_user_input(str(item)) for item in value]


def _terms_from_requirements(requirements: object) -> list[str]:
    if not isinstance(requirements, list):
        return []
    terms: list[str] = []
    for requirement in requirements:
        if not isinstance(requirement, Mapping):
            continue
        text = requirement.get("text")
        if isinstance(text, str) and text.strip():
            terms.append(sanitize_user_input(text))
        terms.extend(_string_items(requirement.get("keywords", [])))
    return terms


def _job_keywords_mapping(job_keywords: JobKeywordsInput) -> Mapping[str, object]:
    if isinstance(job_keywords, JobDescription):
        return {
            "required_skills": [
                sanitize_user_input(term)
                for requirement in job_keywords.requirements
                for term in [requirement.text, *requirement.keywords]
                if term
            ],
            "preferred_skills": [
                sanitize_user_input(term)
                for requirement in job_keywords.qualifications
                for term in [requirement.text, *requirement.keywords]
                if term
            ],
            "keywords": [sanitize_user_input(term) for term in job_keywords.keywords],
        }
    return job_keywords


def _prepare_keywords_for_prompt(job_keywords: JobKeywordsInput) -> str:
    """Format job keywords as a focused, sanitized list for the provider prompt."""

    data = _job_keywords_mapping(job_keywords)
    sections: list[str] = []

    required = _string_items(data.get("required_skills", []))
    if not required and "requirements" in data:
        required = _terms_from_requirements(data.get("requirements"))
    if required:
        sections.append("Required skills to emphasize:\n- " + "\n- ".join(required))

    preferred = _string_items(data.get("preferred_skills", []))
    if not preferred and "qualifications" in data:
        preferred = _terms_from_requirements(data.get("qualifications"))
    if preferred:
        sections.append(
            "Preferred skills (include only if resume supports them):\n- "
            + "\n- ".join(preferred)
        )

    keywords = _string_items(data.get("keywords", []))
    if keywords:
        sections.append(
            "Additional keywords to weave in naturally:\n- " + "\n- ".join(keywords)
        )

    return "\n\n".join(sections) if sections else "No specific keywords extracted."


def _skill_target_parts(target: SkillTargetInput) -> tuple[str, str, str]:
    if isinstance(target, str):
        return sanitize_user_input(target.strip()), "unknown", ""
    if isinstance(target, SkillTarget):
        return (
            sanitize_user_input(target.display_skill or target.normalized_skill),
            target.source.value,
            sanitize_user_input(target.reason),
        )

    skill_value = target.get("skill")
    if not isinstance(skill_value, str):
        skill_value = target.get("display_skill")
    if not isinstance(skill_value, str):
        skill_value = target.get("normalized_skill")
    source_value = target.get("source", "unknown")
    reason_value = target.get("reason", "")
    skill = skill_value if isinstance(skill_value, str) else ""
    source = source_value if isinstance(source_value, str) else str(source_value)
    reason = reason_value if isinstance(reason_value, str) else str(reason_value)
    return (
        sanitize_user_input(skill.strip()),
        sanitize_user_input(source.strip() or "unknown"),
        sanitize_user_input(reason.strip()),
    )


def _prepare_skill_targets_for_prompt(
    skill_targets: SkillTargetPlan | Sequence[SkillTargetInput] | None,
) -> str:
    """Format verified skill targets for the proposal prompt."""

    if skill_targets is None:
        return "No verified skill targets."
    targets: Sequence[SkillTargetInput]
    if isinstance(skill_targets, SkillTargetPlan):
        targets = skill_targets.accepted_targets
    else:
        targets = skill_targets

    lines: list[str] = []
    for target in targets:
        skill, source, reason = _skill_target_parts(target)
        if not skill:
            continue
        suffix = f": {reason}" if reason else ""
        lines.append(f"- {skill} ({source}){suffix}")
    return "\n".join(lines) if lines else "No verified skill targets."


def _change_request_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": True,
        "required": ["changes"],
        "properties": {
            "changes": {
                "type": "array",
                "items": ChangeProposal.model_json_schema(),
            },
            "strategy_notes": {"type": "string"},
        },
    }


def _skill_plan_request_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": True,
        "required": ["target_skills"],
        "properties": {
            "target_skills": {
                "type": "array",
                "items": {
                    "oneOf": [
                        {"type": "string"},
                        {
                            "type": "object",
                            "properties": {
                                "skill": {"type": "string"},
                                "reason": {"type": "string"},
                            },
                        },
                    ]
                },
            },
            "strategy_notes": {"type": "string"},
        },
    }


def _messages(prompt: str, system_prompt: str) -> list[MessageParam]:
    return [
        MessageParam(role="system", content=system_prompt),
        MessageParam(role="user", content=prompt),
    ]


def _strategy_notes(response: Mapping[str, object]) -> str:
    value = response.get("strategy_notes", "")
    return value if isinstance(value, str) else str(value)


def _parse_change_proposals(
    response: Mapping[str, object],
) -> tuple[list[ChangeProposal], list[Warning]]:
    warnings: list[Warning] = []
    if "changes" not in response:
        warnings.append(
            _warning(
                "Provider output had no 'changes' key; returned zero proposals.",
                code="provider_missing_changes",
            )
        )
        return [], warnings

    raw_changes = response.get("changes")
    if not isinstance(raw_changes, list):
        warnings.append(
            _warning(
                "Provider output field 'changes' was not a list; returned zero proposals.",
                code="provider_non_list_changes",
            )
        )
        return [], warnings

    changes: list[ChangeProposal] = []
    for index, raw_change in enumerate(raw_changes):
        if not isinstance(raw_change, Mapping):
            warnings.append(
                _warning(
                    f"Skipped malformed change at index {index}: expected object.",
                    code="provider_malformed_change",
                )
            )
            continue
        try:
            changes.append(ChangeProposal.model_validate(raw_change))
        except ValidationError as exc:
            warnings.append(
                _warning_from_exception(
                    f"Skipped malformed change at index {index}",
                    exc,
                    code="provider_malformed_change",
                )
            )
    return changes, warnings


def _raw_target_skill(raw_target: object) -> dict[str, str] | None:
    if isinstance(raw_target, str):
        skill = raw_target.strip()
        if not skill:
            return None
        return {"skill": skill, "reason": ""}
    if not isinstance(raw_target, Mapping):
        return None
    skill_value = raw_target.get("skill", "")
    reason_value = raw_target.get("reason", "")
    skill = skill_value if isinstance(skill_value, str) else str(skill_value)
    reason = reason_value if isinstance(reason_value, str) else str(reason_value)
    skill = skill.strip()
    if not skill:
        return None
    return {
        "skill": sanitize_user_input(skill),
        "reason": sanitize_user_input(reason.strip()),
    }


def _parse_raw_skill_targets(response: Mapping[str, object]) -> dict[str, object]:
    raw_targets = response.get("target_skills", [])
    if not isinstance(raw_targets, list):
        return {"target_skills": []}

    targets: list[dict[str, str]] = []
    for raw_target in raw_targets:
        parsed = _raw_target_skill(raw_target)
        if parsed is not None:
            targets.append(parsed)
    return {
        "target_skills": targets,
        "strategy_notes": _strategy_notes(response),
    }


async def generate_change_proposals(
    provider: StructuredCompletionProvider,
    original_resume: str,
    job_description: str,
    job_keywords: JobKeywordsInput,
    *,
    language: str = "en",
    prompt_id: str | None = None,
    original_resume_data: ResumeInput | None = None,
    skill_targets: SkillTargetPlan | Sequence[SkillTargetInput] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 4096,
) -> ChangeSet:
    """Generate proposal-only resume changes via an injected structured provider."""

    selected_id = prompt_id or DEFAULT_IMPROVE_PROMPT_ID
    strategy_instruction = DIFF_STRATEGY_INSTRUCTIONS.get(
        selected_id, DIFF_STRATEGY_INSTRUCTIONS[DEFAULT_IMPROVE_PROMPT_ID]
    )
    unknown_strategy_warning: Warning | None = None
    if selected_id not in DIFF_STRATEGY_INSTRUCTIONS:
        unknown_strategy_warning = _warning(
            f"Unknown prompt_id '{selected_id}'; used default diff strategy.",
            code="unknown_prompt_id",
        )

    prompt = DIFF_IMPROVE_PROMPT.format(
        critical_truthfulness_rules=CRITICAL_TRUTHFULNESS_RULES.get(
            selected_id, CRITICAL_TRUTHFULNESS_RULES[DEFAULT_IMPROVE_PROMPT_ID]
        ),
        strategy_instruction=strategy_instruction,
        output_language=get_language_name(language),
        job_keywords=_prepare_keywords_for_prompt(job_keywords),
        skill_targets=_prepare_skill_targets_for_prompt(skill_targets),
        job_description=sanitize_user_input(job_description),
        original_resume=_resume_for_prompt(original_resume, original_resume_data),
    )
    request = StructuredCompletionRequest(
        messages=_messages(
            prompt,
            "You are an expert resume editor. Output only valid JSON with "
            "targeted change proposals.",
        ),
        output_schema=_change_request_schema(),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    try:
        response: Mapping[str, object] = await provider.complete_json(request)
    except Exception as exc:
        warnings = [
            _warning_from_exception(
                "Provider failed while generating change proposals",
                exc,
                code="provider_failure",
            )
        ]
        if unknown_strategy_warning is not None:
            warnings.insert(0, unknown_strategy_warning)
        return ChangeSet(warnings=warnings)

    changes, warnings = _parse_change_proposals(response)
    if unknown_strategy_warning is not None:
        warnings.insert(0, unknown_strategy_warning)

    return ChangeSet(
        changes=changes,
        strategy_notes=_strategy_notes(response),
        warnings=warnings,
    )


async def generate_skill_target_plan(
    provider: StructuredCompletionProvider,
    original_resume_data: ResumeInput,
    job_description: str,
    job_keywords: JobKeywordsInput,
    *,
    language: str = "en",
    candidate_evidence: Sequence[EvidenceInput] | None = None,
    model: str | None = None,
    temperature: float | None = None,
    max_tokens: int = 2048,
) -> SkillTargetPlan:
    """Generate and deterministically verify target skills for proposal generation."""

    prompt = SKILL_TARGET_PLAN_PROMPT.format(
        output_language=get_language_name(language),
        existing_skills=_existing_skills_for_prompt(original_resume_data),
        job_keywords=_prepare_keywords_for_prompt(job_keywords),
        job_description=sanitize_user_input(job_description),
        original_resume=_resume_for_prompt("", original_resume_data),
    )
    request = StructuredCompletionRequest(
        messages=_messages(
            prompt,
            "You are a resume skill planning agent. Output only valid JSON with "
            "target_skills and strategy_notes.",
        ),
        output_schema=_skill_plan_request_schema(),
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    try:
        response: Mapping[str, object] = await provider.complete_json(request)
    except Exception:
        response = {"target_skills": []}

    raw_plan = _parse_raw_skill_targets(response)
    return verify_skill_target_plan(
        raw_plan,
        original_resume_data,
        job_keywords,
        sanitize_user_input(job_description),
        candidate_evidence,
    )
