---
id: complete-composable-flows-gaps
level: initiative
title: "Complete composable-flows gaps: enforce page gate + realize no-custom Flow 1 + doc hygiene"
short_code: "RIT-I-0024"
created_at: 2026-08-11T15:00:00+00:00
updated_at: 2026-08-11T15:00:00+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: S
strategy_id: NULL
initiative_id: complete-composable-flows-gaps
---

# Complete composable-flows gaps Initiative

## Context **[REQUIRED]**

RIT-I-0023 split the monolithic `resume-workflow` into four composable flow skills plus a
complete-flow guide, on a learning-first architecture. A code-verified audit of that release against
`POST_TEST_ISSUES.2026-08-11.md` (performed on `main` @ `4a3f152`) found that RIT-I-0023 was
overwhelmingly a compose + skill-doc-restructure change. It shipped one real capability
(`seed-full-resume-evidence`) but left two **integrity gaps** where a flow skill now promises behavior
the code does not deliver, plus several doc-consistency findings it only partially reconciled:

1. **Page gate promised but not enforced.** `finalize-resume/SKILL.md` states export enforces a
   rendered `max_pages` hard gate, but the facade `export_resume` capability
   (`packages/facade/.../capabilities.py`) calls `render(...)` directly and never invokes the page
   gate that already exists in `packages/export/.../page_gate.py`. So over-length resumes still ship.
2. **No-custom Flow 1 output is dormant.** RIT-T-0169 added `CustomHandoffPolicy.OMIT_AND_LEDGER_TO_EVIDENCE`
   and `handoff_custom_section_to_evidence()`, but the default is `PRESERVE_IN_CANONICAL_CUSTOM` and the
   shipped Flow 1 `build-structure` path never passes OMIT. `parse-resume` still instructs emitting
   skills into BOTH `additional.technicalSkills` and `customSections`. The "no-custom, no duplicate
   Skills section" premise therefore does not take effect in practice.
3. **Doc hygiene debt.** The `standard→refine` rename is only applied at the new flow layer; single-
   purpose skills (`update-shape`, `update-structure`, `check-ats-view`, `check-structure`) still say
   `standard` and route to the deprecated `update-best-practices`. The `check-gaps` master-vs-evidence
   injectability contract is not reconciled with `tailor-resume`, and there is no shared config-pointer
   contract doc.

This initiative closes those specific gaps. It is deliberately small and surgical — it finishes what
RIT-I-0023 enabled rather than opening the larger post-tailoring state/path/fit engine cluster (that
is tracked separately as RIT-I-0025).

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Wire the existing page-budget gate into export across facade/CLI/MCP/API so a rendered over-length
  resume is a hard, auditable failure — with an explicit, recorded override path.
- Make the Flow 1 prepared output genuinely no-custom: exercise `OMIT_AND_LEDGER_TO_EVIDENCE` on the
  Flow 1 `build-structure` path and stop `parse-resume` from producing duplicate flat + custom skills.
- Reconcile the lagging skill docs so `refine` is the single terminal-stage vocabulary and the
  `check-gaps` proof contract matches `tailor-resume`.
- Keep every truth/faithfulness/claim/content-ledger gate intact; add tests that lock each fix.

**Non-Goals:**
- No canonical post-tailoring state model, first-class tailored/final pointers, job-scoped edit-session
  paths, or `fit`-consumes-tailored rework — that is RIT-I-0025.
- No alias-growth hardening, `add_skill` list contract, alias-aware required/preferred/placement
  scoring, or terminology-proposer precision work — pre-existing backlog untouched by RIT-I-0023.
- No new schema-breaking removal of `customSections` from parser inputs (only Flow 1 *output* is
  no-custom, as established in RIT-I-0023).
- No re-architecture of the export renderer; only the gate wiring around it.

## Requirements **[REQUIRED]**

### User Requirements
- A user who runs `finalize-resume` / export gets a hard failure (not a silent over-length PDF) when
  the rendered resume exceeds `max_pages`, and a clear, auditable way to override when they choose to.
- A user who runs `prepare-base-resume` (Flow 1) gets a prepared resume whose rendered output has no
  duplicate Skills section and no custom holding section, with the omitted content preserved in
  learning/evidence.
- A user (or agent) reading the single-purpose skill docs sees consistent `refine`-terminal vocabulary
  and a `check-gaps` proof contract that matches how `tailor-resume` actually injects.

### System Requirements
- **REQ-001: Enforce page gate in export.** `export_resume` (facade) must call the existing
  `packages/export` page-budget check before/around render and fail closed when the rendered document
  exceeds `max_pages`. The CLI/MCP/API export surfaces must surface this failure consistently.
- **REQ-002: Export override contract.** Provide an explicit, recorded override (e.g. an
  `--allow-over-length` flag / request field) so an intentional over-length export is auditable rather
  than silent. Default is fail-closed.
- **REQ-003: Flow 1 uses OMIT policy.** The Flow 1 `build-structure` path must pass
  `OMIT_AND_LEDGER_TO_EVIDENCE` so the prepared artifact omits canonical custom sections and the
  content ledger accounts for the movement to evidence.
- **REQ-004: No duplicate skills from parse-resume.** `parse-resume` guidance (and any capability it
  drives) must not emit the same skills into both `additional.technicalSkills` and `customSections`;
  choose one canonical representation so export renders a single Skills section.
- **REQ-005: standard→refine doc cleanup.** Remove stale `standard` / `update-best-practices` routing
  from `update-shape`, `update-structure`, `check-ats-view`, `check-structure`, and any other active
  skill doc; the deprecated alias may remain but must not be the routed target in active flows.
- **REQ-006: check-gaps proof contract reconciled.** Make the `check-gaps` and `tailor-resume` docs
  agree on what proves injectability (master resume and/or Flow 1 learning-evidence), so gap analysis
  is not described two different ways.
- **REQ-007: Shared config-pointer contract.** Add one shared doc (referenced by `_shared/prerequisites.md`)
  enumerating `active_resume`, `base_resume`, `structure_resume`, `refine_resume`, `final_resume`,
  `active_evidence`, `alias_file`, and lineage semantics.
- **REQ-008: Regression coverage.** Each code fix (REQ-001..004) lands with a test that fails before
  and passes after; doc fixes are covered by the plugin markdown/slug tests.

## Use Cases **[REQUIRED]**

### Use Case 1: Over-length export fails loudly
- **Actor**: Job seeker finalizing a tailored resume that renders to 3 pages with `max_pages=2`.
- **Scenario**: User runs `finalize-resume` → export. The page gate detects 3 rendered pages and fails
  closed with an actionable message; the user either trims (via `perfect`) or passes the explicit
  override.
- **Expected Outcome**: No silent over-length PDF; the doc claim in `finalize-resume` is now truthful.

### Use Case 2: Prepared resume has a single Skills section
- **Actor**: Candidate whose source resume has categorized skills.
- **Scenario**: User runs `prepare-base-resume`. Flow 1 uses OMIT, categorized/custom content is
  ledgered into evidence, and `parse-resume` no longer double-writes skills.
- **Expected Outcome**: The exported prepared resume shows one Skills section, shorter page count, and
  the omitted content is retrievable from learning/evidence.

### Use Case 3: Agent reads consistent docs
- **Actor**: An orchestrating agent following the skills.
- **Scenario**: The agent reads `update-shape`/`update-structure`/`check-gaps` and sees `refine`
  vocabulary and a single injectability-proof contract, with a shared config-pointer doc to resolve
  pointers.
- **Expected Outcome**: No misrouting to `standard`/`update-best-practices`; gap analysis runs with the
  correct proof surface.

## Detailed Design **[REQUIRED]**

**Page gate wiring (REQ-001/002).** Reuse `packages/export/.../page_gate.py` (`check_page_budget`).
In `export_resume` (facade `capabilities.py`), after resolving the resume and shape policy, render,
then run the page-budget check against the rendered artifact (or use the existing rendered-page count
the gate expects). If `blocked` and no override, return a hard error result (mirror how other hard
gates return a failed report + non-zero CLI exit). Add an `allow_over_length` request field / CLI flag
/ MCP+API param, default false; when true, record it in the result so the override is auditable.
Add/extend parity tests in `tests/interface/test_surface_parity.py` for the export surfaces.

**Flow 1 OMIT (REQ-003).** In the Flow 1 build-structure path (`resume_kit_facade` baseline builder →
`apply_shape_transforms(...)`), pass `custom_handoff_policy=CustomHandoffPolicy.OMIT_AND_LEDGER_TO_EVIDENCE`
when the call originates from `prepare-base-resume` / `build-structure` for Flow 1. Confirm the content
ledger records `PRESERVED_IN_EVIDENCE` for the moved content and that `content_ledger_ok` still holds.
Keep the default `PRESERVE_IN_CANONICAL_CUSTOM` for any non-Flow-1 caller to avoid behavior changes
elsewhere.

**Duplicate skills (REQ-004).** Decide the canonical representation (flat `additional.technicalSkills`
for ATS + categories rendered from a single source, NOT a duplicate `customSections` block). Update
`parse-resume/SKILL.md` guidance accordingly and, if a capability materializes both, dedupe before
render. Add a fixture test asserting the exported prepared resume has exactly one Skills section.

**Doc hygiene (REQ-005/006/007).** Mechanical doc edits to the four lagging skills; reconcile
`check-gaps` and `tailor-resume` proof language; add `_shared/config-pointers.md` and reference it from
`_shared/prerequisites.md`. Covered by existing plugin markdown/slug tests.

## Implementation Plan **[REQUIRED]**

1. **RIT-T-0175 — Wire page-budget gate into export + override contract (REQ-001/002/008).**
   Facade/CLI/MCP/API export enforces `check_page_budget`, fails closed, with an auditable override;
   parity + regression tests. Execution profile: `opus + medium`.
2. **RIT-T-0176 — Realize no-custom Flow 1 output (REQ-003/004/008).** Pass OMIT on the Flow 1
   build-structure path; reconcile `parse-resume` duplicate skills; ledger + single-Skills-section
   tests. Execution profile: `opus + medium`.
3. **RIT-T-0177 — standard→refine doc cleanup + deprecated-route removal (REQ-005).** Edit
   `update-shape`, `update-structure`, `check-ats-view`, `check-structure`; plugin markdown tests
   stay green. Execution profile: `sonnet + medium`.
4. **RIT-T-0178 — check-gaps proof contract + shared config-pointer doc (REQ-006/007).** Reconcile
   `check-gaps`/`tailor-resume`; add `_shared/config-pointers.md`; reference from prerequisites.
   Execution profile: `sonnet + medium`.

Tasks 1 and 2 touch disjoint code (export vs shape/parse) and can run in parallel; 3 and 4 are
doc-only and can run in parallel with each other and with 1/2.

## Cross-Initiative Coordination **[REQUIRED]**

- Directly completes [[RIT-I-0023]] (composable flows) — closes the integrity gaps that release left.
- Reuses [[RIT-I-0021]] `perfect`/export page-budget module (`check_page_budget`) — this initiative
  wires it into the export surface rather than reimplementing it.
- Reuses [[RIT-I-0019]] canonical `structure` pass + content ledger for the OMIT handoff.
- Hands off the larger post-tailoring state/path/fit engine cluster to [[RIT-I-0025]]; this initiative
  must NOT start that work.

## Testing Strategy **[REQUIRED]**

- Unit/interface: export page-gate fail-closed + override, across direct/CLI/MCP/API parity.
- Fixture: Flow 1 prepared output has no custom section and exactly one rendered Skills section; ledger
  records the evidence handoff; `content_ledger_ok` holds.
- Plugin markdown/slug tests cover the doc edits and any new `_shared` doc.
- Full ruff/mypy/pytest + plugin markdown tests green before completion.

## Status Updates **[REQUIRED]**

- 2026-08-11: COMPLETED & published (resume-kit 0.15.0 / plugin 1.8.0 / marketplace 0.10.0). All 4
  tasks landed (RIT-T-0175 page-gate wiring + `--allow-over-length`; RIT-T-0176 no-custom Flow 1 +
  parse-resume dedupe; RIT-T-0177 standard→refine doc cleanup; RIT-T-0178 check-gaps proof contract +
  `_shared/config-pointers.md`). Status backfilled after the fact (this section was left empty at
  close — a doc-hygiene miss).
- 2026-08-11: REQ-006 VERIFIED shipped (post-hoc audit). `check-gaps/SKILL.md` and `tailor-resume/SKILL.md`
  both carry an identical "Injectability proof contract" section (injectable = proved by a distinct
  master resume AND/OR confirmed Flow 1 `active_evidence`); `tailor-resume` explicitly states "Flow 3
  uses the same proof contract as check-gaps." `_shared/config-pointers.md` exists (REQ-007). The
  earlier "completed but exit_criteria_met:false + empty Status Updates" flag was doc hygiene only, not
  a real gap. Consequence: RIT-T-0181 / RIT-T-0184 should CROSS-LINK this shipped contract, not
  re-specify it.
