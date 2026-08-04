"""Deterministic truthfulness-rule constants for prompts/orchestration.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/prompts/templates.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc  Apache-2.0
# Modified: Ported the CRITICAL_TRUTHFULNESS_RULES_TEMPLATE string constant,
#   the _build_truthfulness_rules formatter, and the CRITICAL_TRUTHFULNESS_RULES
#   {nudge, keywords, full} mapping verbatim into a provider-free module. No LLM,
#   no app.* imports — these are pure strings reused by prompt/orchestration
#   layers. The rule text is preserved exactly as upstream.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

__all__ = [
    "CRITICAL_TRUTHFULNESS_RULES",
    "CRITICAL_TRUTHFULNESS_RULES_TEMPLATE",
    "build_truthfulness_rules",
]

# Rule text preserved verbatim from upstream; assembled via implicit string
# concatenation so each physical source line stays within the line-length limit
# without altering the emitted prompt content (newlines are significant).
CRITICAL_TRUTHFULNESS_RULES_TEMPLATE = (
    "CRITICAL TRUTHFULNESS RULES - NEVER VIOLATE:\n"
    "1. DO NOT add any skill, tool, technology, or certification that is not "
    "explicitly mentioned in the original resume\n"
    '2. DO NOT invent numeric achievements (e.g., "increased by 30%") unless '
    "they exist in original\n"
    "3. DO NOT add company names, product names, or technical terms not in the original\n"
    '4. DO NOT upgrade experience level (e.g., "Junior" -> "Senior")\n'
    "5. DO NOT add languages, frameworks, or platforms the candidate hasn't used\n"
    "6. DO NOT extend employment dates or change timelines. Copy date ranges "
    "exactly as they appear, including months.\n"
    "7. {rule_7}\n"
    "8. Preserve factual accuracy - only use information provided by the candidate\n"
    "9. NEVER remove existing skills, certifications, languages, or awards. You "
    "may reorder by relevance, but every original item must remain.\n"
    "\n"
    "Violation of these rules could cause serious problems for the candidate in job interviews.\n"
)


def build_truthfulness_rules(rule_7: str) -> str:
    """Fill the truthfulness-rules template with a variant-specific rule 7."""

    return CRITICAL_TRUTHFULNESS_RULES_TEMPLATE.format(rule_7=rule_7)


CRITICAL_TRUTHFULNESS_RULES: dict[str, str] = {
    "nudge": build_truthfulness_rules(
        "DO NOT add new bullet points or content - only rephrase existing content"
    ),
    "keywords": build_truthfulness_rules(
        "You may rephrase existing bullet points to include keywords, "
        "but do NOT add new bullet points"
    ),
    "full": build_truthfulness_rules(
        "You may expand existing bullet points or add new ones that elaborate "
        "on existing work, but DO NOT invent entirely new responsibilities"
    ),
}
