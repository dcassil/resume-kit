---
id: phase-5-interfaces
level: initiative
title: "Phase 5 — Interfaces"
short_code: "RIT-I-0006"
created_at: 2026-08-04T05:06:20+00:00
updated_at: 2026-08-04T06:19:17.510096+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: XL
strategy_id: NULL
initiative_id: phase-5-interfaces
---

# Phase 5 — Interfaces Initiative

## Context **[REQUIRED]**

Phases 0–4 are complete and pushed: the toolkit has a full deterministic + controlled-alignment
**engine** across nine packages (`schemas`, `core`, `document-parser`, `matching`, `ats`,
`job-parser`, `policy`, `evidence`, `alignment`). Every capability is a plain, dependency-injected
Python function returning canonical schema models. What is missing is the **interface layer**: the
ways external callers reach that engine. The vision positions the toolkit as "a standalone agent
plugin, MCP server, CLI, API, and shared engine," and mandates that each interface is a **thin
adapter over the shared core** — "No business rule should exist only inside a CLI command, MCP
handler, agent skill, or API route" (vision, Core Skill and Interface Surface).

Phase 5 builds **all five surfaces** the vision lists, each adapting input/output and orchestrating
user interaction only:
1. **CLI** — `resume-tool` command suite (Typer) with JSON / text / Markdown output, no-LLM mode,
   strict mode, human-in-loop vs non-interactive modes, evidence/config inputs, and
   automation-friendly exit codes.
2. **MCP server** — stable-named tools with structured JSON in/out, stable error codes, warnings
   separate from errors, `requiresHumanInput`, questions, artifacts, and provenance (official
   `mcp` Python SDK).
3. **REST API** — endpoints as thin adapters over the same core (FastAPI + uvicorn), warnings/errors
   separated, human-input surfaced structurally.
4. **Agent plugin skills** — markdown skill definitions under `plugins/resume-intelligence/` that
   drive the CLI/MCP surface (mirrors the installed job-hunter plugin structure).
5. **`job-hunter` bridge** — a library adapter under `integrations/job-hunter/` exposing a stable
   callable surface so `job-hunter` consumes the toolkit without duplicating resume logic and
   without the toolkit ever touching job-hunter state (vision: the toolkit "returns structured
   results, reports, questions, provenance, and generated artifact references to the caller").

**Capability scope (decided with the human):** interfaces expose ONLY capabilities whose core engine
already exists after Phases 0–4, to honor "no business rule only in an interface." That surface:
- `extract-resume` → `document-parser` (`parse_resume_structured` provider path + `extract_resume_text_only` no-LLM)
- `extract-job-description` → `job-parser` (`parse_job_description` + `parse_job_description_text_only`)
- `check-resume-ats` → `ats` (`compute_ats_score`)
- `check-resume-job-match` → `matching` (`check_job_match`)
- `select-best-resume` → `matching` (`select_best`)
- `compare-resume-versions` → `matching` (`compare_versions`)
- `identify-resume-gaps` → `matching` (`analyze_keyword_gaps` → `KeywordGapAnalysis`)
- `align-resume` → `alignment` (`align_resume`, async)
- `validate-resume-truth` → `evidence` (`validate_resume_truth`)
- `build-candidate-evidence` → `evidence` (`build_candidate_evidence`)

NOT exposed this phase (no core engine yet — deferred to Phase 6 when their core lands):
`check-resume-consistency`, `score-resume-bullet`, `improve-resume-section`,
`create-job-specific-resume`, `check-cover-letter-job-match`, `align-cover-letter`,
`audit-application-package`. Their stable CLI/MCP/API names are reserved in the vision but NOT stubbed
here.

Grounding from `references/reuse-inventory.md` and the vision:
- Upstream provides no reusable interface layer: its FastAPI routers, MCP absence, and web-app config
  are all **Replace/New** (reuse-inventory "Replace" rows: existing API routers, API-key persistence,
  web config). So Phase 5 is almost entirely **New** code — thin adapters — not ports. No attribution
  rows are expected unless a specific helper is lifted.
- The core is already dependency-injected (vision Design: "Core matching and alignment services must
  receive dependencies explicitly so the same service is callable from agent plugin, MCP tool, CLI
  command, API endpoint, tests, local LLM provider, and hosted LLM provider"). Interfaces construct
  the provider/config and call the engine — they do not reach into `app.*` globals (upstream's
  `from app.llm import complete_json` anti-pattern is explicitly to be avoided).
- LLM is optional: every surface must support a **no-LLM / deterministic mode** (extraction text-only,
  ATS, matching, select, compare, gaps, truth-structural) with LLM paths (structured parse, job
  keyword extraction, alignment generation) opt-in and requiring an explicitly-configured provider.

Because no concrete LLM provider exists yet (deferred to a later phase per Phase 2/3 notes), Phase 5
interfaces are wired to accept a provider **injected/configured** but ship with the **no-LLM
deterministic paths fully working** and the LLM paths returning a clear "provider not configured"
structured error when invoked without one. This keeps interfaces honest and testable now.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- **Shared adapter substrate** in `core` (or a small new `packages/interfaces-support` if `core` is
  the wrong home — prefer extending `core`): a single place that maps any engine result into the
  canonical `InterfaceResponse` envelope (data + warnings + errors + `requiresHumanInput` + questions
  + provenance + artifacts) and a stable **error-code taxonomy** + **exit-code mapping** reused by ALL
  four transports, so no transport invents its own result shape. This is the load-bearing anti-duplication
  guarantee.
- **`packages/cli` (`resume_kit_cli`)**: a `resume-tool` Typer app exposing `extract`, `extract-job`,
  `check-ats`, `match`, `select`, `compare`, `identify-gaps`, `align`, `validate-truth`,
  `build-evidence`. Flags: `--output {json,text,md}`, `--no-llm`, `--strict`, `--human-in-loop /
  --non-interactive`, `--evidence <path>`, `--config <path>`. Deterministic exit codes (0 ok,
  non-zero per error class; a `requiresHumanInput` result has its own reserved code). A
  `[project.scripts]` `resume-tool` entry point.
- **`packages/mcp` (`resume_kit_mcp`)**: an MCP server (official `mcp` SDK) exposing the stable tool
  names (`resume_extract`, `job_description_extract`, `resume_check_ats`, `resume_check_job_match`,
  `resume_select_best`, `resume_compare_versions`, `resume_identify_gaps`, `resume_align`,
  `resume_validate_truth`, `candidate_evidence_build`) with structured JSON in/out, stable error codes,
  warnings separated from errors, `requiresHumanInput`, questions, provenance.
- **`packages/api` (`resume_kit_api`)**: a FastAPI app with REST endpoints for each exposed capability
  as thin adapters (sync endpoints; `align` runs the async engine). Pydantic request/response models
  reuse `resume_kit_schemas`; warnings/errors separated; `requiresHumanInput` surfaced. No persistence,
  no auth beyond a pluggable hook (out of scope), no async-job queue (vision lists it as longer-term).
- **`plugins/resume-intelligence/`**: markdown agent-skill definitions (one per exposed capability, or
  a coherent grouping) describing how an agent invokes the CLI/MCP surface — modeled on the installed
  job-hunter plugin skill format.
- **`integrations/job-hunter/`**: a library bridge module exposing a stable, typed callable surface
  (e.g. `analyze_resume_for_job`, `align_resume_for_job`, `validate_truth`, returning canonical
  results + artifact references) that `job-hunter` imports. It NEVER writes job-hunter state; it only
  returns structured results/questions/provenance.
- **Contract tests** for every surface (vision Testing: CLI contract tests, MCP contract tests, API
  contract tests): assert the same core input yields equivalent results across CLI/MCP/API (parity),
  correct exit/error codes, no-LLM mode works, and human-in-loop surfaces `requiresHumanInput` without
  advancing.
- Green toolchain: `ruff`, `mypy --strict`, `pytest` all pass; existing 963 tests stay green; new
  interface deps (typer, mcp, fastapi, httpx for tests) are isolated to their own packages' optional
  extras so `core`/engine packages stay dependency-light.

**Non-Goals:**
- Any NEW engine capability (consistency, bullet-score, section-improve, create-for-job, cover-letter,
  package-audit) — Phase 6. Interfaces expose only the existing engine.
- A concrete LLM provider (LiteLLM/OpenAI/Anthropic) — still deferred; interfaces accept an injected
  provider and run no-LLM paths now, returning a structured "provider not configured" error for LLM
  paths.
- Export/PDF/DOCX generation and artifact rendering (Phase 6) — the bridge returns artifact *references*
  where relevant but does not render documents.
- Hosted-API concerns: auth, multi-tenant, encryption-at-rest, async job queue, retention controls,
  usage metering (vision explicitly lists these as longer-term / out of MVP).
- Persistence / databases / API-key storage (upstream Replace rows) — configuration is passed in, not
  stored.
- Running an interactive terminal loop for human-in-loop — interfaces SURFACE `requiresHumanInput` +
  questions and accept a follow-up decision call; the CLI may implement a simple prompt loop, but the
  engine-facing contract stays request/response.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-501: A shared adapter/`InterfaceResponse` mapping + stable error-code taxonomy + exit-code map
    exists in `core` and is the ONLY result-shaping path; all four transports consume it (parity
    enforced by tests). No transport defines its own ad-hoc result/error shape.
  - REQ-502: `packages/cli` provides `resume-tool` with the 10 exposed commands, `--output
    {json,text,md}`, `--no-llm`, `--strict`, human-in-loop/non-interactive, evidence/config inputs, and
    deterministic exit codes; installable via `[project.scripts]`.
  - REQ-503: `packages/mcp` exposes the 10 stable-named MCP tools with structured JSON in/out, stable
    error codes, warnings≠errors, `requiresHumanInput`, questions, provenance.
  - REQ-504: `packages/api` exposes a REST endpoint per exposed capability as a thin FastAPI adapter,
    reusing `resume_kit_schemas` request/response models; `align` invokes the async engine correctly.
  - REQ-505: `plugins/resume-intelligence/` contains agent-skill markdown for the exposed capabilities,
    consistent with the repo's plugin skill conventions.
  - REQ-506: `integrations/job-hunter/` exposes a stable typed bridge that returns canonical results +
    questions + provenance + artifact references and never mutates job-hunter state.
  - REQ-507: Every surface supports a no-LLM deterministic path; LLM-requiring operations without a
    configured provider return a structured, stable "provider not configured" error (not a crash).
  - REQ-508: CLI/MCP/API produce EQUIVALENT results for the same input (cross-surface parity tests).
- **Non-Functional:**
  - NFR-501: `mypy --strict` passes for all new packages; `ruff` clean; existing 963 tests stay green.
  - NFR-502: No engine/business logic in any transport — transports only marshal I/O and call the
    engine (enforced by an import/architecture test where feasible: transports import the engine, the
    engine never imports a transport).
  - NFR-503: New heavy deps (typer, mcp, fastapi, uvicorn, httpx) live in the respective interface
    package's dependencies/optional extras ONLY; `schemas`/`core`/engine packages gain none of them.
  - NFR-504: No network/LLM in any test — LLM paths use the in-memory fake provider; API tests use an
    in-process test client; MCP tests call handlers directly or via an in-memory session.
  - NFR-505: The toolkit never logs or persists resume/job content in interface code (privacy posture).

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
Interfaces are a thin ring around the existing engine:
```
                 ┌──────── engine (Phases 0–4, unchanged) ────────┐
 CLI  ─┐         │ schemas · core · document-parser · job-parser  │
 MCP  ─┤         │ matching · ats · policy · evidence · alignment  │
 API  ─┼──calls──▶                                                 │
plugin ┤         └────────────────────────────────────────────────┘
bridge┘                     ▲ shared adapter substrate (in core):
                            │ InterfaceResponse mapping + error-code
                            │ taxonomy + exit-code map (REQ-501)
```
Dependency direction: transports → shared adapter substrate → engine. The engine NEVER imports a
transport (NFR-502). `core` gains the adapter substrate (no heavy deps). Each interface package
depends on the engine packages it needs plus its own transport dep. The plugin and bridge sit outside
`packages/` (under `plugins/` and `integrations/`) per the vision layout but consume the same core.
`align_resume` is async: MCP/API are async-native and await it; the CLI wraps with `asyncio.run`; the
bridge exposes both an async function and a sync convenience wrapper.

### Chosen stack (decided defaults; isolated per package)
- CLI: **Typer** (click-based; multi-command, testable via `CliRunner`).
- MCP: **official `mcp` Python SDK**.
- API: **FastAPI** + **uvicorn**; tests via `fastapi.testclient`/`httpx`.
- Plugin: markdown skill files (no runtime dep).
- Bridge: pure library (no transport dep) returning canonical schema types.

## Detailed Design **[REQUIRED]**

1. **Shared substrate first** (blocks everything): in `packages/core`, add the `InterfaceResponse`
   result-mapping helpers (engine result → envelope), a stable `ErrorCode` enum + error taxonomy, and
   an exit-code map. Unit-test the mapping. (If `InterfaceResponse` already exists in `core` from Phase
   1, extend it; do not duplicate.)
2. **Capability facade** (optional but recommended, blocks transports): a single in-process module that
   exposes each of the 10 capabilities as one uniform callable `(request-model, config, provider?) ->
   InterfaceResponse` by calling the underlying engine function and mapping via the substrate. All four
   transports call THIS, guaranteeing parity and keeping each transport trivial. Put it in `core` or a
   dedicated `packages/engine-facade`; decide during scaffolding (prefer `core` to limit package
   sprawl).
3. **CLI** (`packages/cli`): Typer app; one command per capability delegating to the facade; output
   formatters (json/text/md); exit-code mapping; `resume-tool` script entry. `CliRunner` contract tests.
4. **MCP** (`packages/mcp`): register the 10 tools over the facade; JSON schema per tool from the
   schema models; error/warty/questions mapping. Contract tests calling tool handlers with the fake
   provider.
5. **API** (`packages/api`): FastAPI routes over the facade; request/response models from schemas;
   `align` awaits the engine. `TestClient` contract tests.
6. **Plugin** (`plugins/resume-intelligence/`): skill markdown per capability describing invocation via
   CLI/MCP. Lint/structure check only.
7. **Bridge** (`integrations/job-hunter/`): typed functions returning canonical results + artifact refs;
   never touches job-hunter state; unit tests with fakes.
8. **Cross-surface parity tests**: same input through CLI/MCP/API/facade yields equivalent core data.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Contract tests** per surface: CLI (`CliRunner`: commands, `--output` variants, `--no-llm`, exit
  codes, `--strict`), MCP (tool handlers via fake provider: JSON in/out, error codes, `requiresHumanInput`),
  API (`TestClient`: status codes, response shape, warnings≠errors), bridge (typed returns, no state
  mutation).
- **Cross-surface parity tests**: assert equivalent core payload for the same input across surfaces
  (REQ-508) — the anti-duplication guarantee made executable.
- **No-LLM mode tests**: deterministic capabilities fully work with no provider; LLM capabilities
  return the stable "provider not configured" structured error (REQ-507).
- **Human-in-loop tests**: `align` with human-in-loop surfaces `requiresHumanInput` + questions and does
  not advance (reusing the Phase 4 review controller behavior through the interface).
- **Architecture test**: engine packages do not import any interface package (NFR-502); heavy transport
  deps do not appear in engine packages (NFR-503).
- All deterministic; no network/LLM — fake provider + in-process test clients. Existing 963 tests stay
  green.
- Gate (run `uv sync --all-packages` first): `uv run ruff check packages tests && uv run mypy
  packages/core packages/schemas packages/document-parser packages/matching packages/ats
  packages/job-parser packages/policy packages/evidence packages/alignment packages/cli packages/mcp
  packages/api && uv run pytest` (add integrations/plugin test paths as they land).

## Alternatives Considered **[REQUIRED]**

- **Let each transport call the engine directly (no shared facade/substrate).** Rejected: guarantees
  drift and violates "no business rule only in an interface" — result shaping, error codes, and
  human-input handling would be re-implemented three times. The shared substrate + facade is the
  mechanism that makes the vision's anti-duplication rule executable and testable (parity tests).
- **Defer the REST API and/or job-hunter bridge to a later slice.** Considered (a recommended option),
  but the human chose all five surfaces now; building them together over one facade is cheaper than
  re-deriving the adapter substrate later, and the surfaces are file-disjoint so they parallelize well.
- **Build a concrete LLM provider now so LLM paths are live.** Rejected/deferred: provider selection is
  a separate concern (later phase); interfaces are fully exercisable via the no-LLM paths + fake
  provider, and shipping a "provider not configured" structured error keeps the LLM surface honest.
- **Home the adapter substrate in a new `packages/interfaces` package.** Leaning against: `core` already
  owns `InterfaceResponse`/warnings/provenance; extending `core` avoids package sprawl and a new
  dependency edge. Final call made at scaffolding time, documented in the scaffold task.
- **argparse instead of Typer / stdlib http instead of FastAPI.** Rejected: Typer + FastAPI are the
  idiomatic, well-typed choices for a multi-command CLI and a REST surface, isolated to their packages
  so the engine stays lean (NFR-503).

## Implementation Plan **[REQUIRED]**

Decomposed by a codex agent into file-disjoint tasks (see child tasks). Expected shape:
1. Shared adapter substrate + error/exit-code taxonomy in `core` (+ tests) — lands first, blocks all.
2. Capability facade over the 10 engine functions (+ tests) — blocks transports.
3. Scaffold `packages/cli`, `packages/mcp`, `packages/api` (pyproject/entry points/deps) — after 1–2.
4. CLI commands + formatters + exit codes + contract tests.
5. MCP tools + contract tests.
6. API routes + contract tests.
7. Plugin skill markdown.
8. job-hunter bridge + tests.
9. Cross-surface parity tests + architecture/boundary tests + public exports (late wave).
Waves: substrate → facade → (scaffold) → CLI/MCP/API/bridge/plugin in parallel (file-disjoint) →
parity/boundary/exports last.

**Exit criteria:** all five surfaces expose the 10 built-engine capabilities as thin adapters over a
single shared facade/substrate; CLI installs as `resume-tool` with correct output formats + exit codes;
MCP server exposes the stable tool names; FastAPI app serves the endpoints; plugin skills + job-hunter
bridge present; no-LLM mode works and LLM-without-provider returns a stable structured error;
cross-surface parity + architecture (engine imports no transport) + no-heavy-deps-in-engine tests pass;
`ruff` + `mypy --strict` + `pytest` all green; existing 963 tests still pass.