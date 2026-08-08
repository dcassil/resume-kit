---
name: update-refine
description: >
  Produce the resume's `refine` version from `structure`/`base`: run the
  best-practices score, auto-apply the truthful auto_suggestible rewrites,
  elicit the user's real facts for needs_user_input items, and write
  <name>-refine.json behind the claim-preservation gate — then point config's
  `refine` at it. Truth-gated, no fabrication. Best run in a subagent.
---

# update-refine — structure/base → refine (best-practices wording pass)

Formerly `update-best-practices` (the `standard` pass); renamed in RIT-I-0020.

Baselining step 3 of `original → base → structure → refine` (RIT-I-0016).
Turns the best-practices findings from **check-best-practices** into the
`refine` version: auto_suggestible rewrites are applied deterministically, and
needs_user_input items are resolved by **asking the user for the real fact** —
never by inventing one. Drives the `build-refine` capability, which writes
`<name>-refine.json` behind the **claim-preservation gate** and sets the
`refine` pointer that all downstream tailoring then prefers.

## Prerequisites

Run the shared **Prerequisites gate** — [`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required inputs:** a **`structure` `ResumeDocument` JSON** (run
  **update-shape** first; falls back to `base` only with a recorded shape-pass
  override), and the **best-practices report** from **check-best-practices**.
- **Does NOT need a job.** The refine pass is job-independent.
- **If no `structure` exists:** run **update-shape** first, or record the
  explicit override before using `base`.

## The walkthrough

1. **Score.** Run **check-best-practices** on `structure` (or the overridden
   `base`) to get the findings, split into `auto_suggestible` and
   `needs_user_input`.
2. **Elicit facts for needs_user_input items.** For each such finding, show its
   `elicitation_prompt` and ask the user for the real fact (e.g. an actual
   metric). Collect answers into an **answers map keyed by the finding key**
   (`resume_kit_scoring.finding_key`). If the user cannot supply a fact, leave
   that finding unanswered — it will be reported as `deferred`, never fabricated.
3. **Build `refine`.** Call `build-refine` with the answers map. It applies the
   `auto_suggestible` rewrites plus the user-supplied answers, enforces the
   **claim-preservation gate** (the wording pass may reword but must not add,
   drop, or alter an employer/title/degree/skill claim), writes
   `resume-kit/resumes/<name>-refine.json`, and records the `refine` pointer.
4. **Report.** Show `applied` (edits made) and `deferred` (needs_user_input
   findings left unanswered). Optionally record a user's declined suggestion via
   **learn-change** so future runs weight it.

## How to invoke

**CLI**

```
resume-tool analyze-best-practices --resume <structure.json>     # via check-best-practices
resume-tool build-refine --root . --answers <answers.json>       # answers: {finding_key: "real rewrite"}
```

**MCP tools:** `resume_analyze_best_practices`, `resume_build_refine` (pass
`answers` as an object mapping finding keys to strings).

## Output (`RefineBuildResult`)

| Field | Type | Notes |
|---|---|---|
| `refine_path` | string | Written `refine` version, relative to `resume-kit/` |
| `applied` | list of strings | Best-practices edits applied (auto + answered) |
| `deferred` | list of strings | needs_user_input findings left unanswered |

## Truth posture

- **Never fabricate a fact** to resolve a needs_user_input item. No metric, no
  rewrite — report it deferred.
- The claim-preservation gate is a HARD GATE: if `build-refine` refuses, surface
  the failure; do not patch around it.
- Only auto-apply the `auto_suggestible` rewrites the analyzer produced; do not
  invent additional edits.

## Notes / follow-up

- **Engine delta (RIT-T-0120 vs AC#3):** the delivered `build-refine` is a
  **batch, claim-preservation-gated write** (analyze → apply auto edits + answers
  → gate → write), not a per-item RIT-I-0015 edit-session walkthrough. The
  "walkthrough" here is the *answer-elicitation* loop in step 2; the application
  itself is the single gated build. A future task could route each item through
  the review-edits orchestrator for per-item accept/reject if that granularity is
  wanted.
