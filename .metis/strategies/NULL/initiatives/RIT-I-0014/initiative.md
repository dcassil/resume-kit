---
id: deterministic-ingest-boundary
level: initiative
title: "Deterministic ingest boundary: extract/validate rails + narrow interpretation agent"
short_code: "RIT-I-0014"
created_at: 2026-08-05T14:21:27.757306+00:00
updated_at: 2026-08-05T14:31:40.843352+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/active"


exit_criteria_met: false
estimated_complexity: M
strategy_id: NULL
initiative_id: deterministic-ingest-boundary
---

# Deterministic ingest boundary: extract/validate rails + narrow interpretation agent Initiative

## Context **[REQUIRED]**

An end-to-end test run of the `resume-intelligence` plugin (init working folder → ingest job → ingest resume → score) exposed a boundary problem. Scoring (`resume-tool check-ats-structure` / `match`) was rock-solid, deterministic, and cheap. Everything upstream of it was the agent improvising around missing rails:

- **Init/scaffold** — the agent hand-created `resume-kit/`, `config.json`, and `synonyms.json` by following the README convention. No code owns this state, so the agent can typo the schema, forget a key, or drift from the canonical shape.
- **Resume ingest** — the `resume-to-json` skill explicitly tells the agent *"You (the agent) are the converter… no LLM provider and no PDF library required."* On a binary `.docx` the agent extracted text via raw zip/XML and hand-authored the JSON. Fragile — it only worked because the agent improvised.
- **Faithfulness** — enforced only by prose ("count the bullets and confirm they match"). The agent grades its own homework; there is no machine gate.

Root cause, confirmed by an independent code review (see Alternatives): the skill lumps three different kinds of work — **extraction** (mechanical), **interpretation** (needs judgment), and **validation** (mechanical) — into one hand-authored agent step, and steers the agent *away* from deterministic CLI that already exists.

Two important corrections surfaced during review that shape scope:

1. **Extraction is already deterministic and bundled.** `packages/document-parser/.../text_extraction.py` (`extract_resume_text` / `extract_resume_text_only`) does docx/pdf/md/txt → text with no LLM and no network, and `python-docx` + `markitdown` are in the **base** wheel. The tester's "python-docx missing" was a *stale install* + the skill steering away from `resume-tool extract`. The `resume-to-json` skill even claims PDF needs the optional `markitdown[pdf]` extra, which **contradicts the README base deps** — a real doc bug and the likely reason the agent never reached for the CLI.
2. **The text→schema step is irreducibly agentic.** `resume-tool extract --no-llm` returns `document=None` + `PROVIDER_FALLBACK_USED` — the deterministic path yields *text only*, never a `ResumeDocument`. So "deterministic ingest" cannot mean a single opaque command; interpretation must stay an agent step, wrapped by deterministic gates on both sides.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Give code ownership to the `resume-kit/` state contract: a deterministic `init` (scaffold folder + `config.json`) and `set-active` (record `active_resume` / `active_job` and the **source file path** each ingest came from).
- Expose a first-class deterministic **extraction** primitive (`extract-text`) that the ingest skills hand to the interpretation agent, and steer the skills to it instead of raw file-reading.
- Add a deterministic **faithfulness HARD GATE** (`validate-faithfulness`) that diffs the agent-produced JSON against the source (bullet/section count parity, token-set diff, non-ASCII scan, verbatim spot-checks) and exits non-zero on drift.
- Rewrite `resume-to-json` and `job-to-json` around the pipeline `extract-text (script) → agent maps text→JSON (subagent) → validate-faithfulness (script HARD GATE) → set-active (script)`, and name the gate in `resume-workflow`.
- Fix the extraction docs/skill contradiction so docx/pdf are correctly described as deterministic and bundled.

**Non-Goals:**
- **Not** building a single opaque `resume-tool ingest` that hides the agent step (the text→schema step is inherently agentic — see Alternatives).
- **Not** adding any new PDF dependency or `markitdown[pdf]` install prompt — the base wheel already covers it.
- **Not** repurposing `validate-truth` as the faithfulness gate — it answers a different question (resume claims vs. `CandidateEvidence`, i.e. internal consistency, not fidelity to the source document). The two stay distinct.
- **Not** replacing the agent interpretation step with a heuristic/regex parser — resume structure varies too wildly (sub-headed role groupings, bare "Career Break" lines, categorized vs flat skills, arbitrary custom sections).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional Requirements**
  - REQ-001: `resume-tool init` deterministically scaffolds `resume-kit/` (config.json with active pointers + alias_file, resumes/, jobs/, working/, learning/) and is idempotent (safe to re-run; does not clobber existing pointers).
  - REQ-002: `resume-tool set-active` records `active_resume` / `active_job` **and** the originating source file path for each, writing to `config.json` via a code-owned schema.
  - REQ-003: `resume-tool extract-text <file>` returns the deterministic `TextExtractionResult` (text + warnings + method) for docx/pdf/md/txt with no LLM and no network.
  - REQ-004: `resume-tool validate-faithfulness --source <file|text> --json <ResumeDocument>` runs deterministic parity/diff checks and exits non-zero on violation, emitting a machine-readable report of dropped/added/altered content and count mismatches.
  - REQ-005: `resume-to-json` / `job-to-json` orchestrate extract-text → agent interpretation (subagent) → validate-faithfulness (blocking) → set-active, and only write `-original.json` after the gate passes; on gate failure the agent gets the diff and loops once.
- **Non-Functional Requirements**
  - NFR-001: Every new capability follows the existing cross-surface parity norm (facade capability + CLI + MCP + API where applicable) with parity tests, consistent with prior phases.
  - NFR-002: `validate-faithfulness` tolerance rules must normalize whitespace/casing/punctuation so faithful conversions do not produce false-positive gate failures, while still catching genuinely dropped or altered content.
  - NFR-003: No new hard third-party dependency; no network calls in any new deterministic command.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
The ingest pipeline is re-modeled as a **scripted spine owned by the skill**, calling deterministic CLI on both ends and an agent (confined subagent) only for the interpretation step:

```
resume-to-json / job-to-json (skill = orchestrator)
  → [CLI]    extract-text <file>            deterministic (bundled libs, no LLM)
  → [AGENT]  map text → ResumeDocument JSON   semantic, subagent, kept out of main context
  → [CLI]    validate-faithfulness           deterministic HARD GATE (blocks write)
  → [CLI]    set-active                       deterministic; records source path + active pointer
```

The CLI stays a pure deterministic transport over the facade — it never spawns agents. Orchestration lives in the skill. This is the key correction to the tester's proposed monolithic `ingest` command.

### Component impact
- **New engine module** for faithfulness diffing (bullet/section parity, token-set diff, non-ASCII scan, verbatim spot-check) with a result schema — likely a small package/module consumed by the facade.
- **New config-owner module** for the `resume-kit/` state contract (config.json schema incl. source paths), consumed by `init` / `set-active`.
- **Facade capabilities** for extract-text, validate-faithfulness, init, set-active; **CLI** commands wrapping them; **MCP/API** surfaces where the parity norm calls for it.
- **Skill rewrites** for `resume-to-json`, `job-to-json`, and a new gate step in `resume-workflow`; **doc fixes** in `commands/setup.md` and README.

### Sequence (happy path + gate failure)
1. Skill resolves source file path → `extract-text` → hands text to interpretation subagent.
2. Subagent returns candidate `ResumeDocument` JSON → skill runs `validate-faithfulness`.
3. Pass → write `-original.json`, `set-active`. Fail → hand the diff back to the subagent, loop once; if still failing, surface to the user.

## Detailed Design **[REQUIRED]**

See the six decomposed tasks for per-command design. Design invariants:
- Interpretation stays agentic and confined to a subagent; the CLI never calls an LLM in these paths (`--no-llm` semantics preserved).
- `validate-faithfulness` is the authoritative gate; the prose faithfulness rules in the skill are retained only as *guidance for the interpretation step*.
- `config.json` gains a machine-owned schema including the source file path per active document, which is what makes the faithfulness gate wiring possible.
- Resumes and jobs are treated **symmetrically** — `job-to-json` has the identical extraction/interpretation problem and gets the same pipeline.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

### Unit Testing
- **Strategy**: Table-driven tests for `validate-faithfulness` tolerance rules — faithful conversions pass; dropped bullet, altered date, added (fabricated) bullet, and non-ASCII cases fail with the right codes. Unit tests for the config-owner schema (idempotent init, source-path recording).
- **Tools**: existing pytest setup.

### Integration Testing
- **Strategy**: End-to-end ingest over a real `.docx` and `.pdf` fixture proving (a) extraction is deterministic via CLI, (b) a deliberately lossy JSON is rejected by the gate, (c) a faithful JSON passes and sets active pointers with the recorded source path.
- **Data Management**: reuse/extend existing resume fixtures (e.g. resume-d) plus a small synthetic docx.

### Test Selection
Prioritize the faithfulness gate (highest new risk / most valuable), then the config contract, then thin CLI/surface wrappers and parity tests.

## Alternatives Considered **[REQUIRED]**

- **Single opaque `resume-tool ingest` (tester's literal proposal).** Rejected: the middle step (text→schema) is irreducibly agentic — a monolithic deterministic command would either re-introduce a mandatory LLM provider inside the CLI or fall back to a lossy heuristic parser. Chosen instead: compose deterministic CLI on both ends with the agent confined to the middle, orchestrated by the skill.
- **Heuristic/regex structured parser to remove the agent entirely.** Rejected: resume structure varies too wildly; brittle and lossy. `extract --no-llm` already demonstrates the deterministic structured path yields no usable document.
- **Reusing `validate-truth` as the faithfulness gate.** Rejected: it validates claims against `CandidateEvidence` derived from the resume (internal consistency), not fidelity of JSON to the source document — a different question. Kept distinct.
- **Adding `markitdown[pdf]` as a prompted extra.** Rejected: base wheel already bundles extraction deps; the perceived gap was a documentation/steering bug, fixed by Task RIT (docs) rather than a dependency change.

Independent review corroborating this decomposition is archived in the initiative discussion; it confirmed the CLI surface (`no init/ingest/set-active/validate-faithfulness`), that config.json is unowned by code, and that `--no-llm` returns no structured document.

## Implementation Plan **[REQUIRED]**

Six tasks (see children). Ordering & dependencies:
1. **Docs/skill contradiction fix** — independent, ships immediately; prevents recurrence of the tester's incident on its own.
2. **`extract-text` CLI + facade** — deterministic extraction primitive.
3. **`init` + `set-active` + config-owner schema** — foundational state contract (records source path).
4. **`validate-faithfulness` HARD GATE** — the highest-value new capability; can accept an explicit source path so it is not hard-blocked by (3), but wires best after it.
5. **Rewrite `resume-to-json` / `job-to-json` + `resume-workflow` gate step** — depends on 2, 3, 4.
6. **Integration test + README/tests reconcile + version bump** — depends on 5.

Human-in-the-loop checkpoints (per Metis initiative rules): confirm scope before decompose (this document), and review the faithfulness tolerance-rule design (Task 4) before finalizing, since false-positive risk is the main design hazard.