# Task: RIT-T-0177 — standard->refine doc cleanup + deprecated-route removal

You are an implementing agent in the resume-kit repo. You EDIT SKILL DOCS ONLY (markdown). Repo root is
your CWD (a git worktree).

## HARD CONSTRAINTS
- **Do NOT run git.** The orchestrator owns all git.
- **Do NOT run `uv sync`/`--reinstall`/full suite.** You MAY run
  `uv run --no-sync pytest plugins/resume-intelligence/tests/` to confirm plugin tests stay green.
- Do NOT change any Python, tests, or skill SLUGS. Doc-only.

## Problem
The `standard -> refine` rename (RIT-I-0020) is applied at the new flow layer but NOT in several
single-purpose skill docs, which still say `original -> base -> standard` and route deferred work to the
deprecated `update-best-practices`. This misroutes agents.

## Files to fix (verify with grep first)
- `plugins/resume-intelligence/skills/update-shape/SKILL.md`
- `plugins/resume-intelligence/skills/update-structure/SKILL.md`
- `plugins/resume-intelligence/skills/check-ats-view/SKILL.md`
- `plugins/resume-intelligence/skills/check-structure/SKILL.md`
Reference the CORRECT vocabulary already used in
`plugins/resume-intelligence/skills/update-refine/SKILL.md` and the flow skills
(`prepare-base-resume`, `complete-resume-flow`): the lineage is
`original -> base -> structure -> refine`.

## Steps
1. `grep -rn "standard\|update-best-practices" plugins/resume-intelligence/skills` to enumerate every
   stale occurrence.
2. Edit the four files (and any other ACTIVE skill doc the grep reveals) so:
   - The lineage reads `original -> base -> structure -> refine` (no stale `standard`).
   - Active-flow routing points at `update-refine`, NOT `update-best-practices`.
   - Any remaining mention of `update-best-practices` is ONLY an explicit "deprecated alias" note, not a
     routed target.
3. Re-grep to confirm only intentional, clearly-labeled back-compat mentions remain.

## Acceptance criteria
- No active skill doc routes to `update-best-practices` or describes the terminal stage as `standard`.
- The deprecated alias skill itself is left in place (do NOT delete it or change slugs).
- `uv run --no-sync pytest plugins/resume-intelligence/tests/` passes.

## Scope guard
- Doc-only. Do NOT touch code, tests, or the `standard`/`update-best-practices` deprecated alias's own
  existence. Do NOT edit files owned by other tasks: leave `parse-resume`, `check-gaps`, `tailor-resume`,
  and `_shared/*` ALONE (other agents own those).

When done: list the files edited and paste the final grep result proving only back-compat mentions remain.
