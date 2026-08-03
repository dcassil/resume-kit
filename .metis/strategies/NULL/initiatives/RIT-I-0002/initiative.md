---
id: phase-1-clean-core-canonical
level: initiative
title: "Phase 1 — Clean Core & Canonical Schemas"
short_code: "RIT-I-0002"
created_at: 2026-08-03T22:06:38.202864+00:00
updated_at: 2026-08-03T22:29:50.480735+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: phase-1-clean-core-canonical
---

# Phase 1 — Clean Core & Canonical Schemas Initiative

## Context **[REQUIRED]**

Phase 0 (RIT-I-0001) confirmed the reuse landscape against the pinned upstream Resume-Matcher
(SHA `116f9cc`). Key findings that shape this phase:
- Upstream coupling is lighter than the vision feared: core services import only
  `app.{llm,prompts,schemas,config}` — all invertible — and no core service touches the DB,
  models, or routers.
- `schemas/models.py` upstream **mixes domain models with HTTP DTOs**; we must split these.
- Structured resume parsing is **LLM-only** upstream (a no-LLM blocker to note, not solve here).

Phase 1 creates the clean foundation every later phase builds on: the `core` and `schemas`
packages. It defines the canonical Pydantic v2 models (`ResumeDocument`, `JobDescription`,
`CandidateEvidence`, `AnalysisReport`, `ChangeProposal`, diffs, provenance, warnings, artifacts,
interface responses), ports/adapts upstream schemas behind clean boundaries with characterization
tests, and defines the provider/storage `Protocol` interfaces (`StructuredCompletionProvider`,
etc.) that invert upstream's `app.*` dependencies. **No frontend, no persistence layer, no
business algorithms yet** — those are Phases 2–4.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Stand up the `uv` workspace with two installable packages: `packages/core`, `packages/schemas`.
- Define canonical, documented Pydantic v2 domain models separated from any transport/HTTP DTOs.
- Port or adapt upstream resume/job schemas into `schemas`, recording upstream path + SHA per the
  attribution ledger, protected by **characterization tests** proving behavior parity before change.
- Define the provider/storage interfaces (`Protocol`s) in `core` that later phases depend on —
  `StructuredCompletionProvider.complete_json`, an LLM-agnostic completion boundary, and a
  storage/artifact interface — so no core code imports a concrete provider.
- Green toolchain: `ruff`, `mypy --strict`, `pytest` all pass in CI-runnable form locally.

**Non-Goals:**
- Any matching, scoring, ATS, alignment, or export logic (Phases 3–6).
- LLM-based structured parsing implementation (Phase 2 adapts it behind the interface defined here).
- Persistence/database or web/API layers (explicitly excluded by the vision for Phase 1).
- CLI/MCP/API interfaces (Phase 5).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-101: `packages/core` and `packages/schemas` are `uv`-workspace members that import cleanly
    and export their public models/interfaces via `__init__`.
  - REQ-102: Canonical models exist for ResumeDocument, JobDescription, CandidateEvidence,
    AnalysisReport, ChangeProposal, Diff/ChangeSet, ClaimProvenance, Warning, Artifact, and a
    generic InterfaceResponse envelope — all Pydantic v2, fully typed, docstringed.
  - REQ-103: Domain models are separated from transport DTOs (upstream mixed them); no HTTP concern
    leaks into domain models.
  - REQ-104: `core` defines provider/storage `Protocol`s; a fake in-memory provider exists for tests.
  - REQ-105: Every ported/adapted schema records upstream path + SHA in `references/attribution.md`
    and carries a modified-source marker; a characterization test locks its behavior.
- **Non-Functional:**
  - NFR-101: `mypy --strict` passes for both packages; `ruff` clean.
  - NFR-102: No `app.*` (upstream) import appears anywhere in `packages/`.
  - NFR-103: No network/LLM call in any Phase 1 test (providers are faked).

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
Realizes the vision's engine-boundary diagram at the lowest layer:
```
packages/schemas  — canonical Pydantic domain models (+ ported upstream schemas, char-tested)
packages/core     — contracts: provider/storage Protocols, shared value types, error/warning types,
                    InterfaceResponse envelope. Depends on schemas; depends on NO concrete provider.
```
Later interface/algorithm packages depend inward on `core`+`schemas`; dependencies are injected as
`Protocol` implementations. This is the dependency-inversion substrate the whole product rests on.

### Key interfaces (illustrative)
```python
class StructuredCompletionProvider(Protocol):
    async def complete_json(self, request: StructuredCompletionRequest) -> dict[str, Any]: ...
```
The concrete LiteLLM-backed implementation lands in `packages/llm` in Phase 2; Phase 1 ships only
the Protocol plus an in-memory fake for tests.

## Detailed Design **[REQUIRED]**

Follow the vision's extraction order for every ported schema: locate upstream equivalent → review
→ classify (already done in `reuse-inventory.md`) → **port tests / add characterization tests
first** → extract behind clean module boundaries → only then adjust behavior. Concretely:
1. Scaffold `packages/core` and `packages/schemas` (pyproject, `__init__`, py.typed) as workspace members.
2. In `schemas`: author canonical domain models from scratch where classified New; port/adapt
   upstream Pydantic models (see `reuse-inventory.md` Reuse/Extract rows) with a characterization
   test per ported model asserting field parity and validation behavior.
3. In `core`: define provider/storage `Protocol`s, shared error/warning/provenance value types, and
   the `InterfaceResponse` envelope (data, warnings, errors, requiresHumanInput, questions,
   artifacts, provenance). Provide an in-memory fake provider under `tests/` or `core.testing`.
4. Wire ruff/mypy/pytest so both packages are covered; ensure `mypy --strict` green.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Unit tests** for every canonical model: construction, validation, serialization round-trip.
- **Characterization tests** for each ported upstream schema, written to pass against current
  upstream behavior BEFORE any modification (prove-it-fails when a field is intentionally broken).
- **Contract tests** for the fake provider proving it satisfies the `Protocol`.
- All deterministic; no network. Coverage target: every public model + interface exercised.

## Alternatives Considered **[REQUIRED]**

- **Single mega-package instead of core+schemas split.** Rejected: the vision mandates package
  separation of contracts vs schemas so interfaces can depend on the minimal surface; a mega-package
  reintroduces the coupling Phase 0 worked to invert.
- **Reuse upstream `schemas/models.py` as-is.** Rejected: it mixes domain + HTTP DTOs (Phase 0
  finding). We adapt it, splitting concerns, under characterization tests.
- **Define provider concretely (LiteLLM) now.** Rejected: violates dependency inversion and drags
  Phase 2 scope forward; Phase 1 ships only the Protocol + fake.

## Implementation Plan **[REQUIRED]**

Decomposed by a codex agent into file-disjoint tasks (see child tasks). Expected shape:
1. Workspace + package scaffolding (`packages/core`, `packages/schemas`, pyproject/py.typed, toolchain).
2. Canonical domain models in `schemas` (New ones) + unit tests.
3. Ported/adapted upstream schemas in `schemas` + characterization tests + attribution updates.
4. `core` contracts: provider/storage Protocols, error/warning/provenance types, InterfaceResponse
   envelope, in-memory fake provider + contract tests.
Waves ordered so scaffolding lands first, then models/contracts in parallel where file-disjoint.

**Exit criteria:** both packages import cleanly and are workspace members; all canonical models
defined, typed, documented, unit-tested; every ported schema characterization-tested and attributed;
provider/storage Protocols + fake provider in place; `ruff` + `mypy --strict` + `pytest` all green;
no `app.*` imports in `packages/`.