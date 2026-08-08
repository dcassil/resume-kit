---
id: standardize-refine-job-independent
level: initiative
title: "Standardize → refine: job-independent wording pass, reclassify destructive rules out, consume structure"
short_code: "RIT-I-0020"
created_at: 2026-08-07T18:24:38.789218+00:00
updated_at: 2026-08-08T00:00:00.000000+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: true
estimated_complexity: M
strategy_id: NULL
initiative_id: standardize-refine-job-independent
---

# Standardize → refine: job-independent wording pass, reclassify destructive rules out, consume structure Initiative

> **Reconstruction note (2026-08-08):** This initiative document and its six task documents were
> authored during execution but existed only as untracked files in the working tree and were
> removed by an unrelated `.metis` reconciliation before they were committed. The code for all
> six phases was already shipped and merged to `main`. This document (and the task docs) were
> reconstructed from the execution record and committed so the Metis system-of-record persists.
> All six phases are **completed**; see commits `0e47f6a` (P1), `863f7b6` (P2), `8484562` (P3),
> `fb4dd32` (P4), `1db1363` (P5), `48a4c26` (P6) and merges `b61d7cf` / `4c063ab`.

## Context **[REQUIRED]**

Second of three planned initiatives reshaping the resume pipeline (see [[RIT-I-0019]] for the
first). Target pipeline: `original → base → structure → refine → tailored → perfect/final`.

- **`base`** — ATS-safe cleanup ([[RIT-I-0016]]).
- **`structure`** — lossless canonicalization to the `jsonresume.md` schema ([[RIT-I-0019]]).
- **`refine`** — *this initiative*: the job-independent **wording-quality** pass (formerly `standardize`).
- **`tailored`** — job-specific keyword/terminology edits (existing).
- **`perfect`/`final`** — job-aware budgets/trims ([[RIT-I-0021]]).

Dogfooding exposed three problems with the old `build_standard` wording pass: (1) it carried
destructive/relevance rules that do not belong pre-job (`SUMMARY_TOO_LONG` = a length trim;
`FOUNDATIONAL_SKILL` = a relevance cut answerable only against a target job); (2) its real value —
quantification enrichment — was under-delivered (3-at-a-time surface + a vague batch tail); (3) its
mechanical auto-rewrites were too narrow to fire on clean resumes. The name "standardize" also
overlapped conceptually with the new `structure` pass. This initiative **renames the wording pass
to `refine`** and re-scopes it to *"job-independent wording quality: rewrite, enrich, quantify — in
place, never shorten-to-fit or cut-for-relevance."*

**Governing principle:** relevance/emphasis/angle → tailored (needs the job); budgets/caps/trimming
→ perfect (needs the finished tailored draft); truth-preserving wording quality → refine (needs
neither). `refine` must stay lossless of substantive content.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Rename the wording pass + lineage/artifact `standard → refine` (`build_standard → build_refine`,
  `<name>-standard.json → <name>-refine.json`, config `standard_resume → refine_resume`
  (+`refine_derived_from`), the skill, and all CLI/MCP/API/facade names) with a back-compat shim.
- Reclassify the two non-wording rules out of `refine`: `SUMMARY_TOO_LONG` → perfect/final;
  `FOUNDATIONAL_SKILL` → tailored. `refine` no longer emits or applies either.
- Confirm `refine`'s remaining rules are exactly the truth-preserving in-place wording rules
  (`MISSING_QUANTIFICATION`, `WEAK_OPENER`, `BUZZWORD`, `FIRST_PERSON_OPENER`).
- Fix quantification elicitation to cover the WHOLE resume (no 3-at-a-time sample / batch tail).
- Broaden mechanical rewrite rules (resolves [[RIT-T-0132]]).
- Consume `structure` as input: `build_refine` resolves `structure ?? base ?? original`.
- Preserve all existing guarantees (edit-session orchestration, hard write gate [[RIT-A-0001]],
  truth/faithfulness, feedback logging, cross-surface parity).

**Non-Goals:** structure/canonicalization ([[RIT-I-0019]]); budgets/trims ([[RIT-I-0021]]);
job-dependent wording (tailored); native canonical-schema consumption in refine; re-implementing
truth/faithfulness or the edit-session orchestrator.

## Requirements **[REQUIRED]**

- REQ-001: Rename with back-compat (read-alias for legacy `standard_resume`; resolution
  `refine ?? standard(legacy) ?? structure ?? base ?? original`).
- REQ-002: Remove `SUMMARY_TOO_LONG` from `refine` (detector preserved for perfect/final).
- REQ-003: Remove `FOUNDATIONAL_SKILL` from `refine` (detector preserved for tailored).
- REQ-004: Confirm/gate the remaining rule set; guard test that no length/relevance/budget rule
  is active in `refine`.
- REQ-005: Non-destructiveness invariant — content-preservation check (no bullet/skill/role/section
  dropped; no shorten-to-target).
- REQ-006: Whole-resume quantification elicitation (no cap, no `MISSING_QUANTIFICATION_MORE` tail).
- REQ-007: Broaden mechanical rewrite rules (`PASSIVE_OPENER`/`VAGUE_IMPACT`/`DUTY_PATTERN`).
- REQ-008: Input resolution `structure ?? base ?? original`.
- REQ-009: Surfaces + skill + workflow parity under the `refine` names; deprecation aliases for old.
- REQ-010: Migration + docs + version bump; E2E `structure → refine`.
- NFRs: determinism, truth/non-destructiveness (hard gates), backward compatibility, surface parity.

## Architecture **[REQUIRED]**

No new package. Re-scopes/renames the wording analyzer/apply in `resume-kit-scoring`
(`best_practices.py`), the facade `build_standard` capability (`baseline.py`), the surfaces, and
the skill. Removes two rules (relocating detectors), broadens the mechanical set, fixes the
quantification loop, consumes `structure`, with back-compat read-aliases.

## Detailed Design / Testing / Coordination **[REQUIRED]**

See the six task documents (RIT-T-0141/0143/0144/0145/0146/0147). Coordinated with [[RIT-I-0019]]
(structure substrate — landed first) and [[RIT-I-0021]] (perfect/final — landed before Phases 4-6;
consumes the relocated `SUMMARY_TOO_LONG` length-budget finding). Adopts the [[RIT-I-0018]] severity
taxonomy; reuses the [[RIT-I-0015]] edit-session orchestrator + hard write gate ([[RIT-A-0001]]) and
the [[RIT-A-0005]] skill lexicon. Resolves backlog [[RIT-T-0132]].

## Implementation Plan **[REQUIRED]**

- **Phase 1 ([[RIT-T-0141]])** — Rule reclassification + non-destructiveness guard. *(opus + high)* — DONE.
- **Phase 2 ([[RIT-T-0143]])** — Whole-resume quantification elicitation. *(opus + medium)* — DONE.
- **Phase 3 ([[RIT-T-0144]])** — Broaden mechanical rewrite rules (resolves [[RIT-T-0132]]). *(opus + medium)* — DONE.
- **Phase 4 ([[RIT-T-0145]])** — Rename + back-compat + config lineage + input resolution. *(opus + high)* — DONE.
- **Phase 5 ([[RIT-T-0146]])** — Surfaces + skill + workflow + deprecation aliases. *(opus + medium)* — DONE.
- **Phase 6 ([[RIT-T-0147]])** — E2E `structure → refine` + migration + docs + version bump. *(opus + medium)* — DONE.

**Outcome:** shipped to `main` (merges `b61d7cf`, `4c063ab`); resume-kit 0.12.0, plugin 1.5.0,
marketplace 0.7.0; full gate green (4035 passed / 1 skipped).
