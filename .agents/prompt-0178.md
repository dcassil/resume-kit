# Task: RIT-T-0178 — check-gaps proof contract + shared config-pointer doc

You are an implementing agent in the resume-kit repo. You EDIT/ADD SKILL DOCS ONLY (markdown). Repo root
is your CWD (a git worktree).

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`/`--reinstall`/full suite.** You MAY run
  `uv run --no-sync pytest plugins/resume-intelligence/tests/` to confirm plugin tests stay green.
- Doc-only. Do NOT change Python, tests, or skill SLUGS.

## Problem
`check-gaps` requires a distinct MASTER resume to classify injectable vs non-injectable, while
`tailor-resume` (post-RIT-I-0023) leans on Flow 1 LEARNING-EVIDENCE. The two docs describe the proof
surface differently. Also, skills reference config pointer/lineage fields ad hoc with no single contract.

## Deliverable A — reconcile the proof contract (edit ONLY these two)
- `plugins/resume-intelligence/skills/check-gaps/SKILL.md`
- `plugins/resume-intelligence/skills/tailor-resume/SKILL.md`
Make them AGREE on what proves injectability: a distinct master resume AND/OR Flow 1 learning-evidence,
stated the same way in both, cross-linked. Be explicit about the degraded case: when NEITHER a master
nor learning-evidence is present, gap analysis falls back to keyword-only classification (clearly
labeled as such). Do not overstate — learning-evidence proves true additions but every edit still
passes the existing truth gates.

## Deliverable B — shared config-pointer contract doc
- Create `plugins/resume-intelligence/skills/_shared/config-pointers.md` enumerating and defining the
  code-owned pointers and lineage: `active_resume`, `base_resume`, `structure_resume`, `refine_resume`,
  `final_resume`, `active_evidence`, `alias_file`, plus the resolution/lineage order
  (`refine -> structure -> base -> original` for baseline; note tailored/final where applicable).
- **Ground every field name in the ACTUAL schema** — read
  `packages/facade/src/resume_kit_facade/project_config.py` (the `ProjectConfig` model) and use only
  fields that exist. If a field the report mentions (e.g. `final_resume`) does NOT exist in the schema,
  document what DOES exist and note the gap rather than inventing a field.
- Reference the new doc from `plugins/resume-intelligence/skills/_shared/prerequisites.md`.

## Acceptance criteria
- `check-gaps` and `tailor-resume` state one consistent injectability-proof contract incl. the degraded
  keyword-only fallback.
- `_shared/config-pointers.md` exists, matches the real `ProjectConfig` fields, and is referenced from
  `_shared/prerequisites.md`.
- `uv run --no-sync pytest plugins/resume-intelligence/tests/` passes (note: `_shared` is excluded from
  the slug set because the test skips dirs starting with `_`, so adding config-pointers.md is safe).

## Scope guard
- Doc-only. Do NOT edit `update-shape`, `update-structure`, `check-ats-view`, `check-structure`,
  `parse-resume`, or any code — those belong to other tasks/agents. Only the files named above.

When done: summarize the two reconciled docs and paste the pointer list you grounded against ProjectConfig.
