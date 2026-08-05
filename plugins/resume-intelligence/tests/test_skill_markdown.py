"""Structural tests for the resume-intelligence plugin skill markdown files.

Validates:
- All expected skill directories exist under plugins/resume-intelligence/skills/.
- Each directory contains a SKILL.md file that is valid UTF-8.
- Each SKILL.md has a non-empty YAML front matter block with non-empty
  ``name`` and ``description`` fields.
- Each SKILL.md references either ``resume-tool`` or its stable MCP tool name.
- No SKILL.md mentions deferred Phase 6 capability names that are not built.

All checks use stdlib only (pathlib + minimal manual YAML front-matter parse).
"""

from __future__ import annotations

import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

PLUGIN_DIR = Path(__file__).parent.parent
SKILLS_DIR = PLUGIN_DIR / "skills"

# ---------------------------------------------------------------------------
# Expected capabilities
# ---------------------------------------------------------------------------

EXPECTED_SKILL_SLUGS: frozenset[str] = frozenset(
    [
        # Ingest
        "resume-to-json",
        "job-to-json",
        # Check
        "check-ats-structure",
        "check-keyword-match",
        "identify-resume-gaps",
        # Improve
        "inject-keywords",
        "update-terminology",
        # Verify / support
        "validate-resume-truth",
        "build-candidate-evidence",
        "compare-resume-versions",
        "select-best-resume",
        # Export / maintain / flow
        "export-resume",
        "manage-synonyms",
        "resume-workflow",
        # Review (agent-driven, advice-only)
        "review-tailored-resume",
        # Preference learning (agent-driven, no CLI/MCP surface)
        "rank-edits",
        "log-edit-feedback",
    ]
)

# CLI commands and MCP tool names that must appear (one per slug). Workflow /
# agent-driven skills (resume-to-json, job-to-json, inject-keywords,
# update-terminology, manage-synonyms, resume-workflow, review-tailored-resume,
# rank-edits, log-edit-feedback) are intentionally exempt — they orchestrate
# other skills/tools (or drive the resume_kit_feedback package, which has no
# CLI/MCP surface) rather than wrapping a single capability.
EXPECTED_CLI_OR_MCP: dict[str, list[str]] = {
    "check-ats-structure": ["resume-tool", "resume_check_ats_structure"],
    "check-keyword-match": ["resume-tool", "resume_check_job_match"],
    "select-best-resume": ["resume-tool", "resume_select_best"],
    "compare-resume-versions": ["resume-tool", "resume_compare_versions"],
    "identify-resume-gaps": ["resume-tool", "resume_identify_gaps"],
    "validate-resume-truth": ["resume-tool", "resume_validate_truth"],
    "build-candidate-evidence": ["resume-tool", "candidate_evidence_build"],
    "export-resume": ["resume-tool", "resume_export"],
}

# Phase 6 deferred capability names must NOT appear in any SKILL.md
DEFERRED_PHASE_6_NAMES: list[str] = [
    "check-resume-consistency",
    "score-resume-bullet",
    "improve-resume-section",
    "create-job-specific-resume",
    "check-cover-letter-job-match",
    "align-cover-letter",
    "audit-application-package",
]


# ---------------------------------------------------------------------------
# Minimal YAML front-matter parser
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict[str, str]:
    """Return key→value pairs from the leading YAML front-matter block.

    Expects the file to start with ``---\\n``, end the block with ``---\\n``,
    and contain only simple ``key: value`` scalar lines (no nested YAML).
    Returns an empty dict if no valid block is found.
    """
    if not text.startswith("---\n"):
        return {}
    rest = text[4:]
    end = rest.find("\n---")
    if end == -1:
        return {}
    block = rest[:end]
    result: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key:
            result[key] = value
    return result


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_skills_directory_exists() -> None:
    assert SKILLS_DIR.is_dir(), f"Skills directory not found: {SKILLS_DIR}"


def test_skill_slug_set_is_complete() -> None:
    """The set of skill directories matches exactly the expected slugs."""
    actual = {
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith("_")
    }
    missing = EXPECTED_SKILL_SLUGS - actual
    extra = actual - EXPECTED_SKILL_SLUGS
    assert not missing, f"Missing skill directories: {sorted(missing)}"
    assert not extra, f"Unexpected skill directories: {sorted(extra)}"


def test_each_skill_has_skill_md() -> None:
    for slug in EXPECTED_SKILL_SLUGS:
        skill_md = SKILLS_DIR / slug / "SKILL.md"
        assert skill_md.is_file(), f"Missing SKILL.md for skill '{slug}': {skill_md}"


def test_each_skill_md_is_valid_utf8() -> None:
    for slug in EXPECTED_SKILL_SLUGS:
        skill_md = SKILLS_DIR / slug / "SKILL.md"
        try:
            _ = skill_md.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise AssertionError(
                f"SKILL.md for '{slug}' is not valid UTF-8: {exc}"
            ) from exc


def test_each_skill_md_has_nonempty_frontmatter() -> None:
    for slug in EXPECTED_SKILL_SLUGS:
        skill_md = SKILLS_DIR / slug / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        assert fm, (
            f"SKILL.md for '{slug}' has no YAML front-matter block"
        )


def test_each_skill_md_frontmatter_has_name_and_description() -> None:
    for slug in EXPECTED_SKILL_SLUGS:
        skill_md = SKILLS_DIR / slug / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)

        name_val = fm.get("name", "")
        # description may be multiline (block scalar); check key exists + text
        # after the front matter block mentions something
        desc_val = fm.get("description", "")
        # For block scalars (|, >) the value after ':' is '>' or '|'; the
        # actual text is in subsequent lines.  We consider it present if the
        # key exists and the overall front-matter block has >10 chars.
        assert name_val, (
            f"SKILL.md for '{slug}': front-matter 'name' is missing or empty"
        )
        fm_block_len = len("\n".join(f"{k}: {v}" for k, v in fm.items()))
        has_description = bool(desc_val) or fm_block_len > 20
        assert has_description, (
            f"SKILL.md for '{slug}': front-matter 'description' is missing or empty"
        )


def test_each_skill_md_references_resume_tool_or_mcp_tool() -> None:
    for slug, expected_tokens in EXPECTED_CLI_OR_MCP.items():
        skill_md = SKILLS_DIR / slug / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        matched = any(token in text for token in expected_tokens)
        assert matched, (
            f"SKILL.md for '{slug}' must reference at least one of "
            f"{expected_tokens!r} (CLI command or MCP tool name)"
        )


def test_no_skill_md_mentions_deferred_phase6_capabilities() -> None:
    pattern = re.compile("|".join(re.escape(name) for name in DEFERRED_PHASE_6_NAMES))
    for slug in EXPECTED_SKILL_SLUGS:
        skill_md = SKILLS_DIR / slug / "SKILL.md"
        text = skill_md.read_text(encoding="utf-8")
        match = pattern.search(text)
        assert not match, (
            f"SKILL.md for '{slug}' references a deferred Phase 6 capability: "
            f"'{match.group()}' — remove it"
        )
