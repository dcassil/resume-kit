---
name: update-structure
description: >
  Produce the resume's `base` version: run the deterministic ATS structural
  check, then apply auto-safe structural fixes (strip PII/placeholders, normalize
  dates and formatting) behind the claim-preservation gate, writing
  <name>-base.json and pointing config's `base` at it. Deterministic, no LLM.
  Judgment/needs-input items are DEFERRED here and handled by the standard
  walkthrough (update-best-practices). Best run in a subagent.
---

# update-structure — original → base (structural check + auto-safe fix)

Baselining step 1 of the `original → base → standard` pipeline (RIT-I-0016). This
skill gets the resume itself structurally ATS-clean **before any job is
involved**. It drives the deterministic `build-base` capability, whose fix is
**auto-safe only** and gated by claim-preservation (no employer/title/degree/
skill claim may be added, dropped, or altered).

## Prerequisites

Run the shared **Prerequisites gate** — [`../_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** an active **`original` `ResumeDocument` JSON** — the
  `active_resume` pointer in `resume-kit/config.json`.
- **Does NOT need a job.** Baselining is job-independent.
- **If the resume JSON is missing** (no `active_resume`, or a raw PDF/DOCX):
  **STOP** and run **parse-resume** first.

## What it does

1. **Structural check.** Run the deterministic resume-only structural check
   (reuse **check-structure**) and present the `AtsStructureReport`
   (`section_completeness` + `recommendations`).
2. **Auto-safe base fix.** Run `build-base` (mode `auto`): it strips PII and
   placeholder text, normalizes dates/formatting, applies only deterministic,
   truth-preserving fixes, enforces the **claim-preservation gate**, writes
   `resume-kit/resumes/<name>-base.json`, and records the `base` pointer.
3. **Report applied vs deferred.** Show which fixes were `applied` and which were
   `deferred` (judgment / needs-input items). Deferred items are NOT fixed here —
   they are carried into the standard walkthrough (**update-best-practices**).

## How to invoke

**CLI**

```
resume-tool check-structure --resume <original.json> [--output {json,text,md}]
resume-tool build-base --root . --mode auto [--output {json,text,md}]
```

**MCP tools:** `resume_check_ats_structure`, `resume_build_base`.

## Modes (auto only — engine delta)

`build-base` is **auto-only by design** (RIT-T-0115): the fixes are deterministic
and truth-preserving, so there is no per-fix interactive approval at the `base`
stage. Interactive, human-in-the-loop handling of the **deferred** judgment items
happens in the next step, **update-best-practices** (the `standard` walkthrough).
Do not claim this skill applies interactive base fixes; it applies the auto-safe
set and defers the rest.

## Output (`BaseBuildResult`)

| Field | Type | Notes |
|---|---|---|
| `base_path` | string | Written `base` version, relative to `resume-kit/` |
| `applied` | list of strings | Auto-safe fixes applied |
| `deferred` | list of strings | Judgment/needs-input items handed to update-best-practices |

Report the applied and deferred lists verbatim, plus the structural report. State
that `base` is a truth-preserving structural pass — no wording judgment was made.

## Truth posture

- The claim-preservation gate is a HARD GATE: if it fails, `build-base` refuses
  and this indicates a bug, not user data — surface the failure, do not patch.
- Never present a deferred judgment item as if it were fixed.

## Notes / follow-up

- **AC#6 deferral (RIT-T-0120):** when the RIT-I-0017 "what the ATS sees" report
  (RIT-T-0109) lands, this skill should surface *that* single report instead of a
  standalone `AtsStructureReport`, to avoid a second ATS view. Until then it uses
  the deterministic `check-structure` report.
