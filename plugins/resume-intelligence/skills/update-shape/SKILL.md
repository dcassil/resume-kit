---
name: update-shape
description: >
  Produce the resume's `structure` version from `base`: run deterministic shape
  analysis, apply auto-safe canonical section shaping behind the content-ledger
  and cross-section claim gates, surface ambiguous section mappings for the
  user's decision, and write <name>-structure.json only when the gates pass.
  Deterministic, non-destructive, no LLM, no wording changes, no budget/trim.
---

# update-shape — base → structure (canonical shape pass)

Baselining step 2 of the `original → base → structure → refine` pipeline
(RIT-I-0019). This skill gets the resume into the canonical resume shape after
the ATS structural `base` pass and before wording improvements. It drives the
deterministic `analyze-shape` and `build-structure` capabilities.

This is a structure-only pass. It is deterministic and non-destructive: it moves
already-present content into canonical sections when the engine can account for
every token, and it records lineage only after the content-ledger and
cross-section claim gates pass. It does **not** rewrite wording, does **not**
trim for budget, and does **not** remove content to make the resume shorter.
Ambiguous mappings are deferred for the user; never guess.

## Prerequisites

Run the shared **Prerequisites gate** —
[`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** a `base` resume JSON — the `base_resume` pointer in
  `resume-kit/config.json`.
- **Fallback input:** if `base` is absent but an `original` `active_resume` is
  present, the capability can analyze/build from the original; in the normal
  workflow, **STOP** and run **update-structure** first so `base` exists.
- **Does NOT need a job.** Shape canonicalization is job-independent.
- **If the resume JSON is missing** (no `base_resume` or `active_resume`, or a
  raw PDF/DOCX): **STOP** and run **parse-resume**, then **update-structure**.

## What it does

1. **Shape analysis.** Run the deterministic resume-only shape analyzer and show
   the `ShapeReport` (`summary` + `findings`). Use the active `base` JSON unless
   the caller explicitly supplies a different resume.
2. **Auto-safe canonicalization.** Run `build-structure`: it applies only the
   report-driven transforms the engine can account for, writes
   `resume-kit/resumes/<name>-structure.json` only when gates pass, and records
   the `structure` pointer plus `structure_derived_from` lineage.
3. **Surface deferred mappings.** If findings are deferred or the build returns
   `structure_path: null`, show the exact source sections and proposed targets
   from the report. Ask the user for explicit mappings before retrying. Do not
   infer a target from nearby content, job keywords, or personal preference.
4. **Report applied vs deferred.** Show `applied`, `deferred`, `ledger_ok`,
   `claims_ok`, and `structure_path`. If either gate fails, stop and report the
   failure; do not patch the JSON by hand.

## How to invoke

**CLI**

```bash
resume-tool analyze-shape \
  --resume resume-kit/resumes/<name>-base.json \
  --root . \
  [--output {json,text,md}]
resume-tool build-structure --root . [--answers <answers.json>] [--output {json,text,md}]
```

`answers.json` is an optional JSON object mapping source section display names to
canonical targets, for example:

```json
{
  "Open Source": "projects",
  "Speaking": "awards"
}
```

**MCP tools:** `resume_analyze_shape`, `resume_build_structure`.

## Output (`StructureBuildResult`)

| Field | Type | Notes |
|---|---|---|
| `structure_path` | string or null | Written `structure` path; null when gated. |
| `report` | `ShapeReport` | Read-only analyzer report used for the build |
| `ledger` | `ContentLedger` | Per-token accounting from the attempted transform |
| `ledger_ok` | boolean | Hard content-ledger gate result |
| `claims_ok` | boolean | Hard cross-section claim-preservation gate result |
| `applied` | list of strings | Shape findings applied |
| `deferred` | list of strings | Shape findings deferred for user decision |

Report these fields verbatim. State clearly that `structure` is a canonical
shape pass only: no wording judgment, no content trimming, no job tailoring.

## Truth posture

- The content-ledger and cross-section claim gates are HARD GATES: if either
  fails, `build-structure` does not write the structure artifact.
- Never remove content to satisfy the ledger. The pass must account for content,
  move it, dedupe it when the engine marks that safe, or defer it.
- Never guess ambiguous section mappings. Ask for a user decision and retry with
  an explicit `answers` map.
- Never present a deferred mapping as fixed.
