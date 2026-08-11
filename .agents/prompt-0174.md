# Task: RIT-T-0174 — Complete flow + docs/tests close-out

You are an implementing agent in the resume-kit Python uv workspace. You WRITE CODE + SKILLS + TESTS
ONLY. Repo root is your CWD (a git worktree). Read `.metis/code-index.md` if present.

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`, `--reinstall`, or the full suite.** You MAY run scoped tests:
  `uv run --no-sync pytest plugins/resume-intelligence/tests/` and your ONE new integration test
  file, IF quick. Never sync/reinstall.
- **No ruff/mypy config edits, no `# type: ignore`/`cast`/`Any` escape hatches.** No fabrication.

## Context (already committed — Flows 1-4 exist as skills)
- `prepare-base-resume` (Flow 1), `ingest-job` (Flow 2), `tailor-resume` (Flow 3),
  `finalize-resume` (Flow 4) all live under `plugins/resume-intelligence/skills/`.
- The existing end-to-end guide is `plugins/resume-intelligence/skills/resume-workflow/SKILL.md` — it
  currently contains the full per-stage detail (steps 1-11).
- Slug test: `plugins/resume-intelligence/tests/test_skill_markdown.py` (EXPECTED_SKILL_SLUGS is
  asserted to EXACTLY match the skill dirs).
- Integration tests live in `tests/integration/` and are driven through the REAL CLI transport,
  deterministic + offline. Study `tests/integration/test_baselining_lineage_integration.py` and
  `tests/integration/test_perfect_e2e.py` for the exact pattern (CliRunner, init → extract-text →
  set-active → build-base → ... assertions, socket-blocking for offline proof).

## Deliverable A — the complete flow (choose the cleaner option, document why)
Reconcile the end-to-end path so there is ONE source of truth for per-stage gates:
- Create `plugins/resume-intelligence/skills/complete-resume-flow/SKILL.md` that sequences the four
  smaller flows IN ORDER — `prepare-base-resume` → `ingest-job` → `tailor-resume` →
  `finalize-resume` — delegating per-stage gates to those flow skills (short; no divergent copy).
- Rewrite `resume-workflow/SKILL.md` so it NO LONGER duplicates per-stage gate detail: it should
  either become a thin pointer to `complete-resume-flow` + the four flows, or be retained as the
  composite guide that explicitly references them. The smaller flow skills are the source of truth.
  Do NOT leave two divergent copies of the stage gates.

## Deliverable B — slug test + docs
- Update `EXPECTED_SKILL_SLUGS` in `test_skill_markdown.py`: add `"complete-resume-flow"`. Keep
  `resume-workflow` if you retain that dir; if you instead remove/rename it, update the slug set
  accordingly so the EXACT-match test still passes. It is a workflow/orchestrating skill → EXEMPT
  from `EXPECTED_CLI_OR_MCP`.
- Update `plugins/resume-intelligence/README.md` AND the repo root `README.md` to document the split:
  the four flows + the complete flow, and the repeated-use path (Flow 1 ONCE per resume, then Flows
  2/3/4 MANY times per job).

## Deliverable C — the integration test (the key acceptance criterion)
Add `tests/integration/test_composable_flows_integration.py`, driven through the real CLI transport,
deterministic + offline (block sockets like the reference tests). It must prove:
1. **Flow 1 runs ONCE**: init → extract-text → validate-faithfulness → set-active → build-base →
   build-structure → analyze-best-practices → build-refine → seed-full-resume-evidence. Assert the
   prepared `refine` artifact exists, has NO custom section, and the learning/evidence file was
   seeded with full-resume content (incl. any custom/unmapped source content).
2. **Two different jobs each run Flow 2 + Flow 3 + Flow 4 WITHOUT rerunning Flow 1**: for each job,
   parse-job/set-active --job → seed-terminology (alias_file grows/dedupes) → check-keywords/
   check-gaps → (truth-gated update via the edit-session) → validate → re-check → fit → export.
   Assert the prepared resume + learning from Flow 1 are reused (not rebuilt), aliases append/dedupe
   across the two jobs, and each job produces a fit+exported artifact under the page gate.
Keep it offline and deterministic (no live provider). Reuse existing fixtures/helpers where possible.

## Deliverable D — surface parity note
If NO new code-owned composite command was added (this task is expected to be skill+test only,
reusing the surfaces T2 already added), confirm the primitive surfaces are unchanged. If you DO add
any composite command, it MUST have cross-surface parity tests in `tests/interface/test_surface_parity.py`.

## Scope guard
- Do NOT re-open Flows 1-4 behavior. Reconcile docs in ONE pass. Avoid two sources of truth for the
  flow order. Do NOT bundle unrelated refactors.

When done: summarize all files added/changed, whether you retained or replaced `resume-workflow`, and
the integration test's assertions.
