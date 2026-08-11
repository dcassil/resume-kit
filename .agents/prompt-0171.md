# Task: RIT-T-0171 — Flow 2 `ingest-job`

You are an implementing agent in the resume-kit Python uv workspace. You WRITE SKILLS + TESTS ONLY
(no new engine code expected). Repo root is your CWD (a git worktree). Read `.metis/code-index.md`
before exploring.

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`, `--reinstall`, or the full test suite.** You MAY run a single scoped
  `uv run --no-sync pytest plugins/resume-intelligence/tests/` to sanity-check the slug test IF quick.
- **No ruff/mypy config edits, no `# type: ignore`/`cast`/`Any` escape hatches.** No fabrication.

## Context (already committed)
- T1 (RIT-T-0169): durable full-resume learning seed substrate.
- T2 (RIT-T-0170): Flow 1 `prepare-base-resume` skill exists at
  `plugins/resume-intelligence/skills/prepare-base-resume/SKILL.md`; the seed capability is now on
  CLI `seed-full-resume-evidence` / MCP `resume_seed_full_resume_evidence` / API.
Study the existing skills for house style, especially:
- `plugins/resume-intelligence/skills/parse-job/SKILL.md`
- `plugins/resume-intelligence/skills/seed-terminology/SKILL.md`
- `plugins/resume-intelligence/skills/learn-terminology/SKILL.md`
- `plugins/resume-intelligence/skills/update-refine/SKILL.md` (frontmatter + section conventions)
- `plugins/resume-intelligence/skills/_shared/prerequisites.md` (the shared gate)

## Objective
Create the standalone **`ingest-job`** flow (Flow 2). It ASSUMES `prepare-base-resume` (Flow 1) has
run at least once and uses the prepared resume + learning base to parse ONE job and grow terminology
learning BEFORE any tailoring checks. It is safe to run repeatedly for multiple jobs.

## Deliverable A — the `ingest-job` skill
Create `plugins/resume-intelligence/skills/ingest-job/SKILL.md`, matching house style:
- YAML frontmatter: `name: ingest-job` and a folded `description:` (`>`) stating it parses a job and
  grows terminology learning against an existing prepared-resume learning base, is safe to run
  repeatedly, and assumes Flow 1 has run. End with "Best run in a subagent."
- "## Prerequisites": run the shared gate `[../_shared/prerequisites.md](../_shared/prerequisites.md)`.
  Gate explicitly on an **active prepared resume (`refine`/canonical) or a recorded override PLUS
  learning state from Flow 1** — i.e. do not run before Flow 1.
- "## The walkthrough": compose existing primitives ONLY —
  1. `parse-job` (faithful job → JobDescription JSON; do NOT add a new job faithfulness validator).
  2. `seed-terminology` / `learn-terminology` against the prepared resume + learning base: propose
     TRUTHFUL synonym pairs for JD keywords the resume already satisfies, each passing human
     confirmation + the existing truth gate before being written. Never auto-accept candidates.
  3. Create or GROW `resume-kit/learning/synonyms.json` — APPEND + DEDUPE, never drop prior aliases.
  4. Register `alias_file` through the code-owned `set-active --alias-file` path (never hand-edit
     config.json).
- Explain WHY this makes the very first tailoring score alias-aware.
- "## How to invoke": the relevant CLI/MCP names used by parse-job + seed-terminology + set-active.
- Note the spelling is `ingest-job`; user-facing docs may note it covers the originally requested
  "injest-job" concept.

## Deliverable B — register + document
- Add `"ingest-job"` to `EXPECTED_SKILL_SLUGS` in
  `plugins/resume-intelligence/tests/test_skill_markdown.py` (the slug set is asserted to EXACTLY
  match the skill dirs — you MUST add it). It is a workflow/agent-driven skill that orchestrates
  other skills, so it is EXEMPT from `EXPECTED_CLI_OR_MCP` (like parse-job/resume-workflow) — do NOT
  add it there.
- Update `plugins/resume-intelligence/README.md` to mention `ingest-job` as Flow 2 and the repeated
  path: run Flow 1 once, then Flow 2 many times.

## Scope guard
- Compose EXISTING skills/capabilities. Do NOT add engine code, a new job validator, or auto-accept
  synonyms. Do NOT run tailoring checks/updates (that is Flow 3, RIT-T-0172). Do NOT require
  rerunning Flow 1 per job.

When done: summarize the skill file added and the test/README edits.
