---
id: agent-grown-alias-index
level: initiative
title: "Agent-Grown Alias Index (plugin, no provider)"
short_code: "RIT-I-0009"
created_at: 2026-08-04T18:50:56+00:00
updated_at: 2026-08-04T18:50:56+00:00
parent: RIT-V-0001
blocked_by: [RIT-I-0008]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: M
strategy_id: NULL
initiative_id: agent-grown-alias-index
---

# Agent-Grown Alias Index (plugin, no provider) Initiative

## Context **[REQUIRED]**

RIT-I-0008 gives the deterministic matcher a curated alias lexicon for the finite, high-frequency
tech-synonym vocabulary. But hand-curating the **long tail** (domain terms like NetSuite ↔
SuiteCommerce, "developer experience" ↔ "platform engineering", employer-specific jargon) does not
scale. The resume-intelligence plugin already runs inside an agent that has judgment AND the Phase-4
truth gates — so the agent is the right actor to PROPOSE new aliases for pairs the lexicon misses, and
to RECORD confirmed ones so the index **compounds over time** for the user's own vocabulary and domains.

This is the "maintained index" idea, but grown by the agent (with truthfulness gating) rather than
hand-authored. It layers on top of RIT-I-0008's lexicon format and stays deterministic at scoring time
— the agent produces DATA (alias entries), not a runtime LLM call. No LLM provider / embeddings
(the optional tier remains out of scope).

Relevant substrate: the plugin's `resume-kit/learning/` working-dir convention (already established),
the `job-to-json`/`resume-to-json` skills, and the alias-lexicon format from RIT-I-0008.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Define a **user/project alias file** (e.g. `resume-kit/learning/synonyms.md` or `synonyms.json`) in
  the SAME format the RIT-I-0008 lexicon uses, that the deterministic matcher loads and MERGES on top
  of the packaged seed lexicon (project overrides/extends the built-in set).
- Add plugin **skill guidance** so that, when a `check-resume-ats` / `check-resume-job-match` /
  `identify-resume-gaps` run shows a JD keyword as "missing" that the resume plausibly satisfies under
  a different term, the agent PROPOSES an alias — **truth-gated** (only genuine synonyms of the SAME
  underlying skill/fact; never "React"≈"Vue", never inflating an unrelated skill) — and, on
  confirmation, APPENDS it to the project alias file so future runs match it automatically.
- Make alias growth **auditable and reversible**: each recorded alias notes canonical, alias, and a
  one-line justification; the user can review/prune the file.
- Ensure the deterministic engine (RIT-I-0008) can be pointed at a project alias file (config/env or
  the `resume-kit/config.json` pointer) so CLI/MCP/API all honor the grown index, not just the agent.

**Non-Goals:**
- Any runtime LLM/embeddings call for matching — the agent writes DATA; scoring stays deterministic.
- Changing the deterministic matcher internals (owned by RIT-I-0008) beyond adding the
  project-alias-file MERGE hook.
- Auto-adding aliases without truthfulness gating or user visibility (must never silently equate
  distinct skills to inflate scores).
- Terminology-alignment rewrites (RIT-I-0010).

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-901: A project alias file format + location is defined under `resume-kit/learning/`, mergeable
    with the packaged seed lexicon; the deterministic matcher loads and merges it (project entries win
    on conflict, or union — decide + document).
  - REQ-902: Plugin skills instruct the agent to propose aliases ONLY for genuine same-fact synonyms,
    with a required one-line justification, and to append confirmed entries to the project file.
  - REQ-903: A truthfulness gate for alias proposals is documented and enforced in the skill: reject
    aliases that equate distinct skills, broaden scope, or would let an unsupported claim score as
    present. Ambiguous → do not add; surface to the user instead.
  - REQ-904: Recorded aliases are human-readable, justified, and prunable; a run that adds aliases
    reports what it added.
  - REQ-905: CLI/MCP/API honor the project alias file via config (not agent-only), so the grown index
    benefits every surface.
- **Non-Functional:**
  - NFR-901: No LLM/embeddings/network at scoring time.
  - NFR-902: Alias growth is deterministic-safe: merging the file never makes scoring non-reproducible
    for a fixed file.
  - NFR-903: Plugin skill markdown validates (`claude plugin validate`) and the skill test set stays
    green.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
```
Built-in seed lexicon (RIT-I-0008 package data)
        + project alias file  resume-kit/learning/synonyms.(md|json)   <-- agent appends here
        = effective AliasIndex loaded by the deterministic matcher (matching/ats)

Agent loop (plugin skills): run ATS/match -> see a "missing" keyword the resume satisfies under
another term -> apply truth gate -> propose alias -> on confirm, append {canonical, alias, why} ->
next run matches it automatically (deterministically).
```
The engine change is small: a loader hook that merges a project alias file (path from
`resume-kit/config.json`/env) with the seed. All growth logic + gates live in the plugin skills
(agent-side), keeping the engine deterministic and provider-free.

## Detailed Design **[REQUIRED]**

1. Define the project alias file format (mirror RIT-I-0008's lexicon; add per-entry `why`) and its
   location under `resume-kit/learning/`. Add a merge/loader hook in the deterministic matcher (small
   coordination with RIT-I-0008's module: accept an optional project-alias path).
2. Add/extend plugin skills (`check-resume-ats`, `check-resume-job-match`, `identify-resume-gaps`, and
   a small shared `manage-synonyms` note or the `resume-to-json`/`job-to-json` learning loop) with the
   propose→gate→confirm→append workflow and the truthfulness gate.
3. Wire config: `resume-kit/config.json` gains an `alias_file` pointer; CLI/MCP/API read it so the
   grown index applies everywhere.
4. Tests: engine merge/loader test (seed + project file → expected effective matches); plugin skill
   validation; a fixture showing a domain synonym (e.g. NetSuite↔SuiteCommerce) added to the project
   file makes a previously-missed keyword match.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Engine merge tests:** packaged seed + a temp project alias file → the project alias now matches;
  conflict/union resolution behaves as documented; missing file is a no-op.
- **Determinism:** for a fixed alias file, scoring is reproducible.
- **Skill tests:** `claude plugin validate` passes; skill markdown mentions the truthfulness gate and
  the append target; existing plugin skill test set stays green (add the new slug if a dedicated
  `manage-synonyms` skill is introduced).
- **Truthfulness guard (doc-level + example):** an illustrative rejected proposal (React≈Vue) is
  documented so agents don't equate distinct skills.

## Alternatives Considered **[REQUIRED]**

- **Hand-curate the long tail in the package.** Rejected: doesn't scale; domain/employer terms are
  per-user. The seed lexicon (RIT-I-0008) covers the finite common set; the agent grows the rest.
- **Runtime LLM synonym resolution.** Rejected/deferred: reintroduces a provider + non-determinism at
  scoring time; the agent writing durable DATA keeps scoring deterministic.
- **Global (cross-project) alias store.** Deferred: start project-scoped under `resume-kit/learning/`;
  a shared/global store can come later without changing the format.
- **Auto-append without gating/visibility.** Rejected: could silently inflate scores by equating
  distinct skills — violates the truth posture.

## Implementation Plan **[REQUIRED]**

Decompose (later, on approval) into ~3-4 tasks: (1) engine loader/merge hook for a project alias file +
config pointer + tests (coordinates with RIT-I-0008); (2) plugin skill workflow (propose→gate→
confirm→append) + truthfulness gate + validation; (3) CLI/MCP/API honor the config alias path; (4)
fixture/integration test proving a project-added domain synonym starts matching.

**Exit criteria:** the deterministic matcher merges a project alias file under `resume-kit/learning/`
with the packaged seed; plugin skills let the agent propose truth-gated aliases and append confirmed,
justified entries; every surface (not just the agent) honors the grown index via config; scoring stays
deterministic and provider-free; plugin validates and tests are green.
