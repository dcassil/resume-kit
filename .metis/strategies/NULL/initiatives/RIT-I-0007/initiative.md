---
id: phase-6-export-packaging
level: initiative
title: "Phase 6 — Export & Packaging"
short_code: "RIT-I-0007"
created_at: 2026-08-04T15:24:40+00:00
updated_at: 2026-08-04T16:08:58.435932+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: XL
strategy_id: NULL
initiative_id: phase-6-export-packaging
---

# Phase 6 — Export & Packaging Initiative

## Context **[REQUIRED]**

Phases 0–5 are complete and pushed: the toolkit has a full deterministic + controlled-alignment
engine (nine packages) and a complete interface layer (facade + CLI + MCP + REST API + plugin skills
+ job-hunter bridge) over it — 1971 tests green. Two things remain before it is a *shippable product*:
(1) it can analyze/align/validate resumes but cannot yet **export** a revised resume as a real
document artifact (PDF/DOCX), and (2) it is only usable in-place from the `uv` workspace — it is **not
pip-installable** (the root `resume-kit` wheel is a hollow shell pointing at a non-existent
`src/resume_kit`, and inter-package deps resolve only via local `[tool.uv.sources]` workspace, so
`pip install resume-kit` from an index yields nothing usable).

**Scope decided with the human: Export + Packaging first.** This initiative delivers artifact export
and makes the toolkit genuinely installable. The remaining vision Phase-6 features — cover-letter
match/align, application-package auditing, and the four deferred engine capabilities
(`check-resume-consistency`, `score-resume-bullet`, `improve-resume-section`,
`create-job-specific-resume`) — are explicitly deferred to a future **Phase 7** initiative and are NOT
built here. This keeps the phase focused on producing a working, installable product fastest.

**Rendering decisions (human):** PDF via **ReportLab** (pure Python, no system libraries, fully
deterministic — chosen over WeasyPrint's pango/cairo system deps and Playwright's heavy Chromium
runtime); DOCX via **python-docx** (already a workspace dev dependency from Phase 2). This satisfies
the vision's hard constraint: *"Do not require the Resume Matcher frontend to render a resume."*

**Packaging decision (human): umbrella `resume-kit` distribution, build-ready.** One installable
distribution that vendors ALL `resume_kit_*` import packages, with optional extras selecting the
surfaces: `pip install resume-kit` (engine + facade + export), `resume-kit[cli]` (+ Typer +
`resume-tool`), `resume-kit[mcp]`, `resume-kit[api]`, `resume-kit[all]`. I configure everything
(fix the root wheel to force-include every src tree, move third-party deps into base + extras, add
publish metadata + a CI publish workflow) but **do NOT run the actual upload** — Daniel runs the final
`twine`/trusted-publish with his PyPI credentials.

Grounding from `references/reuse-inventory.md` (pinned SHA `116f9cc`):
- **Replace→New — PDF/DOCX export** (`app/pdf.py`): the ONLY upstream export path renders the Next.js
  `/print/*` page via Playwright/Chromium. *Nothing is reusable beyond intent* (reuse-inventory
  landmine #4: "Export must be rebuilt; nothing reusable beyond intent"). So `packages/export` is
  entirely NEW code — no port, no attribution row.
- The **artifact substrate already exists** in `packages/core`: `ArtifactRef` (artifact_id /
  artifact_type / content_type / metadata) + the async `ArtifactStore` Protocol (`put`/`get`) +
  `FakeArtifactStore` (`resume_kit_core.testing`). Export writes rendered bytes through an injected
  `ArtifactStore` and returns an `ArtifactRef`; `InterfaceResponse` already carries an `artifacts`
  list. No new core substrate is needed — reuse it.
- The **interface pattern from Phase 5 is fixed**: a new `export-resume` capability is added to the
  `resume_kit_facade` REGISTRY (deterministic, no LLM provider needed) and every transport
  (CLI/MCP/API/plugin/bridge) picks it up as a thin adapter. No business rule may live in a transport
  (enforced by the existing boundary + parity tests, which must be extended to cover export).
- `ResumeDocument` (schemas) is the render input: `PersonalInfo` (name/title/email/phone/location/
  links), `summary`, `Experience[]` (title/company/years/description[]), `Education[]`, `Project[]`,
  `Additional` (skills/languages/certs/awards), `CustomSection[]`. Export renders these deterministically.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- **`packages/export` (`resume_kit_export`)** — a deterministic, no-LLM, no-frontend renderer:
  `render_pdf(resume: ResumeDocument, *, options) -> bytes` (ReportLab) and
  `render_docx(resume: ResumeDocument, *, options) -> bytes` (python-docx), plus a small
  format-dispatch (`ExportFormat` = pdf|docx) and a `render(resume, format, options) -> bytes`. Depends
  inward on `resume_kit_schemas` (+ `resume_kit_core` for options/types) ONLY; ReportLab + python-docx
  are `export`-local deps (never in the engine core). Output is byte-deterministic for identical input
  (fixed fonts/metadata; no timestamps embedded).
- **`export-resume` capability in the facade** — deterministic capability that renders a
  `ResumeDocument` to the requested format, writes the bytes through an injected `ArtifactStore`
  (default `FakeArtifactStore` in tests), and returns an `InterfaceResponse` whose `artifacts` carries
  the `ArtifactRef` (with content_type application/pdf or the DOCX MIME) — plus the raw bytes surfaced
  in a transport-appropriate way (base64 in JSON envelopes; a `--out <path>` file write in the CLI).
- **Artifact wiring through every surface** — CLI `resume-tool export` (writes the file to `--out` or
  stdout-safe base64; correct exit codes), an MCP `resume_export` tool, a POST `/export` API endpoint
  (returns the artifact bytes with the right content-type, or the envelope + base64), a plugin
  `export-resume` SKILL.md, and a bridge `export_resume` callable. All thin adapters over the facade
  capability; cross-surface parity + boundary tests extended to include export.
- **Umbrella packaging** — make `resume-kit` a real, installable distribution:
  - Fix root `[tool.hatch.build.targets.wheel]` to force-include EVERY `resume_kit_*` import package
    (from `packages/*/src/` and `integrations/*/src/`) into one wheel — replacing the hollow
    `src/resume_kit` target.
  - Move third-party runtime deps into the root `[project]`: base = pydantic + markitdown + pdfminer +
    python-docx + reportlab (engine + export); `[project.optional-dependencies]` extras `cli` (typer),
    `mcp` (mcp SDK), `api` (fastapi + uvicorn), `all` (union). Declare the `resume-tool` console script
    at the umbrella level (so `pip install resume-kit[cli]` yields the command).
  - Keep the per-package `pyproject.toml` files for local `uv` workspace dev, but ensure the SHIPPED
    umbrella wheel is self-contained (no unresolved workspace `resume-kit-*` Requires-Dist).
  - Add publish readiness: complete `[project]` metadata (classifiers, urls, license file, long
    description = README), a `LICENSE` (Apache-2.0) + `NOTICE`/attribution inclusion, and a **GitHub
    Actions publish workflow** using PyPI Trusted Publishing (OIDC) triggered on a version tag —
    configured but NOT executed. Document the manual `uv build` + `twine upload` fallback in the README.
- **Installability proof** — a test/CI step that builds the umbrella wheel and `pip install`s it into a
  CLEAN throwaway virtualenv (no workspace, no uv sources), then imports `resume_kit_facade` and runs
  `resume-tool --help` (with `[cli]`), proving the shipped artifact is self-contained.
- Green toolchain: `ruff`, `mypy --strict`, `pytest` all pass; existing 1971 tests stay green; export
  is deterministic and tested (byte-stable snapshots or structural PDF/DOCX assertions).

**Non-Goals:**
- Cover-letter match/align, application-package audit, and the four deferred engine capabilities
  (`check-resume-consistency`, `score-resume-bullet`, `improve-resume-section`,
  `create-job-specific-resume`) — deferred to **Phase 7**. Their stable names stay reserved, unstubbed.
- Actually publishing to PyPI (running `twine upload` / triggering the release) — configured and
  build-ready only; Daniel pushes the button with his credentials.
- Per-surface separate PyPI distributions (rejected in favor of the umbrella + extras).
- WeasyPrint / headless-Chromium rendering (rejected for system-dep / runtime weight).
- Pixel-faithful reproduction of the upstream frontend resume template — export produces a clean,
  correct, deterministic document, not a byte-match of the Next.js `/print` output.
- Async job queues, hosted-mode artifact storage backends (an S3/filesystem `ArtifactStore` impl is
  out of scope; the Protocol + fake suffice; a filesystem impl MAY be added only if a transport needs
  it to write `--out`, kept minimal).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-601: `packages/export` renders a `ResumeDocument` to PDF (ReportLab) and DOCX (python-docx)
    deterministically (identical input → identical bytes), no LLM, no frontend, no Chromium.
  - REQ-602: A new `export-resume` facade capability writes rendered bytes via an injected
    `ArtifactStore` and returns an `InterfaceResponse` carrying an `ArtifactRef` (correct content_type)
    + a way to obtain the bytes; it is deterministic and never requires an LLM provider.
  - REQ-603: CLI `resume-tool export` (with `--format {pdf,docx}`, `--out <path>`), an MCP
    `resume_export` tool, a POST `/export` API endpoint, a plugin `export-resume` skill, and a bridge
    `export_resume` callable — all thin adapters over the facade capability.
  - REQ-604: Cross-surface parity + interface-boundary tests are extended to include export
    (facade ≡ CLI ≡ MCP ≡ API for the artifact metadata; engine still imports no transport; reportlab/
    python-docx confined to `packages/export`).
  - REQ-605: The root `resume-kit` wheel force-includes every `resume_kit_*` import package and builds
    a self-contained wheel with base deps + `[cli]/[mcp]/[api]/[all]` extras and the `resume-tool`
    entry point; no unresolved `resume-kit-*` Requires-Dist in the shipped metadata.
  - REQ-606: A clean-venv install test builds the umbrella wheel, `pip install`s it (with `[cli]`) into
    a fresh virtualenv, and asserts `import resume_kit_facade` + `resume-tool --help` succeed.
  - REQ-607: Publish readiness — complete PyPI metadata (classifiers/urls/license/long-description),
    bundled `LICENSE` (Apache-2.0) + attribution, and a Trusted-Publishing GitHub Actions workflow
    gated on a version tag; NOT executed.
- **Non-Functional:**
  - NFR-601: `mypy --strict` clean for `packages/export` + all touched packages; `ruff` clean; existing
    1971 tests stay green.
  - NFR-602: reportlab + python-docx appear ONLY in `packages/export` deps and the umbrella base deps —
    never in engine packages (extend the boundary test's engine-only forbidden set).
  - NFR-603: No network/LLM in any test; export tests are deterministic (byte-stable or structural).
  - NFR-604: Export is a pure function of its inputs — no wall-clock timestamps, no random IDs, no
    locale-dependent formatting embedded in the output bytes.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
```
packages/export (resume_kit_export)   NEW — ReportLab PDF + python-docx DOCX renderers.
   depends on: resume_kit_schemas (+ resume_kit_core for options/types). NO LLM, NO transport.
   third-party: reportlab, python-docx (export-local only).
        ▲
        │ export-resume capability (deterministic) writes bytes via ArtifactStore → ArtifactRef
packages/facade  ── adds export-resume to REGISTRY, returns InterfaceResponse{artifacts:[ArtifactRef]}
        ▲
   CLI `export` · MCP `resume_export` · API POST `/export` · plugin skill · bridge export_resume
   (thin adapters; artifact bytes surfaced per transport: file/base64)

Packaging (root pyproject.toml): umbrella `resume-kit` force-includes all resume_kit_* src trees;
  base deps = engine + export; extras [cli]/[mcp]/[api]/[all]; console_script resume-tool;
  Trusted-Publishing CI workflow (build-ready, not run).
```
Artifact bytes: the facade stores via `ArtifactStore.put(...)` and returns the `ArtifactRef`; because
`InterfaceResponse.artifacts` carries refs (not raw bytes), each transport retrieves/returns bytes as
fits it — CLI writes `--out` file, API streams bytes with content-type, MCP/JSON base64-encodes. The
capability accepts an optional `ArtifactStore` (defaults to an in-memory store) so it is fully testable
with `FakeArtifactStore`.

## Detailed Design **[REQUIRED]**

1. Scaffold `packages/export` (pyproject with reportlab + python-docx, py.typed, tests). Define
   `ExportFormat` + `ExportOptions` (schemas or export-local), `render_pdf`, `render_docx`, `render`.
2. Implement the ReportLab PDF renderer (platypus flowables: header/personal-info, summary, experience
   with bullets, education, projects, skills/additional, custom sections) — deterministic (embedded
   standard fonts, no doc timestamps). Structural + byte-stability tests.
3. Implement the python-docx DOCX renderer (headings, paragraphs, bullet lists mirroring the PDF
   sections). Structural tests (open the produced docx, assert sections/paragraphs present).
4. Add the `export-resume` facade capability (deterministic; ArtifactStore-injected; returns
   ArtifactRef + bytes access) + facade tests (both formats, artifact metadata, no-provider path).
5. Wire transports: CLI `export` (--format/--out), MCP `resume_export`, API POST `/export`, plugin
   `export-resume` SKILL.md, bridge `export_resume`; per-surface contract tests + extend parity.
6. Packaging: rewrite root `[tool.hatch.build.targets.wheel]` to force-include every `resume_kit_*`
   src package; set base `[project.dependencies]` + `[project.optional-dependencies]` extras + the
   `resume-tool` console script + full metadata; add `LICENSE`/attribution to the sdist/wheel; add the
   Trusted-Publishing GitHub Actions workflow (`.github/workflows/publish.yml`, tag-gated, not run).
7. Clean-venv install test (REQ-606): build wheel, install into a throwaway venv, import + run
   `resume-tool --help`. Extend boundary tests (reportlab/python-docx engine-forbidden; export package
   allowed) and known-package set (+ export).

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Determinism/snapshot tests** for `render_pdf`/`render_docx`: identical input → identical bytes
  (or a stable structural fingerprint); assert content_type and that no wall-clock/random data leaks in.
- **Structural tests**: parse the produced DOCX (python-docx) and PDF (pdfminer, already a dep) back to
  text and assert every resume section/bullet is present and in order.
- **Facade capability tests**: pdf + docx happy paths via `FakeArtifactStore`; ArtifactRef metadata;
  deterministic (no provider); malformed/empty resume handled with a structured error not a crash.
- **Transport contract + parity**: CLI `export --out` writes a valid file + exit 0; API `/export`
  returns bytes with correct content-type; MCP `resume_export` returns the envelope + base64; parity of
  artifact metadata across facade/CLI/MCP/API.
- **Boundary**: reportlab/python-docx forbidden in engine packages (extend engine-only forbidden set);
  export package present in known-package set; engine still imports no transport.
- **Packaging/install (REQ-606)**: build the umbrella wheel, `pip install` into a clean venv, assert
  `import resume_kit_facade` and `resume-tool --help`. (May be marked to run in CI / gated behind an env
  flag if a clean-venv build is slow, but MUST be runnable locally.)
- All deterministic; no network/LLM. Existing 1971 tests stay green.
- Gate (uv sync --all-packages first): `uv run ruff check packages tests integrations plugins && uv run
  mypy <all engine+facade+transport packages> packages/export <bridge> && uv run pytest packages
  integrations plugins tests`.

## Alternatives Considered **[REQUIRED]**

- **WeasyPrint (HTML/CSS→PDF).** Rejected by the human: better typography but needs pango/cairo system
  libraries, which complicate a pure-`pip install` story and CI. ReportLab is pure-Python and fully
  deterministic.
- **Headless Chromium (Playwright).** Rejected: heaviest runtime (Chromium download), slower, and
  closest to the very frontend dependency the vision says to drop. ReportLab keeps export self-contained.
- **Per-surface PyPI distributions** (`resume-kit-cli`, `resume-kit-mcp`, …). Rejected by the human in
  favor of one umbrella `resume-kit` + extras: fewer names to own, one release, simpler install UX; the
  workspace packages remain for local dev but ship inside the one wheel.
- **Publish to PyPI now.** Deferred: build-ready + CI configured, but the actual upload needs Daniel's
  PyPI credentials/account, so the human owns the final push.
- **Include all remaining vision capabilities this phase** (cover-letter/audit/consistency/bullet/
  section/create-for-job). Deferred to Phase 7 (human decision) to ship an installable product first.
- **Return raw bytes in `InterfaceResponse`.** Rejected: the envelope is JSON-serialisable and carries
  `ArtifactRef`s, not blobs; bytes flow through the `ArtifactStore` + per-transport retrieval, keeping
  the envelope small and transport-agnostic (consistent with the Phase 5 substrate).

## Implementation Plan **[REQUIRED]**

Decomposed by a codex agent into file-disjoint tasks (see child tasks). Expected shape:
1. Scaffold `packages/export` + `ExportFormat`/`ExportOptions` — lands first.
2. ReportLab PDF renderer (+ determinism/structural tests).
3. python-docx DOCX renderer (+ structural tests).
4. `export-resume` facade capability (ArtifactStore-injected) + facade tests.
5. Transport adapters — CLI/MCP/API/plugin/bridge export (file-disjoint parallel) + contract tests.
6. Umbrella packaging: root wheel force-include + deps/extras + console script + metadata + LICENSE +
   publish workflow.
7. Clean-venv install test + extend boundary/parity/known-package tests + public exports (late wave).
Waves: scaffold → renderers (pdf/docx parallel) → facade capability → transports (parallel) →
packaging → install-proof + boundary/parity/exports.

**Exit criteria:** `packages/export` renders deterministic PDF (ReportLab) + DOCX (python-docx) with no
LLM/frontend; `export-resume` capability returns an `ArtifactRef` via an injected `ArtifactStore` and is
exposed by all five surfaces as thin adapters; cross-surface parity + boundary tests cover export
(reportlab/python-docx engine-forbidden); the root `resume-kit` builds a self-contained umbrella wheel
with `[cli]/[mcp]/[api]/[all]` extras + the `resume-tool` script; a clean-venv `pip install` of the
wheel imports `resume_kit_facade` and runs `resume-tool --help`; PyPI publish metadata + Trusted-
Publishing CI workflow are in place (not executed); `ruff` + `mypy --strict` + `pytest` all green;
existing 1971 tests still pass.