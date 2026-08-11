# Task: RIT-T-0170 — Flow 1 `prepare-base-resume`

You are an implementing agent in the resume-kit Python uv workspace. You WRITE CODE + SKILLS + TESTS
ONLY. Repo root is your CWD (a git worktree). Read `.metis/code-index.md` before exploring.

## HARD CONSTRAINTS
- **Do NOT run git.** No add/commit/branch/stash/checkout. The orchestrator owns git.
- **Do NOT run `uv sync`, `--reinstall`, or the full test suite.** The orchestrator runs the
  authoritative gate. You MAY run a single narrowly-scoped `uv run --no-sync pytest <your new file>`
  to sanity-check IF quick; never sync/reinstall.
- **No mypy/ruff config edits, no `# type: ignore`, no `cast`/`Any` escape hatches.** Fix real code.
- **No fabrication.** Learning/evidence is proof input, never a truth-gate bypass.

## Context: what T1 (RIT-T-0169, already committed) gave you
T1 added the durable learning-seed substrate. Reuse it — do NOT re-implement:
- Facade capability registered under key `"seed-full-resume-evidence"` →
  `seed_full_resume_evidence_capability` in `packages/facade/src/resume_kit_facade/capabilities.py`
  (registry line ~1505). Request/Result: `SeedFullResumeEvidenceRequest` / `SeedFullResumeEvidenceResult`
  in `packages/facade/src/resume_kit_facade/models.py`, both exported from the facade `__init__`.
- Facade merge writer `merge_evidence_file(...)`; default learning file `learning/candidate-evidence.json`.
- `CustomHandoffPolicy.OMIT_AND_LEDGER_TO_EVIDENCE` in `resume_kit_scoring.shape_fix` (default stays
  `PRESERVE_IN_CANONICAL_CUSTOM`). Flow 1's prepared output uses the OMIT policy so the prepared
  resume has NO canonical custom section, while custom source content is ledgered as retained in
  evidence (never dropped).
- `EvidenceKind.SOURCE_CUSTOM`, `ContentFate.PRESERVED_IN_EVIDENCE`.

**The T1 capability is NOT yet wired to CLI/MCP/API.** You must surface it (below) so the skill can
invoke it and so surface parity holds (REQ-008).

## Deliverable A — surface `seed-full-resume-evidence` across CLI/MCP/API (with parity)
Follow the EXACT existing pattern used by `build-refine` / `resume_build_refine` / `POST /build-refine`:
- **CLI**: add a `seed-full-resume-evidence` command in
  `packages/cli/src/resume_kit_cli/app.py` (mirror `build_refine` at ~line 866: build the request,
  call the facade capability via `caps`, `_run(...)`).
- **MCP**: add `resume_seed_full_resume_evidence` in `packages/mcp/src/resume_kit_mcp/tools.py`
  (mirror `resume_build_refine` ~line 977; also add to the exported tool-name list ~line 109).
- **API**: add `POST /seed-full-resume-evidence` in `packages/api/src/resume_kit_api/routes.py`
  (~line 471 pattern) with a body model in `packages/api/src/resume_kit_api/models.py`.
- **Parity tests**: add a `SurfaceCase` to `tests/interface/test_surface_parity.py` so
  direct/CLI/MCP/API agree for this capability, matching how existing capabilities are covered.
- Keep the flag/param surface minimal: it operates on the active project root (`--root`), reads the
  active/source resume, merges into the learning evidence file, idempotent.

## Deliverable B — the `prepare-base-resume` skill
Create `plugins/resume-intelligence/skills/prepare-base-resume/SKILL.md`. Match the house style of
existing skills (see `plugins/resume-intelligence/skills/update-refine/SKILL.md`):
- YAML frontmatter with `name: prepare-base-resume` and a `description:` (folded `>` block) that
  states it prepares one resume WITHOUT needing a job, produces an ATS-ready no-custom canonical
  artifact, and seeds durable full-resume learning. End with "Best run in a subagent."
- A "## Prerequisites" section that runs the shared gate:
  `[../_shared/prerequisites.md](../_shared/prerequisites.md)`. Explicitly: **does NOT need a job**.
- A "## The walkthrough" that composes existing primitives in order:
  `parse-resume` → `update-structure` (build-base) → `update-shape` (build-structure, canonical
  no-custom) → `check-best-practices` → `update-refine` → optional `check-ats-view`, PLUS the new
  learning seed step (invoke `seed-full-resume-evidence`) placed so the FULL source resume content
  (incl. custom/unmapped) is captured before the no-custom projection removes it from the artifact.
- "## How to invoke" listing the new CLI + MCP names for the seed step.
- A truth-posture section: no-custom output must not silently drop ambiguous content — it is retained
  in learning; every edit still passes existing gates; no fabrication.
- Note it can be run for MULTIPLE resumes without clobbering unrelated learning/config pointers.

## Deliverable C — register + document the new skill slug
- Add `"prepare-base-resume"` to `EXPECTED_SKILL_SLUGS` in
  `plugins/resume-intelligence/tests/test_skill_markdown.py` (the slug-set test asserts an EXACT
  match — you MUST add it or the suite fails). Put it under a sensible group comment (e.g. a new
  "Flows" group).
- Update `plugins/resume-intelligence/README.md` to mention `prepare-base-resume` and that it is
  reusable BEFORE any job-specific work (Flow 1 of the composable flows).

## Scope guard
- Flow 1 is NOT job-aware. Do NOT add job parsing/tailoring/perfect/export here.
- Do NOT silently discard ambiguous source content to satisfy the no-custom requirement.
- Do NOT build Flow 2/3/4 or the complete flow (later tasks).
- Keep `refine` as the default downstream tailoring input after the flow completes.

When done: summarize the files added/changed, the new CLI/MCP/API names, and the skill slug, so the
orchestrator can gate and wire later flows.
