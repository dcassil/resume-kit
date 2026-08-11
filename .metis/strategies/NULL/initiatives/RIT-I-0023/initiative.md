---
id: composable-resume-flows-learning-first
level: initiative
title: "Composable resume flows: prepare base, ingest job, tailor, finalize, and complete"
short_code: "RIT-I-0023"
created_at: 2026-08-11T13:49:59+00:00
updated_at: 2026-08-11T13:49:59+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: NULL
initiative_id: composable-resume-flows-learning-first
---

# Composable resume flows: prepare base, ingest job, tailor, finalize, and complete Initiative

## Context **[REQUIRED]**

The current `resume-workflow` guide is one large end-to-end runbook. Internally it already has the right
stage boundaries:

```
parse resume -> base -> structure -> refine -> parse job -> seed terminology -> tailor -> perfect -> export
```

But those boundaries are not expressed as independent user-facing flows. That makes users rerun or mentally
step through resume preparation even when they only want to prepare one or more base resumes, build learning
from several jobs, tailor multiple times from a prepared resume, or finalize a tailored resume later.

This initiative splits the workflow into four distinct flows plus one composite flow:

1. `prepare-base-resume` — parse and prepare a resume once, seed durable learning from the full base resume,
   and produce an ATS-ready canonical resume structure with no custom sections in the prepared output.
2. `ingest-job` — parse one job and grow terminology learning, assuming at least one prepared resume /
   learning base exists.
3. `tailor-resume` — run job-specific checks, truthful keyword/terminology updates, validation, re-checks,
   and optional missing-requirement interview.
4. `finalize-resume` — run `perfect` and `export-resume`, with the rendered `max_pages` hard gate.
5. `complete-resume-flow` — call flows 1-4 in order for the existing end-to-end path.

The architectural shift is learning-first. Flow 1 should seed durable learning/evidence with the full resume
content, including experience, skills, certifications, projects, education, and content that does not map
cleanly into the ideal canonical resume structure. Once that learning base exists, later flows can rely on
durable evidence/learning records instead of carrying every possible detail in the resume JSON.

Important scope constraint: this initiative should **not** globally remove backward compatibility for
`ResumeDocument.customSections` or existing parser inputs. "No custom sections" means the **prepared Flow 1
output** should be an opinionated canonical structure without custom holding sections; ambiguous or unmapped
source content is preserved in learning/evidence, not guessed into a resume section and not dropped.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Add four independent flow skills plus one complete-flow guide so users can run the stages independently.
- Make `prepare-base-resume` usable on one or many resumes without requiring a job.
- Persist full-resume learning/evidence during Flow 1, including material facts already retained in the
  prepared resume and facts that are intentionally left out of the no-custom canonical output.
- Keep Flow 2 reusable for pre-seeding / deepening learning across multiple jobs.
- Allow the common repeated path: run Flow 1 once, then run Flow 2, Flow 3, and optionally Flow 4 many times.
- Keep truth/faithfulness gates and the existing single-purpose skills/capabilities; compose instead of
  replacing them with a new monolith.
- Preserve existing primitive capability surfaces unless a thin composite surface is explicitly useful for
  code-owned state writes or tests.

**Non-Goals:**
- No rewrite of the parser, matcher, edit-session orchestrator, feedback stack, or export renderer.
- No weakening of faithfulness, claim-preservation, truth, content-ledger, or page gates.
- No direct hand-editing of `resume-kit/config.json` or learning files from skills; code-owned writers own
  machine-readable state.
- No global schema-breaking removal of `customSections` compatibility from existing BuildDoc/ResumeDocument
  inputs.
- No automatic fabrication from learning data. Learning expands proof; updates still pass existing gates.

## Requirements **[REQUIRED]**

### User Requirements
- A user can run `prepare-base-resume` by itself to prepare one or multiple source resumes before any job is
  selected.
- A user can run `ingest-job` by itself to parse jobs and grow terminology learning against an existing
  prepared-resume learning base.
- A user can run `tailor-resume` repeatedly for different jobs without rerunning resume preparation.
- A user can run `finalize-resume` separately after tailoring, including delayed final fit/export.
- A user can still run a complete flow that performs all four stages in order.

### System Requirements
- **REQ-001: Flow 1 durable learning seed.** Add or extend a code-owned writer that merges full-resume
  `CandidateEvidence` into `resume-kit/learning` / active evidence. It must dedupe deterministically and
  preserve existing user-confirmed evidence.
- **REQ-002: Full-resume evidence coverage.** The seed includes summary, work headers, work bullets, projects,
  education, skills, certifications, languages, awards, and source custom/unmapped content.
- **REQ-003: Flow 1 no-custom prepared output.** The prepared resume artifact uses the ideal canonical
  structure without custom sections. Ambiguous content that cannot be cleanly mapped is preserved in learning
  with source metadata instead of being guessed into the resume JSON.
- **REQ-004: Flow 2 learning-aware job ingest.** `ingest-job` parses the job and runs `seed-terminology` /
  `learn-terminology` against the prepared resume and learning base, creating or growing
  `learning/synonyms.json` and registering `alias_file`.
- **REQ-005: Flow 3 tailoring split.** `tailor-resume` starts from prepared `refine`/canonical output plus the
  active job; runs keyword/gap checks, terminology/keyword updates through edit-session, validation, re-checks,
  and the optional missing-requirement interview branch.
- **REQ-006: Flow 4 finalization split.** `finalize-resume` runs `perfect` and `export-resume`; export remains
  the rendered `max_pages` hard gate.
- **REQ-007: Complete flow.** `complete-resume-flow` sequences flows 1-4 with the same gates and outputs, not a
  second divergent runbook.
- **REQ-008: Surface/test parity where code-owned composites exist.** If new facade/CLI/MCP/API composite
  commands are added, they must have parity tests. If the composite remains skill-only, primitive capability
  parity must remain unchanged and skill markdown tests must cover the new slugs.

## Use Cases **[REQUIRED]**

### Use Case 1: Prepare a resume once, tailor many times
- **Actor**: Job seeker with a master resume and several target jobs.
- **Scenario**: User runs `prepare-base-resume` on the master resume. It writes the prepared canonical resume
  and seeds learning/evidence. Later the user runs `ingest-job` + `tailor-resume` for each job without
  reparsing the resume.
- **Expected Outcome**: Preparation cost is paid once; later tailoring uses the prepared resume and durable
  evidence/learning.

### Use Case 2: Build a deeper learning base before tailoring
- **Actor**: User researching a role family before applying.
- **Scenario**: User runs `prepare-base-resume`, then `ingest-job` on several representative postings to grow
  terminology aliases and requirement memory before tailoring an actual application.
- **Expected Outcome**: Alias and learning data improve matching from the first actual tailoring run.

### Use Case 3: Keep ambiguous resume content without polluting the submitted JSON
- **Actor**: Candidate whose source resume has custom sections such as patents, publications, leadership, or
  domain highlights.
- **Scenario**: Flow 1 maps clean items into canonical sections. Content that does not cleanly map is saved as
  evidence/learning with source metadata, while the prepared resume JSON has no custom section payload.
- **Expected Outcome**: The output is clean and ATS-oriented, but later job-specific tailoring can still draw
  on truthfully grounded learning.

## Detailed Design **[REQUIRED]**

**Flow 1: `prepare-base-resume`.** Compose the existing parse and baselining stages:
`parse-resume -> update-structure/build-base -> update-shape/build-structure -> check-best-practices ->
update-refine -> check-ats-view`. Add the durable learning seed before/around shape canonicalization so
the source resume's full content is captured before ambiguous/custom content is removed from the prepared
artifact. The output is a prepared canonical/refine artifact and a merged evidence/learning file.

**Learning seed.** Reuse `CandidateEvidence` and the existing `resume_kit_evidence` extractor, but extend it
to cover all material sections, including custom/unmapped content. Persist via a code-owned merge writer,
similar in posture to `add-evidence`, not by hand-written skill JSON edits. IDs remain content-addressed so
reruns are stable and idempotent.

**No-custom prepared output.** Keep parser/input compatibility for `customSections`, but make the Flow 1
prepared output write only first-class canonical sections. Where the current shape pass would preserve
unmapped content in canonical `custom`, this flow routes that content to evidence/learning instead. The
content ledger must still account for the movement or preservation so nothing is silently lost.

**Flow 2: `ingest-job`.** Compose `parse-job` and `seed-terminology`. Gate on an existing prepared resume or
recorded override plus learning state. It should be safe to run repeatedly for different jobs, appending and
deduping synonyms rather than replacing prior learning.

**Flow 3: `tailor-resume`.** Compose the existing job-specific path: `check-keywords`, `check-gaps`,
`rank-changes` when useful, `update-keywords`, `update-terminology`, optional `review-resume`,
`validate-facts`, second scoring, and optional `interview-missing-job-description`. It should consume the
Flow 1 prepared output and learning/evidence, not the raw source resume.

**Flow 4: `finalize-resume`.** Compose `perfect` and `export-resume`; it should gate on a tailored resume and
active job. Export remains the final rendered page hard gate.

**Complete flow.** The existing `resume-workflow` should become or point to a complete-flow guide that simply
calls the four smaller flows in order. The smaller flows are the source of truth for per-stage gates.

## Implementation Plan **[REQUIRED]**

1. **RIT-T-0169 — Durable full-resume learning seed + no-custom handoff policy.** Extend evidence extraction
   and persistence so Flow 1 can seed all material resume content and route ambiguous/unmapped content into
   learning instead of the prepared resume JSON.
2. **RIT-T-0170 — Flow 1 `prepare-base-resume`.** Add the skill/runbook and any thin composite code needed
   to parse, baseline, seed learning, and emit the prepared no-custom output.
3. **RIT-T-0171 — Flow 2 `ingest-job`.** Add the skill/runbook for job parse + terminology seed/grow against
   prepared learning.
4. **RIT-T-0172 — Flow 3 `tailor-resume`.** Add the skill/runbook for job-specific checks, updates,
   validation, re-checks, and optional interview.
5. **RIT-T-0173 — Flow 4 `finalize-resume`.** Add the skill/runbook for `perfect` + export and verify hard
   gates.
6. **RIT-T-0174 — Complete flow + docs/tests close-out.** Reconcile `resume-workflow`, README, skill slug
   tests, and any cross-surface or integration tests for the complete sequence.

## Cross-Initiative Coordination **[REQUIRED]**

- Builds on [[RIT-I-0014]] deterministic ingest and code-owned `resume-kit/` state.
- Builds on [[RIT-I-0019]] canonical `structure` pass and content ledger.
- Builds on [[RIT-I-0020]] `refine` as the default tailoring input.
- Builds on [[RIT-I-0021]] `perfect` / export page gate.
- Builds on [[RIT-I-0022]] optional missing-requirement interview in the tailoring flow.
- Reuses [[RIT-I-0013]] learning/feedback posture and [[RIT-I-0015]] edit-session gate; it should not fork
  either.

## Testing Strategy **[REQUIRED]**

- Unit tests for evidence extraction coverage and deterministic merge/dedupe.
- Shape/ledger tests proving unmapped/custom content is preserved in learning and not silently dropped when
  the prepared output omits custom sections.
- Skill markdown tests for the new flow slugs and updated complete-flow guide.
- Integration test for running Flow 1 once, then Flow 2 + Flow 3 + Flow 4 repeatedly for two jobs without
  rerunning Flow 1.
- Existing ruff, mypy, and pytest gates remain required before completion.

## Status Updates **[REQUIRED]**

*To be added during implementation.*
