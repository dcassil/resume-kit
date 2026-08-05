---
id: single-responsibility-skill
level: initiative
title: "Single-responsibility skill redesign + self-gating + flow guide"
short_code: "RIT-I-0011"
created_at: 2026-08-05T01:21:30.087274+00:00
updated_at: 2026-08-05T01:47:49.676131+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: M
strategy_id: NULL
initiative_id: single-responsibility-skill
---

# Single-responsibility skill redesign + self-gating + flow guide Initiative

## Context **[REQUIRED]**

The resume-intelligence plugin's SKILL layer grew organically to 15 skills with overlapping purposes,
ambiguous names, and skills whose default path silently requires an LLM provider. Real agent test runs
exposed the failure modes:
- An agent ran the deterministic `job_description_extract` and got EMPTY keywords/qualifications (the
  LLM path is the default; no provider was configured), then had to hand-build the JobDescription — the
  `job-to-json` skill already does this, but the overlap made the right path non-obvious.
- Another agent found `align-resume` is a silent no-op without a provider (empty change set), and worked
  around it by doing the tailoring itself — confirming that the agent-driven, truth-gated pattern is what
  actually works.

Overlaps/ambiguity today: `extract-resume` vs `resume-to-json`; `extract-job-description` vs
`job-to-json`; three "how good is this resume?" skills (`check-resume-ats`, `check-resume-job-match`,
`identify-resume-gaps`); two "align" skills with very different mechanics/safety (`align-resume`
LLM-rewrite vs `align-terminology` deterministic surface mirror).

Decision (owner: Daniel): make each skill do ONE thing, have each skill self-gate on its prerequisites
(so running keyword matching without the job/resume JSON stops with a clear "run X first" instead of
empty output), and add a thin orchestration guide that sequences the skills. Remove/disable the
provider-only duplicate skills. Changes are confined to the SKILL layer + the plugin's own tests/README;
the MCP tools, CLI, facade capabilities, and the job-hunter bridge are NOT renamed (skills present a
single slice of an existing tool's output). This is a plugin/agent-UX initiative — no engine behavior or
scoring math changes.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Every remaining skill has ONE clear responsibility and an unambiguous verb-noun name, so an agent
  never has to choose between overlapping skills.
- Every skill begins with a **Prerequisites gate**: it verifies its required inputs exist (via the
  `resume-kit/` working-dir convention — `config.json` `active_resume`/`active_job` → the resume/job
  JSON, plus any skill-specific inputs) and, if a prerequisite is missing, STOPS and names the exact
  skill to run first. No skill silently produces empty/garbage output from missing inputs.
- Split the composite ATS check into single-purpose checks: `check-ats-structure` (only structural/parse
  issues that make an ATS miss or error) and `check-keyword-match` (only resume↔job keyword coverage).
  The blended 0.20/0.55/0.25 composite score is dropped (it belonged to no single skill); the
  orchestration guide shows the granular results together.
- Add two single-purpose IMPROVE skills that work with NO provider, both truth-gated: `inject-keywords`
  (surface missing-but-true keywords into the resume) and `update-terminology` (mirror the JD's exact
  wording for a synonym the resume already satisfies — the renamed `align-terminology`).
- Add a `resume-workflow` orchestration guide that sequences the skills (ingest → check → improve →
  validate-truth → re-check → export), names the gates, and marks optional steps.
- Remove/disable the provider-only duplicate skills (`extract-resume`, `extract-job-description`,
  `align-resume`) and the composite scorers (`check-resume-ats`, `check-resume-job-match`). Underlying
  MCP tools/CLI stay callable; only the SKILL wrappers go.
- Keep `claude plugin validate` green and the plugin skill-markdown test suite green throughout; bump the
  plugin version.

**Non-Goals:**
- No rename/merge of MCP tools, CLI commands, facade capabilities, or the job-hunter bridge. The only
  exception is if a single-purpose check genuinely cannot be sliced from an existing tool's output
  (e.g., a resume-only structure check that the composite tool won't produce without a job) — treated as
  an investigation point in RIT-T-0072-equivalent, and only a minimal additive change if unavoidable.
- No change to engine scoring math, matching, alignment, policy, evidence, terms, or export behavior.
- No re-enable of LLM auto-rewrite (`align-resume`) — disabled for now; may return later behind a clear
  provider gate.
- No new PyPI engine release required (this is plugin-layer). A plugin version bump only.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional Requirements:**
  - REQ-1101: Each shipped skill does exactly one thing, named verb-noun and unambiguously; no two
    skills overlap in purpose.
  - REQ-1102: Each skill's first step is a Prerequisites gate that checks required inputs and, when
    missing, halts with an explicit "run `<skill>` first" message — never empty output.
  - REQ-1103: `check-ats-structure` reports ONLY structural/parse issues + section completeness (resume
    only, job-independent where feasible). `check-keyword-match` reports ONLY keyword coverage +
    matched/missing (resume + job). Neither emits a blended composite score.
  - REQ-1104: `inject-keywords` and `update-terminology` are single-purpose, no-LLM, and truth-gated
    (route through / respect `validate-resume-truth`; never fabricate; identity/date/employer untouched).
  - REQ-1105: `resume-workflow` guide sequences the skills with explicit order, gates, and optional
    steps; it references skills by their exact slugs.
  - REQ-1106: Removed skills (`extract-resume`, `extract-job-description`, `align-resume`,
    `check-resume-ats`, `check-resume-job-match`) no longer exist as skill directories; the plugin
    skill-slug test set and README table reflect the final set.
- **Non-Functional Requirements:**
  - NFR-1101: `claude plugin validate` passes; the plugin skill-markdown test suite stays green
    (`EXPECTED_SKILL_SLUGS` / `EXPECTED_CLI_OR_MCP` reconciled to the final set).
  - NFR-1102: No changes to MCP tool names, CLI commands, facade capabilities, or the job-hunter bridge
    (except a minimal, additive engine slice only if a structure-only check is otherwise impossible).
  - NFR-1103: The full `uv run pytest` engine suite stays green (skills are markdown; engine untouched).

## Detailed Design **[REQUIRED]**

Final skill set (13 + guide):
- **Ingest (no-LLM):** `resume-to-json`, `job-to-json`.
- **Check (no-LLM):** `check-ats-structure` (reshaped from `check-resume-ats` — structure/parse issues +
  section completeness only), `check-keyword-match` (reshaped from `check-resume-job-match` — keyword
  coverage + matched/missing only), `identify-resume-gaps` (kept; single-purpose gap list).
- **Improve (no-LLM, truth-gated):** `inject-keywords` (NEW — surface missing-but-true keywords into
  skills/summary), `update-terminology` (renamed from `align-terminology` — mirror JD synonym wording).
- **Verify/support (no-LLM):** `validate-resume-truth`, `build-candidate-evidence`,
  `compare-resume-versions`, `select-best-resume`.
- **Export (no-LLM):** `export-resume`. **Maintain:** `manage-synonyms`.
- **Flow:** `resume-workflow` (NEW guide).
- **Removed:** `extract-resume`, `extract-job-description`, `align-resume`, `check-resume-ats`,
  `check-resume-job-match`.

**Prerequisites-gate convention:** a shared, copy-pasted-consistent "## Prerequisites" section + a first
"Gate:" step in each skill. It resolves inputs from the `resume-kit/` working dir (`config.json`
`active_resume`/`active_job` → JSON paths) and, if missing, stops and names the upstream skill
(`resume-to-json` / `job-to-json`). Skills that also need gaps or evidence name those upstream skills.
Because skills are agent instructions (not code), the gate is an instruction the agent executes — the
underlying tools still error cleanly, but the gate prevents reaching them with missing inputs.

**Slice-not-rename:** `check-ats-structure` and `check-keyword-match` both call existing tools and
present only their slice of the output (section completeness/recommendations vs keyword coverage/
matched-missing). Investigation point: confirm `check-ats-structure` can produce a resume-only structural
result from the existing tool; if the composite tool requires a job input to return section completeness,
make the minimal additive engine change to expose structure-only (NFR-1102 exception) — otherwise no
engine change.

**resume-workflow guide:** documents the canonical order — `resume-to-json` + `job-to-json` →
`check-ats-structure` + `check-keyword-match` + `identify-resume-gaps` → (improve) `inject-keywords`
and/or `update-terminology` → `validate-resume-truth` → re-run the checks to show deltas → `export-resume`
— with each step's gate and which are optional. Notes that `manage-synonyms` grows the alias index and
that LLM auto-rewrite is disabled.

## Alternatives Considered **[REQUIRED]**

- **Merge the three scorers into one `evaluate-resume` skill + a router (original proposal).** Rejected
  by the owner in favor of single-responsibility skills: smaller units are easier to test, refine, and
  maintain, and a merged skill re-introduces multi-purpose ambiguity. The orchestration guide provides
  the combined view instead.
- **Keep the composite ATS score as its own tiny skill.** Rejected: the blended 0.20/0.55/0.25 weighting
  is somewhat arbitrary and belongs to no single responsibility; granular structure + keyword results are
  clearer and the guide shows them together.
- **Additive-only (keep all skills, add warnings + router).** Rejected: leaves the overlaps and ambiguous
  names that caused the agent failures.
- **Rename the MCP tools/CLI/facade to match (full rename).** Rejected: large blast radius (`.mcp.json`,
  CLI, facade parity tests, job-hunter bridge) for no agent-UX benefit; the skills can present a single
  slice of existing tools.
- **Leave provider-gated skills, mark them only.** Partially adopted (removal chosen over marking for the
  duplicates); marking alone kept the dead-end skills discoverable.

## Implementation Plan **[REQUIRED]**

Decompose (on approval) into file-disjoint skill-dir tasks + one orchestrator integration pass:
1. **Check skills** — create `check-ats-structure` + `check-keyword-match` (single-purpose slices) with
   gates; add gate to `identify-resume-gaps`; resolve the structure-only investigation point.
2. **Improve skills** — create `inject-keywords` (NEW, truth-gated) + `update-terminology` (rename
   `align-terminology`, keep behavior, add gate).
3. **Gates + guide** — add the Prerequisites-gate section to the ingest/verify/support/export/maintain
   skills; author the `resume-workflow` orchestration guide; author the shared gate-convention reference.
4. **Integration (orchestrator)** — remove the 5 deprecated skill dirs, reconcile
   `EXPECTED_SKILL_SLUGS` + `EXPECTED_CLI_OR_MCP`, rewrite the README skill/tool table + add a flow
   section, bump the plugin version, run `claude plugin validate` + the full gate.

**Exit criteria:** the plugin ships the final single-responsibility skill set; every skill self-gates on
its prerequisites; the composite ATS scorers and provider-only duplicates are gone; a `resume-workflow`
guide sequences the flow; `claude plugin validate` passes; the plugin skill-markdown suite + full
`uv run pytest` engine suite are green; README + version updated. No MCP/CLI/facade/bridge renames (save
any unavoidable minimal additive engine slice for structure-only, explicitly noted if used).