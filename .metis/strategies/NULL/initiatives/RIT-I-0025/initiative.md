---
id: post-tailoring-state-path-fit-model
level: initiative
title: "Canonical post-tailoring state/path model: first-class tailored/final pointers, job-scoped edit-session, fit-consumes-tailored"
short_code: "RIT-I-0025"
created_at: 2026-08-11T15:00:00+00:00
updated_at: 2026-08-11T15:00:00+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: post-tailoring-state-path-fit-model
---

# Canonical post-tailoring state/path model Initiative

> **STATUS: DISCOVERY / NOT DECOMPOSED.** Scaffolded from the RIT-I-0023 audit against
> `POST_TEST_ISSUES.2026-08-11.md`. This is the report's P0 cluster (its recommended fix order #1–2)
> and was an explicit non-goal of RIT-I-0023. It needs human review and a design phase before
> decomposition. Do NOT create tasks or begin implementation until Daniel reviews and approves the
> approach.

## Context **[REQUIRED]**

The post-test review found the highest-severity issues concentrated in write-path state and the
tailor → fit → export handoff. These are architectural, not doc-level, and RIT-I-0023 deliberately did
not touch them (it composed existing capabilities). The audit of `main` @ `4a3f152` confirmed they are
untouched. The core problems, as reported and to be re-verified during discovery:

- **No canonical post-tailoring state model.** Committed tailoring writes to
  `resume-kit/working/<stem>.tailored.json` but does not promote that file into the active version
  lineage. `fit` later re-resolves the baseline lineage (`refine → structure → base → original`) and
  can operate from the untailored baseline instead of the committed tailored resume — explaining fit
  hash drift and the observed baseline-pollution workaround.
- **Tailored/final outputs are not first-class config pointers.** `fit`, review, export, and
  validation cannot reliably consume the same intended resume without manually overwriting baseline
  lineage files.
- **Edit-session working paths are not job-scoped.** A single active `working/edit-session.json` plus a
  working path derived from the active resume NAME (not the job) means multiple jobs against one
  refined resume collide on the same tailored working file and trigger `working_resume_tampered`
  errors.
- **`fit` does not explicitly consume the committed tailored resume.** `fit --auto-fit` can re-read
  `refine` after tailoring and ignore/reject the committed working copy.

## Goals & Non-Goals **[REQUIRED]**

**Goals (provisional — to be refined in discovery/design):**
- Define ONE canonical post-tailoring state model and path convention that tailor, review, fit,
  validate, and export all consume.
- Make tailored and final outputs first-class, code-owned config pointers (e.g. `tailored_resume`,
  `final_resume`) in `ProjectConfig`, with a clear resolution order.
- Job-scope the edit-session working paths so concurrent jobs against one refined resume do not collide.
- Make `fit` consume the intended tailored input explicitly rather than re-resolving baseline lineage.

**Non-Goals (provisional):**
- Not the page-gate wiring, no-custom Flow 1 realization, or doc hygiene — those are [[RIT-I-0024]].
- No weakening of truth/faithfulness/claim/content-ledger gates.
- No renderer rewrite.

## Requirements **[REQUIRED]**

*To be elaborated during discovery/design. High-level candidates (each to be validated against current
code before acceptance):*
- A documented state/path contract for tailored and final resumes.
- First-class `ProjectConfig` pointers for tailored/final outputs with atomic, code-owned writes.
- Job-scoped edit-session/working-path derivation.
- `fit` input resolution that prefers the committed tailored resume.
- Migration/back-compat for existing projects that only have baseline lineage pointers.

## Use Cases **[REQUIRED]**

*To be elaborated during discovery. Seed scenarios:*
- A user tailors resume R for jobs A and B in the same project without the two runs colliding on one
  working file or triggering `working_resume_tampered`.
- A user tailors, walks away, and later runs `fit` + export; both operate on the committed tailored
  resume, not the untailored `refine` baseline.
- Fit/export/review/validate all report against the same intended resume with a stable hash.

## Detailed Design **[REQUIRED]**

*To be produced in the design phase after discovery. Must include: the chosen pointer names and
`ProjectConfig` schema changes; the resolution order across original/base/structure/refine/tailored/
final; the job-scoping key for edit-session/working paths; the `fit` input-resolution change; and a
migration path for existing projects. This section is intentionally left as a design placeholder — per
the human-in-the-loop rule, the design is a directional choice requiring Daniel's review before it is
written and decomposed.*

## Implementation Plan **[REQUIRED]**

*To be produced after design approval. Not decomposed yet — this initiative is in discovery. Likely
shape (indicative only): state/path contract + pointers → edit-session job-scoping → fit input
resolution → export/review/validate consumption → migration + e2e. Each will get a `Recommended Agent`
profile at decomposition time.*

## Cross-Initiative Coordination **[REQUIRED]**

- Successor to [[RIT-I-0023]] (composable flows) and [[RIT-I-0024]] (gap close-out); this initiative
  owns the deeper engine state model those two deliberately left alone.
- Interacts with [[RIT-I-0015]] edit-session orchestrator + hard write gate (must not fork it).
- Interacts with [[RIT-I-0021]] `perfect`/`fit` and [[RIT-I-0014]] code-owned `ProjectConfig` state
  contract (pointer additions extend that contract).

## Testing Strategy **[REQUIRED]**

*To be elaborated during design. Must ultimately include: multi-job no-collision integration coverage,
fit-consumes-tailored regression, pointer resolution/migration tests, and no regression to existing
truth/gate suites.*

## Status Updates **[REQUIRED]**

- 2026-08-11: Scaffolded in discovery from the RIT-I-0023 post-release audit. Awaiting Daniel's review
  before design + decomposition.
