# resume-intelligence Plugin

Agent skills for the resume-kit Phase 5 interface surface.

## Install

In Claude Code:

```
/plugin marketplace add dcassil/resume-kit
/plugin install resume-intelligence@resume-kit
```

**Prerequisite** — the skills and the bundled MCP server (`resume-kit-mcp`) call
the `resume-kit` package, so install it too so those commands exist on PATH:

```
uv tool install "resume-kit[all]"      # or: pip install "resume-kit[all]"
```

Without it the skill *docs* still load, but the `resume-tool` CLI and the
`resume-kit` MCP tools won't launch.

## Skill renames in v1.0.0 (RIT-A-0005)

v1.0.0 renames 14 skills to a uniform `verb-noun` lexicon so behavior class is
inferable from the name (`check-*` = safe read-only report, `validate-*` = a
hard gate, `update-*` = gated mutation, `learn-*` = future-run learning). This is
a **breaking change** (hence the major bump). If you referenced an old skill
name, update it:

| Old skill | New skill |
|-----------|-----------|
| `resume-to-json` | `parse-resume` |
| `job-to-json` | `parse-job` |
| `build-candidate-evidence` | `extract-evidence` |
| `check-ats-structure` | `check-structure` |
| `check-keyword-match` | `check-keywords` |
| `identify-resume-gaps` | `check-gaps` |
| `compare-resume-versions` | `compare-versions` |
| `select-best-resume` | `select-resume` |
| `validate-resume-truth` | `validate-facts` |
| `inject-keywords` | `update-keywords` |
| `rank-edits` | `rank-changes` |
| `review-tailored-resume` | `review-resume` |
| `log-edit-feedback` | `learn-change` |
| `manage-synonyms` | `learn-terminology` |

Six of these names were also the string identifier of a `resume-tool` CLI
command / facade capability, so those code identifiers were renamed to match in
the same release: the CLI command `check-ats-structure` → `check-structure`, and
the capability keys `check-ats-structure` → `check-structure`,
`identify-resume-gaps` → `check-gaps`, `compare-resume-versions` →
`compare-versions`, `select-best-resume` → `select-resume`,
`validate-resume-truth` → `validate-facts`, `build-candidate-evidence` →
`extract-evidence` (each carries a `Renamed to … from …` comment at its
definition). The MCP tool names (`resume_check_ats_structure`, …) are unchanged.

## Turning documents into JSON (agent-driven, no LLM provider)

The analysis/alignment capabilities operate on canonical JSON, not raw files.
Two conversion skills let the agent produce that JSON directly (best run as
**subagents** — they are confined, high-token tasks):

- **`parse-resume`** — a PDF/DOCX/MD/text resume → faithful `ResumeDocument`
  JSON, under strict no-alteration gates. Saved to
  `resume-kit/resumes/<name>-original.json`.
- **`parse-job`** — a job posting → structured `JobDescription` JSON with
  `requirements` + `keywords`, so deterministic **skills-coverage** scoring works
  without an LLM provider. Saved to `resume-kit/jobs/<name>-original.json`.

### Working directory convention

All state lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json                          # active_resume / active_job / alias_file pointers + preferences
├── resumes/<name>-original.json         # immutable faithful resume conversions
├── resumes/<name>-base.json             # baselining: original + auto-safe structural fixes
├── resumes/<name>-structure.json        # baselining: canonical shape after base
├── resumes/<name>-refine.json           # baselining: wording pass (default tailoring input)
├── jobs/<name>-original.json            # immutable job conversions
├── working/edit-session.json            # code-owned active edit-session state
├── working/<name>.tailored.json         # commit-session output for a tailored resume
├── learning/synonyms.json               # grown project alias index (default alias_file target)
└── learning/<skill>.md                  # accumulated hints; skills read these first, append new ones
```

`-original.json` files are the untouched conversions (the name maps back to the
source file). To modify a resume, propose `ChangeProposal` records and run the
`resume-tool review-edits` session loop; `commit-session` writes the tailored copy under
`working/`. Direct hand-editing of the working resume is unsupported unless the
session is reconciled with `resume-tool review-edits reconcile`.

#### `config.json` `alias_file` pointer

Alongside `active_resume` and `active_job`, `config.json` may carry an optional
`alias_file` key pointing at a project alias JSON (the RIT-T-0068 format
`{"version": 1, "aliases": {canonical: [alias, ...]}}`). It defaults to
`learning/synonyms.json` and is resolved against the `resume-kit/` working dir
(not the shell CWD), matching the `active_resume`/`active_job` convention.

`config.json` is code-owned by `resume-tool init` / `resume-tool set-active`;
skills must not hand-edit it. Keyword-scoring surfaces also accept an explicit
`alias_file` override — `resume-tool match --alias-file <path>` /
`identify-gaps --alias-file <path>` on the CLI, an `alias_file` field on the
`resume_check_job_match` / `resume_identify_gaps` MCP tools, and an `alias_file`
body field on the corresponding API routes. Keyword matching uses the alias
index; `check-structure` is structure-only and takes no alias file. When the
pointer is absent the surfaces run seed-only, identical to prior behaviour.

These skills describe how an agent drives the `resume-tool` CLI or the MCP
server. Each skill does ONE thing and self-gates on its prerequisites (it stops
and names the upstream skill to run first when a required input — a resume/job
JSON — is missing, rather than producing empty output). Start with the
`resume-workflow` guide, which sequences the skills. Skills are thin invocation
guides — they do not implement resume intelligence logic and must not invent
facts, bypass evidence, or create business rules in prompt text.

## Workflow (start here)

`resume-workflow` is the entry-point guide; it runs the skills in order:

1. **Ingest** — `parse-resume`, `parse-job` (no LLM; the agent converts the
   files/posting into canonical JSON). Writes the immutable `<name>-original.json`.
2. **Baseline** *(job-independent — REQUIRED before any tailoring)* — take
   `original` through `original → base → structure → refine`: `update-structure`
   runs the structural check + the auto-safe `base` fix behind the
   claim-preservation gate (`<name>-base.json`) and the lossless structure pass
   (`<name>-structure.json`); `check-best-practices` scores `structure` and
   classifies each finding `auto_suggestible` vs `needs_user_input`;
   `update-refine` applies the auto-suggestible rewrites plus user-supplied
   facts through the `build-refine` capability and writes `<name>-refine.json`
   behind the same gate. **`refine` then becomes the default resume for all
   tailoring below** (active resolution is
   `refine ?? standard(legacy) ?? structure ?? base ?? original`). The
   CLI/capability/API surface is `build-refine`; the MCP tool is
   `resume_build_refine`. Migration: the former `standard` pass is now
   `refine`; legacy `standard_resume` pointers still resolve as a read-alias,
   and `build-standard` surfaces remain as one-release deprecation aliases for
   `build-refine`. If the user declines baselining, that override is recorded so
   the tailoring gate is satisfied.
3. **Check** *(tailoring — gated on `refine` or a recorded override)* —
   `check-keywords` (resume↔job keyword coverage) and `check-gaps`
   (missing / injectable keywords), both run against `refine`. The structural
   check already ran in baselining and is not repeated. `check-ats-view` renders
   the read-only "what the ATS sees" report (sections, entities/YoE, and zoned
   keywords) off the same deterministic ScoreDoc projection that scoring reads.
4. **Improve** (no LLM, truth-gated; gated on `refine`) — `update-keywords` and
   `update-terminology` produce truthful `ChangeProposal` records, prompt for
   mode (`interactive`, `review_at_end`, or `auto`), then drive
   `resume-tool review-edits open` → `resume-tool review-edits prompt` →
   `resume-tool review-edits decide` → `resume-tool review-edits commit` →
   `validate-facts`. When several truthful candidates exist,
   `rank-changes` calls `resume-tool rank-edit-candidates` first; after a
   decision, `learn-change` calls `resume-tool record-edit-feedback` and
   refreshes preferences with `resume-tool refresh-preferences --now <iso>`.
   Confirmed user evidence is persisted with
   `resume-tool add-evidence --confirmed --content ...`; `validate-facts`
   reports near-match confirmed claims as `USER_CONFIRMED`, reserves
   `CONTRADICTED` for structural conflicts or active refutations, and uses
   `UNSUPPORTED` for missing evidence. Every claim includes a stable
   `reason_code`.
5. **Verify** — `validate-facts`; then re-run the checks to see the delta.
6. **Review** (optional, no LLM provider) — `review-resume` dispatches a
   subagent to critique the tailored resume against the original + job and writes
   parseable, advice-only findings to `resume-kit/review/<session>.md` (it never
   edits the resume; act on findings via `update-keywords` /
   `update-terminology` / `validate-facts`).
7. **Export** — `export-resume` (PDF/DOCX).

Supporting: `extract-evidence`, `compare-versions`,
`select-resume`, and `learn-terminology` (grows the project alias index used
by keyword matching + terminology).

## Capability Map

| Skill directory | CLI command | MCP tool name | LLM required? |
|---|---|---|---|
| `parse-resume` | (agent-driven) | — | No (agent converts) |
| `parse-job` | (agent-driven) | — | No (agent converts) |
| `check-structure` | `resume-tool check-structure` | `resume_check_ats_structure` | No (deterministic) |
| `check-keywords` | `resume-tool match` | `resume_check_job_match` | No (deterministic) |
| `check-gaps` | `resume-tool identify-gaps` | `resume_identify_gaps` | No (deterministic) |
| `check-ats-view` | `resume-tool ats-view` | `resume_ats_view` | No (deterministic) |
| `update-keywords` | `resume-tool review-edits open`; `resume-tool review-edits prompt`; `resume-tool review-edits decide`; `resume-tool review-edits commit`; `resume-tool review-edits status`; `resume-tool review-edits reconcile` | `edit_session_open` / `edit_session_prompt` / `edit_session_decide` / `edit_session_commit` / `edit_session_status` / `edit_session_reconcile` | No (deterministic gate) |
| `update-terminology` | `resume-tool suggest-terminology` + `resume-tool review-edits open`; `resume-tool review-edits prompt`; `resume-tool review-edits decide`; `resume-tool review-edits commit`; `resume-tool review-edits status`; `resume-tool review-edits reconcile` | `resume_suggest_terminology` + `edit_session_open` / `edit_session_prompt` / `edit_session_decide` / `edit_session_commit` / `edit_session_status` / `edit_session_reconcile` | No (deterministic gate) |
| `validate-facts` | `resume-tool validate-truth` | `resume_validate_truth` | No (deterministic) |
| `extract-evidence` | `resume-tool build-evidence` | `candidate_evidence_build` | No (deterministic) |
| `compare-versions` | `resume-tool compare` | `resume_compare_versions` | No (deterministic) |
| `select-resume` | `resume-tool select` | `resume_select_best` | No (deterministic) |
| `export-resume` | `resume-tool export` | `resume_export` | No (deterministic) |
| `add-evidence` | `resume-tool add-evidence --confirmed` | `candidate_evidence_add` | No (deterministic) |
| `learn-terminology` | (agent-driven) | — | No (grows alias index) |
| `review-resume` | (agent-driven, advice-only) | — | No (subagent) |
| `rank-changes` | `resume-tool rank-edit-candidates` | `edit_candidates_rank` | No (deterministic ranking) |
| `learn-change` | `resume-tool record-edit-feedback` / `resume-tool refresh-preferences` | `edit_feedback_record` / `preferences_refresh` | No (records outcome) |
| `resume-workflow` | (guide) | — | No (orchestration) |

**Disabled / not surfaced as skills:** LLM auto-rewrite (`align-resume`) is
disabled for now — the no-LLM `update-keywords` + `update-terminology` cover
truthful tailoring. The raw LLM extract tools (`resume_extract`,
`job_description_extract`) remain callable via CLI/MCP but are not surfaced as
skills; prefer the agent-driven `parse-resume` / `parse-job`, which need no
provider.

## Architecture Note

Every interface is a thin adapter over `resume_kit_facade`.  No business rule
lives in an interface.  Agents invoke the CLI or MCP tool and act on the
returned `InterfaceResponse` (data / warnings / errors / requiresHumanInput /
questions / provenance).

## Phase 6 Capabilities (NOT built — do not invoke)

`check-resume-consistency`, `score-resume-bullet`, `improve-resume-section`,
`create-job-specific-resume`, `check-cover-letter-job-match`,
`align-cover-letter`, `audit-application-package`.  These names are reserved
but have no engine implementation and no CLI/MCP tool.
