---
id: phase-0-upstream-audit-of-resume
level: initiative
title: "Phase 0 — Upstream Audit of Resume-Matcher"
short_code: "RIT-I-0001"
created_at: 2026-08-03T21:47:30.445109+00:00
updated_at: 2026-08-03T22:06:19.316455+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: NULL
initiative_id: phase-0-upstream-audit-of-resume
---

# Phase 0 — Upstream Audit of Resume-Matcher Initiative

## Context **[REQUIRED]**

The vision (RIT-V-0001) mandates building resume-kit by **selectively porting** proven behavior
from [Resume-Matcher](https://github.com/srbhr/Resume-Matcher) (Apache-2.0) rather than
rewriting from scratch. Every reuse claim in the vision is explicitly **preliminary** and must
be confirmed against real upstream code before any extraction begins.

Phase 0 is that confirmation step. It clones Resume-Matcher at a pinned commit, runs its backend
tests, reviews its license/attribution obligations, and produces a concrete **Reuse / Extract /
Adapt / Replace / New** matrix grounded in actual files, dependencies, and tests — not
assumptions. No product code is written in this phase. Its output is the evidence base that
de-risks Phases 1–6: without it, later extraction agents would be guessing at coupling, test
coverage, and licensing.

This is a pure research/documentation initiative. Its deliverables are the three `references/`
documents (`upstream-audit.md`, `reuse-inventory.md`, `attribution.md`) plus a pinned upstream
clone the extraction phases can read.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Clone Resume-Matcher at a single **pinned commit SHA** and record it everywhere reuse is claimed.
- Run the upstream backend test suite and record pass/fail, coverage gaps, and environmental needs.
- Review Apache-2.0 obligations and enumerate concrete attribution requirements for reused code.
- Inventory every relevant subsystem (parsing, schemas, scoring, diff engine, allowed-path gates,
  prompts, providers, export, tests, fixtures) with its files, imports, and tests.
- Produce a complete **Reuse/Extract/Adapt/Replace/New** classification matrix, one row per subsystem.
- For each candidate, identify whether it can run **without** the upstream database, config, or frontend.
- Record known quality risks and extraction blockers (e.g. `from app.*` coupling, LLM-required parsing).

**Non-Goals:**
- Writing any product code, packages, or interfaces (that is Phase 1+).
- Porting or refactoring upstream code (only reading/classifying/documenting).
- Redistributing Resume-Matcher — the clone lives in gitignored `./upstream/`, never in the product.
- Final scoring-algorithm decisions (Phase 3 audits scoring in depth; Phase 0 only flags it).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional Requirements:**
  - REQ-001: `references/upstream-audit.md` records the pinned commit SHA, clone instructions,
    backend test command + result, dependency summary, and modules that run without DB/frontend.
  - REQ-002: `references/reuse-inventory.md` contains one row per relevant subsystem with upstream
    file path, commit SHA, classification (Reuse/Extract/Adapt/Replace/New), dependencies, tests,
    and notes.
  - REQ-003: `references/attribution.md` lists every subsystem intended for reuse with upstream
    path, SHA, and the Apache-2.0 obligations that apply.
  - REQ-004: Every "Strong and reusable" and "Adapt" candidate named in the vision is either
    confirmed or explicitly refuted with a code-grounded reason.
- **Non-Functional Requirements:**
  - NFR-001: All findings are reproducible — a reader can re-run the exact clone + test commands.
  - NFR-002: No upstream code is committed to the product repo; the clone is gitignored.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
No runtime architecture is produced in Phase 0. The "architecture" here is the **evidence
pipeline**: pinned clone → test run → per-subsystem inspection → classification matrix →
attribution ledger. Findings feed directly into Phase 1's clean-core design.

### Component inventory (audit targets)
The audit must at minimum inspect these upstream subsystems, mapping each to a target
`packages/*` home and a classification:
- Text extraction (MarkItDown PDF/DOCX) → `document-parser`
- Resume/job Pydantic schemas → `schemas`
- LLM resume-to-JSON parsing + date restoration → `document-parser` + `llm`
- Job-keyword extraction + match scoring → `matching`
- Diff-based improvement (allowed/blocked paths, original-value verification, skill-add gates,
  rejection reporting) → `alignment` + `policy`
- LiteLLM provider integration + config → `llm`
- Prompts (tailoring, truthfulness, skill-target) → `alignment`
- PDF/DOCX export → `export`
- Upstream tests + fixtures → `tests/characterization`, `tests/fixtures`
- Web frontend, tracker/Kanban, SQLite/TinyDB persistence, API routers, settings UI → **Replace/Leave-behind**

## Detailed Design **[REQUIRED]**

Follow the vision's mandated extraction order for the *classification* step (steps 1–3 only in
Phase 0; steps 4–8 belong to later phases):
1. Locate equivalent behavior in Resume-Matcher.
2. Review the code and its tests.
3. Classify as Reuse / Extract / Adapt / Replace / New with a one-line justification.

The clone is created with `git clone` into `./upstream/` and immediately pinned:
`git -C upstream rev-parse HEAD` → record the SHA in all three reference docs. Upstream backend
tests are run in an isolated virtualenv per upstream instructions; results (command, pass/fail
counts, skips, env requirements) are captured verbatim into `upstream-audit.md`.

Each subsystem row must answer: (a) what does it do, (b) what does it import (esp. `app.*`
coupling), (c) is it tested upstream and how, (d) can it run without DB/frontend, (e) its
classification and target package.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

Phase 0 writes no product tests. Verification is **document completeness + reproducibility**:
- The pinned SHA resolves and the clone checks out at it.
- The recorded upstream test command runs and produces the recorded result.
- Every vision-named reuse candidate appears in the inventory with a classification.
- `attribution.md` covers every Reuse/Extract/Adapt row.
Reviewer (orchestrator) spot-checks 3 inventory rows against actual upstream files before the
initiative is marked complete.

## Alternatives Considered **[REQUIRED]**

- **Skip the audit, trust the vision's preliminary reuse list.** Rejected: the vision explicitly
  labels every reuse claim preliminary and requires Phase 0 confirmation; skipping compounds risk
  into every later extraction.
- **Fork Resume-Matcher and refactor in place.** Rejected by the vision — it forbids a permanent
  fork; the product must be a clean repo with selective, attributed extraction.
- **Add Resume-Matcher as a git subtree/submodule of the product now.** Rejected for Phase 0: a
  gitignored reference clone is sufficient and keeps the distributed product free of upstream code.
  A pinned-SHA subtree may be used transiently during a later extraction phase if needed.

## Implementation Plan **[REQUIRED]**

Decomposed into tasks by a codex agent (see child tasks). Expected task shape:
1. Clone + pin Resume-Matcher; record SHA; run backend tests; capture results → `upstream-audit.md`.
2. License/attribution review → Apache-2.0 obligations enumerated → `attribution.md` scaffold.
3. Subsystem inventory + Reuse/Extract/Adapt/Replace/New matrix → `reuse-inventory.md`.
4. Confirm/refute each vision-named candidate; flag `app.*` coupling and no-LLM feasibility.
5. Orchestrator review: spot-check rows, verify reproducibility, mark complete.

**Exit criteria:** all three reference docs populated and reproducible; pinned SHA recorded;
upstream tests run and results captured; every vision reuse candidate classified; orchestrator
spot-check passed.