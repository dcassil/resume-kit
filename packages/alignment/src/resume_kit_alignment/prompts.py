"""Prompt templates for provider-injected proposal generation.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/prompts/templates.py
#   (get_language_name, CRITICAL_TRUTHFULNESS_RULES_TEMPLATE,
#    CRITICAL_TRUTHFULNESS_RULES, DIFF_STRATEGY_INSTRUCTIONS,
#    SKILL_TARGET_PLAN_PROMPT, DIFF_IMPROVE_PROMPT)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Kept only provider-agnostic prompt constants needed by Phase 4
#   proposal generation. The diff prompt explicitly asks for proposals only
#   and forbids final/applied resume output; concrete provider imports and
#   app.* dependencies are intentionally absent. Long prompt lines are packaged
#   via implicit string concatenation to satisfy the line-length limit without
#   changing the emitted prompt text.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

from typing import Final

LANGUAGE_NAMES: Final[dict[str, str]] = {
    "en": "English",
    "es": "Spanish",
    "zh": "Chinese (Simplified)",
    "ja": "Japanese",
    "pt": "Brazilian Portuguese",
    "fr": "French",
    "ko": "Korean",
}

DEFAULT_IMPROVE_PROMPT_ID: Final[str] = "keywords"

CRITICAL_TRUTHFULNESS_RULES_TEMPLATE: Final[str] = (
    "CRITICAL TRUTHFULNESS RULES - NEVER VIOLATE:\n"
    "1. DO NOT add any skill, tool, technology, or certification that is not "
    "explicitly mentioned in the original resume unless it is a verified skill target\n"
    "2. DO NOT invent numeric achievements unless they exist in the original resume\n"
    "3. DO NOT add company names, product names, or technical terms not in the "
    "original resume or verified skill targets\n"
    "4. DO NOT upgrade experience level\n"
    "5. DO NOT add languages, frameworks, or platforms the candidate has not used "
    "unless verified for human review\n"
    "6. DO NOT extend employment dates or change timelines\n"
    "7. {rule_7}\n"
    "8. Preserve factual accuracy - only use information provided by the candidate "
    "or verified targets\n"
    "9. NEVER remove existing skills, certifications, languages, or awards; you may "
    "only propose reorder/addition changes for review.\n"
)


def _build_truthfulness_rules(rule_7: str) -> str:
    return CRITICAL_TRUTHFULNESS_RULES_TEMPLATE.format(rule_7=rule_7)


CRITICAL_TRUTHFULNESS_RULES: Final[dict[str, str]] = {
    "nudge": _build_truthfulness_rules(
        "DO NOT add new bullet points or content - only propose rephrasing existing content"
    ),
    "keywords": _build_truthfulness_rules(
        "You may propose rephrasing existing bullet points to include keywords, "
        "but do NOT add new bullet points"
    ),
    "full": _build_truthfulness_rules(
        "You may propose new bullets that elaborate on existing work, "
        "but do NOT invent entirely new responsibilities"
    ),
}

DIFF_STRATEGY_INSTRUCTIONS: Final[dict[str, str]] = {
    "nudge": (
        "Make minimal edits. Only rephrase where there is a clear match. "
        "Do not add new bullet points."
    ),
    "keywords": (
        "Weave in relevant keywords where evidence already exists. "
        "You may rephrase bullets but do not add new ones."
    ),
    "full": (
        "Make targeted adjustments. You may rephrase bullets, add verified JD "
        "skills, and add new bullets that elaborate on existing work, but do not "
        "invent new responsibilities."
    ),
}

SKILL_TARGET_PLAN_PROMPT: Final[str] = (
    """Build a concise skill target plan for tailoring this resume to the job.

Return ONLY a JSON object. Do not rewrite the resume.

Rules:
1. Prefer required and preferred JD skills.
2. Include existing resume skills that are highly relevant to the JD.
3. You may include JD skills that are missing from the resume skills list.
4. Do not include skills unrelated to the JD.
5. Do not include certifications.
6. Generate reasons in {output_language}.

Existing resume skills:
{existing_skills}

JD keywords and skills:
{job_keywords}

Job Description:
{job_description}

Resume JSON:
{original_resume}

Output this exact JSON format:
{{
  "target_skills": [
    {{
      "skill": "skill name",
      "reason": "why this skill should be emphasized"
    }}
  ],
  "strategy_notes": "brief notes for the next editing pass"
}}"""
)

DIFF_IMPROVE_PROMPT: Final[str] = (
    "Given this resume and job description, output a JSON object with targeted "
    "change proposals to better align the resume with the job.\n"
    "\n"
    "Do NOT return, rewrite, or apply a final resume document. This step proposes "
    "changes only; another component applies approved proposals.\n"
    "\n"
    "{critical_truthfulness_rules}\n"
    "\n"
    "RULES:\n"
    "1. Only propose content changes; never change names, companies, dates, "
    "institutions, or degrees\n"
    "2. Do not invent metrics or achievements not supported by the original resume text\n"
    "3. Do not add new work entries, education entries, or project entries\n"
    "4. {strategy_instruction}\n"
    "5. Each change MUST include the original text copied exactly so it can be "
    "verified before application\n"
    "6. For each change, explain WHY it helps match the job description\n"
    "7. Generate all proposed new text in {output_language}\n"
    "8. Do not use em dash characters\n"
    "9. Keep changes minimal and targeted; do not rewrite content that already aligns well\n"
    "10. You may add a skill only if it appears in the verified skill targets below\n"
    "11. Reframe existing content in the job description's terminology only when the "
    "candidate's original content already supports the claim\n"
    "12. Preserve original capitalization, especially for proper nouns, technical "
    "terms, and acronyms\n"
    "\n"
    "PATHS you can target:\n"
    '- "summary" - the resume summary text\n'
    '- "workExperience[i].description[j]" - a specific bullet\n'
    '- "workExperience[i].description" - append a new bullet (action: "append")\n'
    '- "personalProjects[i].description[j]" - a specific project bullet\n'
    '- "personalProjects[i].description" - append a new project bullet (action: "append")\n'
    '- "education[i].description" - the education entry\'s description text\n'
    '- "additional.technicalSkills" - reorder the skills list (action: "reorder") '
    'or add one verified skill (action: "add_skill")\n'
    '- "additional.languages" - reorder the languages list (action: "reorder")\n'
    '- "additional.certificationsTraining" - reorder the certifications list (action: "reorder")\n'
    '- "additional.awards" - reorder the awards list (action: "reorder")\n'
    "\n"
    "Do NOT target: personalInfo, dates/years, company names, education "
    "degree/institution/years, customSections.\n"
    "\n"
    "Keywords to emphasize:\n"
    "{job_keywords}\n"
    "\n"
    "Verified skill targets:\n"
    "{skill_targets}\n"
    "\n"
    "Job Description:\n"
    "{job_description}\n"
    "\n"
    "Original Resume:\n"
    "{original_resume}\n"
    "\n"
    "Output this exact JSON format, nothing else:\n"
    "{{\n"
    '  "changes": [\n'
    "    {{\n"
    '      "path": "workExperience[0].description[1]",\n'
    '      "action": "replace",\n'
    '      "original": "the exact original text at this path",\n'
    '      "value": "the improved text",\n'
    '      "reason": "why this change helps"\n'
    "    }},\n"
    "    {{\n"
    '      "path": "additional.technicalSkills",\n'
    '      "action": "reorder",\n'
    '      "original": ["current skill order"],\n'
    '      "value": ["most relevant skill first", "then next"],\n'
    '      "reason": "reordered to prioritize JD-relevant skills"\n'
    "    }},\n"
    "    {{\n"
    '      "path": "additional.technicalSkills",\n'
    '      "action": "add_skill",\n'
    '      "original": null,\n'
    '      "value": "verified skill target missing from the skills list",\n'
    '      "reason": "added verified JD skill for review"\n'
    "    }}\n"
    "  ],\n"
    '  "strategy_notes": "brief summary of the tailoring approach"\n'
    "}}"
)


def get_language_name(code: str) -> str:
    """Return a prompt-facing language name for a language code."""

    return LANGUAGE_NAMES.get(code, "English")
