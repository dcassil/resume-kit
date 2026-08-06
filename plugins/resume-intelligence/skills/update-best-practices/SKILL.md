---
name: update-best-practices
description: >
  Produce the resume's `standard` version from `base`: run the best-practices
  score, auto-apply the truthful auto_suggestible rewrites, elicit the user's
  real facts for needs_user_input items, and write <name>-standard.json behind
  the claim-preservation gate — then point config's `standard` at it. Truth-gated,
  no fabrication. Best run in a subagent.
---

# update-best-practices — base → standard (best-practices pass)

Baselining step 3 of `original → base → standard` (RIT-I-0016). Turns the
best-practices findings from **check-best-practices** into the `standard` version:
auto_suggestible rewrites are applied deterministically, and needs_user_input
items are resolved by **asking the user for the real fact** — never by inventing
one. Drives the `build-standard` capability, which writes `<name>-standard.json`
behind the **claim-preservation gate** and sets the `standard` pointer that all
downstream tailoring then prefers.

## Prerequisites

Run the shared **Prerequisites gate** — [`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required inputs:** a **`base` `ResumeDocument` JSON** (run **update-structure**
  first; falls back to the active original if no `base`), and the
  **best-practices report** from **check-best-practices**.
- **Does NOT need a job.** The standard pass is job-independent.
- **If no `base` exists:** run **update-structure** first.

## The walkthrough

1. **Score.** Run **check-best-practices** on `base` to get the findings, split
   into `auto_suggestible` and `needs_user_input`.
2. **Elicit facts for needs_user_input items.** For each such finding, show its
   `elicitation_prompt` and ask the user for the real fact (e.g. an actual
   metric). Collect answers into an **answers map keyed by the finding key**
   (`resume_kit_scoring.finding_key`). If the user cannot supply a fact, leave
   that finding unanswered — it will be reported as `deferred`, never fabricated.
3. **Build `standard`.** Call `build-standard` with the answers map. It applies
   the `auto_suggestible` rewrites plus the user-supplied answers, enforces the
   **claim-preservation gate** (the wording pass may reword but must not add,
   drop, or alter an employer/title/degree/skill claim), writes
   `resume-kit/resumes/<name>-standard.json`, and records the `standard` pointer.
4. **Report.** Show `applied` (edits made) and `deferred` (needs_user_input
   findings left unanswered). Optionally record a user's declined suggestion via
   **learn-change** so future runs weight it.

## How to invoke

**CLI**

```
resume-tool analyze-best-practices --resume <base.json>          # via check-best-practices
resume-tool build-standard --root . --answers <answers.json>     # answers: {finding_key: "real rewrite"}
```

**MCP tools:** `resume_analyze_best_practices`, `resume_build_standard` (pass
`answers` as an object mapping finding keys to strings).

## Output (`StandardBuildResult`)

| Field | Type | Notes |
|---|---|---|
| `standard_path` | string | Written `standard` version, relative to `resume-kit/` |
| `applied` | list of strings | Best-practices edits applied (auto + answered) |
| `deferred` | list of strings | needs_user_input findings left unanswered |

## Truth posture

- **Never fabricate a fact** to resolve a needs_user_input item. No metric, no
  rewrite — report it deferred.
- The claim-preservation gate is a HARD GATE: if `build-standard` refuses, surface
  the failure; do not patch around it.
- Only auto-apply the `auto_suggestible` rewrites the analyzer produced; do not
  invent additional edits.

## Notes / follow-up

- **Engine delta (RIT-T-0120 vs AC#3):** the delivered `build-standard` is a
  **batch, claim-preservation-gated write** (analyze → apply auto edits + answers
  → gate → write), not a per-item RIT-I-0015 edit-session walkthrough. The
  "walkthrough" here is the *answer-elicitation* loop in step 2; the application
  itself is the single gated build. A future task could route each item through
  the review-edits orchestrator for per-item accept/reject if that granularity is
  wanted.
