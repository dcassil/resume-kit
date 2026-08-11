# Task: RIT-T-0173 — Flow 4 `finalize-resume`

You are an implementing agent in the resume-kit Python uv workspace. You WRITE SKILLS + TESTS ONLY
(no new engine code). Repo root is your CWD (a git worktree). Read `.metis/code-index.md` if present,
else use the skill docs.

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`, `--reinstall`, or the full suite.** You MAY run a scoped
  `uv run --no-sync pytest plugins/resume-intelligence/tests/` to sanity-check the slug test.
- **No ruff/mypy config edits, no `# type: ignore`/`cast`/`Any`.** No fabrication.

## Context (already committed)
- Flows 1-3 exist: `prepare-base-resume`, `ingest-job`, `tailor-resume`.
- Existing capabilities you COMPOSE (do NOT reimplement):
  - `plugins/resume-intelligence/skills/perfect/SKILL.md` — job-aware budget/page fit
    (`resume-tool fit`, incl. `--auto-fit`); decision-driven trims with accounting.
  - `plugins/resume-intelligence/skills/export-resume/SKILL.md` — renders PDF/DOCX; enforces the
    rendered `max_pages` HARD gate (`resume-tool export` / `resume_export`).
- House style: `update-refine/SKILL.md`; shared gate `_shared/prerequisites.md`.

## Objective
Create the standalone **`finalize-resume`** flow (Flow 4): the final job-aware fit + export, run AFTER
a tailored resume exists (Flow 3). It OWNS `perfect` + `export-resume` and nothing else.

## Deliverable A — the `finalize-resume` skill
Create `plugins/resume-intelligence/skills/finalize-resume/SKILL.md`, matching house style:
- Frontmatter: `name: finalize-resume` + folded `description:` (`>`) stating it runs the final
  job-aware fit and export over a tailored resume, enforces the rendered page hard gate, and does no
  preparation/ingest/tailoring. End "Best run in a subagent."
- "## Prerequisites": run `[../_shared/prerequisites.md](../_shared/prerequisites.md)`. Gate on a
  **tailored resume JSON** and an **`active_job`**.
- "## The walkthrough":
  1. **`perfect`** — run `resume-tool fit` (decision-driven or explicit `--auto-fit`); preserve the
     explicit decision/accounting behavior for trims.
  2. **`export-resume`** — run AFTER perfect. Export enforces the rendered `max_pages` HARD gate;
     state explicitly that fit is NOT submission-ready until export passes (rendered output is
     authoritative; `perfect` may warn/fit but does not replace the export gate).
- "## How to invoke": the CLI/MCP names (`resume-tool fit`/`resume_build_perfect`,
  `resume-tool export`/`resume_export`).
- Explicit guardrails: this flow does NOT mutate master lineage
  (`original`/`base`/`structure`/`refine`) and does NOT run preparation, job ingest, or tailoring
  updates.

## Deliverable B — register + document
- Add `"finalize-resume"` to `EXPECTED_SKILL_SLUGS` in
  `plugins/resume-intelligence/tests/test_skill_markdown.py` (exact-match slug set — you MUST add
  it). It orchestrates existing skills → EXEMPT from `EXPECTED_CLI_OR_MCP` (do NOT add it there).
- Update `plugins/resume-intelligence/README.md` to document `finalize-resume` as Flow 4, runnable
  independently after delayed tailoring.

## Scope guard
- Compose EXISTING `perfect` + `export-resume`. Do NOT add engine code, do NOT run prep/ingest/tailor
  steps, do NOT touch `resume-workflow` (that reconciliation is T6). Keep the page hard gate in export.

When done: summarize the skill file added and the test/README edits.
