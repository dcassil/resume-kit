# Task: RIT-T-0172 — Flow 3 `tailor-resume`

You are an implementing agent in the resume-kit Python uv workspace. You WRITE SKILLS + TESTS ONLY
(no new engine code expected). Repo root is your CWD (a git worktree). Read `.metis/code-index.md`
before exploring (may be absent — then use the skill docs).

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`, `--reinstall`, or the full suite.** You MAY run a scoped
  `uv run --no-sync pytest plugins/resume-intelligence/tests/` to sanity-check the slug test.
- **No ruff/mypy config edits, no `# type: ignore`/`cast`/`Any`.** No fabrication. Learning/evidence
  is proof input, never a truth-gate bypass.

## Context (already committed)
- T1: durable full-resume learning seed. T2: Flow 1 `prepare-base-resume`. T3: Flow 2 `ingest-job`.
- The current end-to-end guide is `plugins/resume-intelligence/skills/resume-workflow/SKILL.md`.
  Its **steps 5–10 are the job-specific tailoring path** you will extract into this standalone flow.
- Shared apply runbook: `plugins/resume-intelligence/skills/_shared/apply-changes.md`
  (mode prompt → per-change decide → commit hard gate → validate-facts → re-score). REUSE it; do not
  duplicate its contents.
- House style reference: `plugins/resume-intelligence/skills/update-refine/SKILL.md`,
  `.../update-keywords/SKILL.md`, `.../interview-missing-job-description/SKILL.md`, and the shared
  gate `.../_shared/prerequisites.md`.

## Objective
Create the standalone **`tailor-resume`** flow (Flow 3): job-specific tailoring AFTER Flow 1 (prepared
resume + learning) and Flow 2 (active job + alias file). It consumes the prepared `refine`/canonical
output + learning/evidence, NOT the raw source resume. It writes a tailored working resume and
**does NOT run `perfect` or export** (that is Flow 4).

## Deliverable A — the `tailor-resume` skill
Create `plugins/resume-intelligence/skills/tailor-resume/SKILL.md`, matching house style:
- Frontmatter: `name: tailor-resume` + folded `description:` (`>`) stating it is job-specific
  tailoring over a prepared resume + active job + learning, truth-gated, and stops before perfect/
  export. End "Best run in a subagent."
- "## Prerequisites": run `[../_shared/prerequisites.md](../_shared/prerequisites.md)`. Gate on:
  a **prepared resume (`refine`/canonical output or recorded override)**, an **`active_job`**, and
  **available learning/evidence** from Flow 1.
- "## The walkthrough" — extract resume-workflow steps 5–10, composing existing primitives:
  1. **First scoring:** `check-keywords` + `check-gaps` (use `alias_file` when present).
  2. **Route truthful improvements** through `update-keywords` + `update-terminology`, optionally
     `rank-changes` first, all via the shared apply runbook
     [`../_shared/apply-changes.md`](../_shared/apply-changes.md). Direct JSON edits unsupported
     except through `review-edits reconcile`.
  3. **`validate-facts`** after committed changes.
  4. **Re-run scoring** (`check-keywords` + `check-gaps`) and report deltas.
  5. **Optional `review-resume`** (advice-only offer) and **optional
     `interview-missing-job-description`** when the second scoring stays below the configured
     `interview_threshold` or required coverage is incomplete.
- Make the Flow-1 dependency explicit: learning/evidence can PROVE true additions, but every edit
  still passes the existing gates (no ungated auto-insertion).
- "## How to invoke": name the CLI/MCP the sub-skills use.
- End with an explicit statement: this flow writes a tailored working resume and does NOT run
  `perfect` or `export` — those belong to Flow 4 `finalize-resume`.

## Deliverable B — register + document
- Add `"tailor-resume"` to `EXPECTED_SKILL_SLUGS` in
  `plugins/resume-intelligence/tests/test_skill_markdown.py` (exact-match slug set — you MUST add
  it). It is a workflow/agent-driven orchestrating skill → EXEMPT from `EXPECTED_CLI_OR_MCP` (do NOT
  add it there).
- Update `plugins/resume-intelligence/README.md` to document `tailor-resume` as Flow 3 (runnable
  repeatedly per job after Flow 1 + Flow 2, without rerunning resume preparation).

## Scope guard
- Compose EXISTING skills. Do NOT add engine code. Keep `perfect` and export OUT of this flow.
- Do NOT modify `resume-workflow` yet (the complete-flow reconciliation is T6, RIT-T-0174).
- Do NOT let learning evidence become ungated auto-insertion.

When done: summarize the skill file added and the test/README edits.
