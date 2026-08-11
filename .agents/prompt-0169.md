# Task: RIT-T-0169 — Durable full-resume learning seed + no-custom handoff policy

You are an implementing agent in the resume-kit Python uv workspace. You WRITE CODE + TESTS ONLY.
Repo root is your current working directory (a git worktree). Read `.metis/code-index.md` before
exploring to find where things live.

## HARD CONSTRAINTS
- **Do NOT run any git commands.** No add/commit/branch/stash/checkout. The orchestrator owns git.
- **Do NOT run verification** (`uv sync`, `ruff`, `mypy`, `pytest` full-suite, packaging). The
  orchestrator runs the authoritative gate once you finish. You MAY read files and reason, and you
  may run a single narrowly-scoped `uv run --no-sync pytest <your new test file>` to sanity-check
  your own new test IF quick — but never `uv sync`/`--reinstall` and never the full suite.
- **Do NOT edit ESLint/mypy/ruff config or add per-line ignores / `# type: ignore` / casts through
  `Any` to dodge type errors.** Fix the underlying code. Pydantic v2 models.
- **No fabrication paths.** Learning/evidence records are PROOF inputs; they must never become a
  bypass for the truth/faithfulness/claim gates.

## Objective
Add the code-owned substrate Flow 1 (`prepare-base-resume`) needs: seed/merge durable
`CandidateEvidence` learning from the FULL source resume — including content that will NOT live in
the prepared resume JSON — and define the no-custom handoff policy so ambiguous/custom source content
is preserved in learning/evidence rather than guessed into a section or dropped.

## Acceptance criteria (all must hold)
1. Evidence extraction covers: summary, work headers, work bullets, projects, education, technical
   skills, certifications/training, languages, awards, AND source custom/unmapped content.
2. A code-owned merge writer persists full-resume evidence into `resume-kit/learning` or the active
   evidence file, with deterministic content-addressed IDs and idempotent dedupe.
3. Existing confirmed/user evidence is preserved on merge; rerunning does not delete or duplicate
   prior learning.
4. Source metadata is recorded well enough to trace an evidence item back to its source resume
   section (including which custom section it came from).
5. The shape/no-custom policy is explicit in code: prepared output omits custom holding sections,
   while ambiguous content is retained in learning/evidence and accounted for by the content
   ledger / provenance (nothing silently dropped).
6. Backward compatibility for existing `ResumeDocument.customSections` inputs remains intact — do
   NOT remove that schema field or break existing parser inputs.

## Technical approach (from the task doc — follow unless code says otherwise)
- Extend `resume_kit_evidence.build_candidate_evidence` (in `packages/evidence`) OR add a sibling
  extractor that accepts the source BuildDoc/ResumeDocument BEFORE the no-custom projection, so the
  full content (incl. custom sections) is captured.
- Add a facade-level persistence/merge helper/capability (in `packages/facade`) only if needed so
  skills never hand-edit JSON. Reuse `ProjectConfig.active_evidence` / `evidence_file` conventions.
- Keep content-addressed ID behavior stable; avoid order-based IDs (reruns must be idempotent).
- Reuse the existing `add-evidence` posture (packages/facade) for the merge writer.
- The shape pass + content ledger live in packages/scoring / packages/schemas (RIT-I-0019). Where
  the current shape pass would preserve unmapped content in a canonical `custom` bucket, the policy
  for Flow 1 is to route that content to evidence/learning instead — but the LEDGER must still
  account for the movement. Add the policy hook / helper; the actual Flow 1 skill wiring is a later
  task, so keep this task to the substrate + policy + tests.

## Tests to add
- Unit: evidence extraction coverage for every listed section incl. custom/unmapped content.
- Unit: deterministic content-addressed IDs + idempotent merge/dedupe (rerun = no dup, no loss).
- Unit: confirmed/user evidence preserved across merge.
- Unit/shape: unmapped/custom source content is preserved in learning and accounted for by the
  ledger when the prepared output omits custom sections (no silent drop).

## Scope guard
Substrate + policy + tests ONLY. Do NOT build the `prepare-base-resume` skill/runbook here (that is
RIT-T-0170). Do NOT touch job/tailoring/perfect/export code.

When done: leave a short summary of the files you added/changed and the new public
functions/capabilities, so the orchestrator can wire later flows to them.
