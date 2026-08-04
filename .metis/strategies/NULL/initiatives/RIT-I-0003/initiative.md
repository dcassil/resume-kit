---
id: phase-2-document-extraction-parsing
level: initiative
title: "Phase 2 — Document Extraction & Parsing"
short_code: "RIT-I-0003"
created_at: 2026-08-03T23:30:00+00:00
updated_at: 2026-08-04T01:06:18.846496+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: phase-2-document-extraction-parsing
---

# Phase 2 — Document Extraction & Parsing Initiative

## Context **[REQUIRED]**

Phases 0–1 are complete and pushed. Phase 0 (RIT-I-0001) confirmed the reuse landscape against
pinned upstream Resume-Matcher (SHA `116f9cc`); Phase 1 (RIT-I-0002) stood up the clean `uv`
workspace with `packages/schemas` (`resume_kit_schemas`: canonical Pydantic v2 domain models,
domain split from transport DTOs) and `packages/core` (`resume_kit_core`:
`StructuredCompletionProvider`/`CompletionProvider` Protocols, `ArtifactStore`, error/warning
taxonomy, `InterfaceResponse[T]` envelope, in-memory fakes under `resume_kit_core.testing`).

Phase 2 builds the **document extraction & parsing** layer — the first algorithmic package —
on top of that substrate. It is the entry point of the whole pipeline: turning raw resume bytes
(PDF/DOCX/Markdown/plain text) into (a) deterministic extracted text and (b) an optional,
LLM-produced structured `ResumeDocument`, with confidence, warnings, and provenance attached.

Grounding from the Phase 0 reuse inventory (`references/reuse-inventory.md`), all relative to
`upstream/apps/backend/app/`:
- **Reuse — `services/parser.py:119` `parse_document(bytes, filename)`**: MarkItDown PDF/DOCX→Markdown
  extraction. Deterministic, no LLM, no DB. The only non-LLM half of the upstream parser. Confirmed
  strong reusable. Deps: `markitdown[docx]`, `pdfminer.six`.
- **Reuse — `services/parser.py:35,40` `restore_dates_from_markdown` / `_extract_markdown_dates`**:
  pure-regex re-hydration of month-inclusive dates the LLM drops (patches year-only fields).
  Independent of the LLM path. Prime port.
- **Adapt — `services/parser.py:144` `parse_resume_to_json`**: LLM parse → `restore_dates_from_markdown`
  → `ResumeData.model_validate`. Must be inverted behind `core`'s `StructuredCompletionProvider`;
  keep the date-restore + validate as a deterministic wrapper around the injected provider call.
  This is the vision's known no-LLM structured-parsing gap: structured extraction needs an LLM
  upstream; we design around it by making structured parse optional and always offering a no-LLM
  text-extraction mode.
- **Extract — `llm.py:218–352` JSON extraction/retry helpers** (`_extract_message_text`,
  `_to_code_block`, JSON-fence parsing): pure text/JSON-repair helpers to isolate from transport.
- **Extract — `prompts/templates.py` `PARSE_RESUME_PROMPT` + `RESUME_SCHEMA_EXAMPLE`**: pure prompt
  string constants used by structured parse.

Every ported/adapted unit must carry a modified-source marker and an `references/attribution.md`
row (upstream path + SHA), and be protected by characterization tests before any behavior change,
per the vision extraction order.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Stand up `packages/document-parser` (`resume_kit_document_parser`) as a `uv`-workspace member that
  depends inward only on `resume_kit_schemas` and `resume_kit_core` (never on `app.*`, never on a
  concrete LLM provider).
- Deterministic, no-LLM text extraction for PDF/DOCX/Markdown/plain-text via a ported MarkItDown
  wrapper, returning extracted Markdown text plus warnings — always available even when no provider
  is configured.
- Ported, pure-regex date-restoration behavior, characterization-tested against upstream.
- LLM-based structured parsing (`bytes/text → ResumeDocument`) adapted behind
  `core.StructuredCompletionProvider`, with the deterministic date-restore + schema-validate wrapper
  preserved; usable with the in-memory fake provider in tests (no network).
- A parse-result envelope carrying: extracted text, optional structured document, a parse
  **confidence** signal, structured **warnings** (taxonomy from `core`), and **provenance** recording
  which method (deterministic vs LLM) produced each part and the upstream/source lineage.
- Explicit **no-LLM text mode**: a first-class entrypoint that yields text + warnings and clearly
  signals structured parsing is unavailable, rather than failing.
- Green toolchain: `ruff`, `mypy --strict`, `pytest` all pass; characterization tests for every
  ported unit; provider-boundary tests use the fake provider only.

**Non-Goals:**
- Any matching, scoring, ATS, keyword, or gap-analysis logic (Phase 3).
- Any alignment, diff, freedom-level, evidence, or truth-validation logic (Phase 4).
- CLI/MCP/API/plugin interfaces (Phase 5); export (Phase 6).
- A concrete LiteLLM provider implementation (that lands in `packages/llm`, wired in a later phase);
  Phase 2 consumes only the `core` Protocol + the fake.
- Job-description parsing/keyword extraction (`extract_job_keywords`) — that is Phase 3 job-parser
  scope, not resume document parsing.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-201: `packages/document-parser` is a `uv`-workspace member importing cleanly; its public API
    is exported via `__init__` (extract-text entrypoint, structured-parse entrypoint, result models).
  - REQ-202: Deterministic text extraction accepts `(bytes, filename)` for PDF/DOCX and raw
    Markdown/plain text, returning extracted Markdown text + warnings, with NO LLM and NO DB.
  - REQ-203: Date-restoration behavior is ported pure (regex only) and characterization-tested to
    match upstream output on the ported fixtures before any change.
  - REQ-204: Structured parsing produces a canonical `ResumeDocument` (Phase 1 schema) via an injected
    `StructuredCompletionProvider`, applying date-restoration and schema validation deterministically
    around the provider call; it never imports a concrete provider.
  - REQ-205: The parse result carries confidence, warnings (using `core`'s warning taxonomy), and
    provenance (method + source lineage) for extracted text and structured output.
  - REQ-206: A no-LLM text-extraction entrypoint exists and, when no provider is available, returns
    text + warnings and signals structured parsing unavailable rather than raising.
- **Non-Functional:**
  - NFR-201: `mypy --strict` passes for the package; `ruff` clean; existing 284 tests stay green.
  - NFR-202: No `app.*` (upstream) import anywhere in `packages/document-parser`.
  - NFR-203: No network/LLM call in any Phase 2 test — structured parsing tests use the in-memory
    fake `StructuredCompletionProvider` from `resume_kit_core.testing`.
  - NFR-204: Every ported/adapted unit has a modified-source marker and an `attribution.md` row with
    upstream path + SHA `116f9cc`.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
Adds the first algorithmic layer above the Phase 1 substrate:
```
packages/schemas          — canonical Pydantic domain models (ResumeDocument, warnings, provenance…)
packages/core             — provider/storage Protocols, warning taxonomy, InterfaceResponse envelope
packages/document-parser  — NEW. Deterministic text extraction (MarkItDown) + date restoration
                            + LLM structured parse behind core.StructuredCompletionProvider.
                            Depends inward on core + schemas only. Provider injected, never imported.
```
Text extraction and date-restoration are pure/deterministic and always available. Structured parsing
is the only LLM-dependent path and is invoked through the injected Protocol, so the same package is
exercised with the fake provider in tests and a real provider in production without code change.

### Key boundary (illustrative)
```python
async def parse_resume_structured(
    data: bytes, filename: str, provider: StructuredCompletionProvider
) -> ParseResult:  # extracted text + ResumeDocument + confidence + warnings + provenance
    ...

def extract_resume_text(data: bytes, filename: str) -> TextExtractionResult:  # no-LLM, always available
    ...
```

## Detailed Design **[REQUIRED]**

Follow the vision extraction order for each ported unit: locate upstream equivalent (done — see
Context) → review → classify (done — reuse inventory) → **port tests / add characterization tests
first** → extract behind clean module boundaries → only then adjust behavior. Concretely:
1. Scaffold `packages/document-parser` (`pyproject.toml`, `src/resume_kit_document_parser/__init__.py`,
   `py.typed`, tests dir) as a workspace member; declare deps `markitdown[docx]`, `pdfminer.six`,
   and workspace deps on `core` + `schemas`; wire ruff/mypy/pytest.
2. Port the deterministic MarkItDown text extractor (`parse_document`) into a text-extraction module,
   stripping upstream `app.*` coupling; add a modified-source marker + attribution row; unit-test on
   fixtures (a small PDF/DOCX/MD sample under `tests/fixtures`).
3. Port date-restoration (`restore_dates_from_markdown` + `_extract_markdown_dates`) pure; add a
   characterization test asserting parity with upstream output on ported fixtures.
4. Extract the pure JSON-repair/text-extraction helpers from upstream `llm.py` (the transport-free
   subset) into a small helper module for structured parsing; characterization-test the JSON-fence
   parsing.
5. Extract the `PARSE_RESUME_PROMPT` + `RESUME_SCHEMA_EXAMPLE` prompt constants into a prompts module
   (pure strings, attributed).
6. Implement the parse-result models (extracted text, optional `ResumeDocument`, confidence,
   warnings, provenance) in a results module, reusing `core` warning/provenance types where they
   exist and `schemas` for the document.
7. Adapt `parse_resume_to_json` into `parse_resume_structured(...)` taking an injected
   `StructuredCompletionProvider`; keep date-restore + `ResumeDocument` validation as a deterministic
   wrapper; map provider/validation failures into warnings + confidence rather than hard crashes.
8. Implement the no-LLM `extract_resume_text(...)` entrypoint and the public `__init__` surface.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Characterization tests** for date-restoration and JSON-fence parsing, written to pass against
  current upstream behavior BEFORE any modification (prove-it-fails when logic is intentionally broken).
- **Unit tests** for deterministic text extraction on small PDF/DOCX/MD fixtures (content presence,
  no loss of key text), and for the no-LLM entrypoint's warnings/unavailable signaling.
- **Provider-boundary tests** for structured parse using the in-memory fake
  `StructuredCompletionProvider` from `resume_kit_core.testing`: happy path → valid `ResumeDocument`
  with provenance=LLM; malformed provider output → warnings + reduced confidence, no crash; dropped
  months → date-restoration repairs them.
- All deterministic; no network. Existing 284 tests must stay green.
- Gate: `uv run ruff check packages tests && uv run mypy packages/core packages/schemas packages/document-parser && uv run pytest`.

## Alternatives Considered **[REQUIRED]**

- **Fold parsing into `core` instead of a new package.** Rejected: `core` holds contracts only;
  putting MarkItDown + LLM parsing there reintroduces coupling and drags heavy deps (`markitdown`,
  `pdfminer`) into the contract layer. A dedicated `document-parser` package keeps the dependency
  graph honest.
- **Deterministic-only structured extraction (no LLM at all).** Rejected for now: upstream structured
  parsing is LLM-only and a robust deterministic structured extractor is out of scope; instead we make
  structured parse optional behind the provider and guarantee a no-LLM *text* mode (vision-aligned).
- **Implement a concrete LiteLLM provider here to test end-to-end.** Rejected: violates dependency
  inversion and pulls Phase-5/llm scope forward; the `core` fake provider fully exercises the boundary.
- **Reuse `parse_resume_to_json` as-is.** Rejected: it imports `app.llm`/`app.prompts`/`app.schemas`
  and hard-couples to the upstream config/transport; we adapt it behind the injected Protocol under
  characterization protection.

## Implementation Plan **[REQUIRED]**

Decomposed by a codex agent into file-disjoint tasks (see child tasks). Expected shape:
1. Scaffold `packages/document-parser` (pyproject/py.typed/toolchain/workspace wiring) — lands first.
2. Deterministic text extraction (MarkItDown port) + fixtures + unit tests + attribution.
3. Date-restoration port + characterization tests + attribution.
4. JSON-repair helpers + parse prompt constants extraction + characterization tests + attribution.
5. Parse-result models (text, document, confidence, warnings, provenance).
6. Structured parse adapter over `StructuredCompletionProvider` + no-LLM text entrypoint + public
   `__init__` + provider-boundary tests (fake provider).
Waves ordered so scaffolding lands first, then file-disjoint modules in parallel; the structured-parse
adapter (which composes the others) serializes after its dependencies.

**Exit criteria:** `packages/document-parser` imports cleanly as a workspace member; deterministic
text extraction works for PDF/DOCX/MD/plain-text with warnings and no LLM; date-restoration ported
and characterization-tested; structured parse produces a canonical `ResumeDocument` via the injected
provider with confidence/warnings/provenance and passes with the fake provider; no-LLM text mode is a
first-class entrypoint; every ported unit attributed with SHA `116f9cc` and marked; `ruff` +
`mypy --strict` + `pytest` all green; no `app.*` import in the package; existing 284 tests still pass.