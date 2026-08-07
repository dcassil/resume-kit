# ---------------------------------------------------------------------------
# Derived from apps/backend/app/prompts/templates.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# License: Apache-2.0
# Modified: Ported ``EXTRACT_KEYWORDS_PROMPT`` verbatim as a pure string
#   constant. No behavioral change to the prompt text itself; the surrounding
#   ``app.prompts`` module coupling (placeholder validation, re-exports) is
#   dropped. The ``{job_description}`` format placeholder is preserved so the
#   provider-injected parser can inject the raw posting text.
# ---------------------------------------------------------------------------
"""Prompt constants for job-description keyword extraction.

This module holds only pure string templates. It has no provider, network, or
SDK dependency; the string is consumed by
:mod:`resume_kit_job_parser.parse`, which formats ``{job_description}`` and
sends it through a :class:`~resume_kit_core.providers.StructuredCompletionProvider`.
"""

from __future__ import annotations

# The first prompt line is preserved verbatim from upstream and exceeds the
# 100-char line limit; splitting it would alter the prompt text sent to the LLM.
EXTRACT_KEYWORDS_PROMPT = """Extract job requirements as JSON. Output ONLY the JSON object, no other text.

Example format:
{{
  "company": "Acme Corp",
  "role": "Senior Backend Engineer",
  "required_skills": ["Python", "AWS"],
  "preferred_skills": ["Kubernetes"],
  "experience_requirements": ["5+ years"],
  "education_requirements": ["Bachelor's in CS"],
  "key_responsibilities": ["Lead team"],
  "keywords": ["microservices", "agile"],
  "experience_years": 5,
  "seniority_level": "senior"
}}

Extract numeric years (e.g., "5+ years" → 5) and infer seniority level.
Set "company" to the hiring company name and "role" to the job title exactly as
written in the posting; use an empty string for either if it is not stated.

"required_skills", "preferred_skills", and "keywords" MUST be concrete skill
tokens or short noun phrases (e.g. "Python", "CI/CD", "distributed systems"),
NOT full requirement sentences. Do not put clauses like "4-6+ years of
experience building large-scale web apps" in these arrays — extract the concrete
skills from such sentences instead (e.g. "large-scale web apps"). Prose belongs
in "experience_requirements" / "key_responsibilities".

Job description:
{job_description}"""  # noqa: E501
"""Job-keyword extraction prompt (from apps/backend/app/prompts/templates.py)."""
