# Resume Intelligence Toolkit (`resume-kit`)

A reusable, trustworthy system for **evaluating, comparing, aligning, generating, and
validating** resume materials against specific jobs. It answers five core questions:

- Can an ATS reliably parse this resume?
- How closely does this resume match a specific job?
- Which relevant qualifications are missing or poorly represented?
- What truthful changes would improve alignment?
- Did the revised resume actually improve?

Resume-kit is a shared **core engine** exposed through an **agent plugin**, an **MCP server**,
a **CLI** (`resume-tool`), and a **REST API**. All interfaces are thin adapters over the same
core — no business rule lives only in a route, command, handler, or skill.

## Installation

`resume-kit` ships as a single self-contained wheel that vendors every internal
import package. Choose extras for the surface(s) you want:

```bash
pip install resume-kit          # core engine + export (base)
pip install "resume-kit[cli]"   # + the resume-tool CLI
pip install "resume-kit[mcp]"   # + the MCP server
pip install "resume-kit[api]"   # + the FastAPI/uvicorn REST API
pip install "resume-kit[all]"   # everything
```

The base install carries the engine and export third-party runtime dependencies
(`pydantic`, `markitdown`, `pdfminer.six`, `python-docx`, `reportlab`). Extras add
`typer` (cli), `mcp` (mcp), and `fastapi` + `uvicorn` (api).

### The `resume-tool` command

Installing the `cli` extra exposes the console script:

```bash
pip install "resume-kit[cli]"
resume-tool --help
```

### Deterministic ingest pipeline

Turning a resume/job file into structured JSON is split into **deterministic
rails around one confined interpretation step**, so only the text→schema mapping
needs an agent — extraction and validation are mechanical:

```bash
resume-tool init                                   # scaffold resume-kit/ + config.json (idempotent)
resume-tool extract-text resume.docx               # deterministic text (docx/pdf/md/txt), no LLM, no network
#  → agent maps the extracted text onto the ResumeDocument schema (the one agentic step)
resume-tool validate-faithfulness \                # HARD GATE: exits non-zero on drift
  --source resume.docx --json resume-kit/resumes/resume-original.json
resume-tool set-active \                            # record active pointer + originating source path
  --resume resumes/resume-original.json --source resume.docx
```

Text extraction (`markitdown`, `pdfminer.six`, `python-docx`) is bundled in the
**base** install — docx/pdf/md/txt all extract deterministically with no optional
extra. `validate-faithfulness` is a machine gate: it diffs the produced JSON
against the source (bullet/section parity, dropped/added tokens, altered
high-signal fields, non-ASCII scan) and **exits non-zero** when the conversion is
not faithful, so an unfaithful conversion never silently reaches disk. The
`resume-kit/` working directory and its `config.json` (active resume/job pointers,
their source paths, and `alias_file`) are owned by code via `init` / `set-active`
— not hand-authored.

### BuildDoc vs. ScoreDoc — the scoring projection

The resume the pipeline edits and exports (`ResumeDocument`, the **BuildDoc**) is
kept distinct from the representation that scoring reads. Before any scoring or
matching runs, a deterministic, offline `project_scoredoc` projects the BuildDoc
into a **ScoreDoc**: a zoned keyword index, segmented sections tagged by zone
(skills list, experience, summary, …), and extracted entities plus years of
experience. All scoring and matching read the ScoreDoc — not the raw resume JSON.

This is why a skill listed in a *categorized* custom section (e.g. a
`stringList` "Cloud Skills" section) now counts as a canonical skill rather than
incidental body text: the projection maps it into the skills zone, so it earns
the same keyword-placement credit as `additional.technicalSkills`. The ScoreDoc
is also what powers the **ats-view** "what the ATS sees" report — the read-only
view of the sections, entities/YoE, and zoned keywords an ATS is likely to parse
(`resume-tool ats-view --resume <path>`), identical across the CLI, MCP, API, and
facade surfaces.

### Resume baselining and final fit (`original → base → structure → standard → refine → tailored → perfect`)

Before any job-specific tailoring, a resume moves through a fixed, deterministic
baselining lineage that produces four tracked versions:

```bash
resume-tool build-base                              # original → base (auto): strips PII, normalizes
                                                    #   presentation, behind the claim-preservation gate
resume-tool analyze-shape \                         # base → structure report: redundant/non-standard
  --resume resumes/resume-base.json                 #   sections, mappings, and informational budgets
resume-tool build-structure                         # base → structure: canonicalizes shape losslessly
                                                    #   behind ledger + claims-preserved gates
resume-tool analyze-best-practices \                # job-independent best-practices report; each finding
  --resume resumes/resume-structure.json            #   is auto_suggestible or needs_user_input
resume-tool build-standard --answers answers.json   # structure → standard: applies auto-suggestible rewrites
                                                    #   + user-supplied facts, behind the same gate
```

- **`original`** — the faithful, code-owned ingest of the source file (produced by
  the pipeline above; never edited in place).
- **`base`** — `original` with only *auto-safe* structural fixes applied (PII
  removed, formatting/date presentation normalized). `build-base` runs the
  structural check and writes `<name>-base.json` **only if the
  claim-preservation gate holds** — no employer/title/degree/skill claim may be
  added, dropped, or altered. Findings that need judgment are deferred to the
  walkthrough.
- **`structure`** — `base` projected into the canonical resume schema:
  redundant skill/custom sections are merged and deduped, section order is
  normalized, and ambiguous custom sections are deferred rather than guessed.
  `build-structure` writes `<name>-structure.json` only when the content ledger
  is fully accounted and whole-resume claims are preserved.
- **`standard`** — `structure` after the generic best-practices walkthrough:
  every finding is classified `auto_suggestible` (a truthful rewrite is applied
  now) or `needs_user_input` (the user supplies real facts, e.g. a metric).
  Applied behind the same claim-preservation gate. If no `structure` exists yet,
  `build-standard` remains backward-compatible and falls back to `base`, then
  `original`.

**All job-specific tailoring runs off `standard`, not `original`.** The active
resume resolves as `standard ?? structure ?? base ?? original`, so once
baselining has run, downstream tailoring and edit sessions operate on the
best-practices-improved `standard` version by default. The lineage is fully
deterministic and offline: no LLM or network is touched on the baselining path.

After the improve/refine loop produces a job-specific tailored resume, run the
perfect fit pass before export:

```bash
resume-tool fit --root . --job jobs/job.json              # inspect ranked budget-fit decisions
resume-tool fit --root . --job jobs/job.json --auto-fit   # commit logged auto-fit decisions
```

`perfect` is job-specific and non-destructive of the master lineage: it reads
the resolved tailored input, writes `<name>-<job>-final.json`, and records every
removal as either a ranked decision or a logged auto-fit change in the content
ledger. The MCP surface is `resume_build_perfect` with the same `root`, `job`,
`decisions`, and `auto_fit` inputs. Export remains the rendered page hard gate:
the exporter enforces `shape_policy.informational_budgets.max_pages`, blocking
over-length output unless the caller uses the explicit page-budget override.

### Project aliases and accepted terminology edits

The deterministic matcher loads the packaged seed alias lexicon plus an optional
project alias file from `resume-kit/config.json`'s `alias_file` pointer. Manual
synonym growth still goes through the truth-gated `manage-synonyms` workflow.
In addition, `resume-tool review-edits commit` self-heals that project file for
accepted terminology edits: when a user accepts or edits a terminology proposal
that mirrors the employer's wording, the commit records the resume term as an
alias of the accepted employer term with `source: "accepted_edit"` provenance
and the caller-supplied timestamp. Rejected, skipped, auto-mode,
non-terminology, and malformed edits never grow aliases.

### Improve-phase edit sessions

Targeted resume improvements are written through the code-owned edit-session
orchestrator, not direct JSON edits. The flow is: build truthful
`ChangeProposal` records, prompt the user for a mode (`interactive`,
`review_at_end`, or `auto`), run `resume-tool review-edits open`, then loop through
`resume-tool review-edits prompt` and `resume-tool review-edits decide`.
Rejections and user-modified edits carry a structured `EditFeedbackReasonCode`
plus an optional note. Finally `resume-tool review-edits commit` applies the
hard gate and writes the tailored resume to the reported `working_path`;
`resume-tool validate-truth` remains the final truth check. Intentional
out-of-band edits must be accepted with `resume-tool review-edits reconcile`
before the session continues.

The loop records outcomes as `EditFeedback` via `resume-tool record-edit-feedback`
and can rebuild the deterministic preference profile with
`resume-tool refresh-preferences --now <iso>`. Confirmed user evidence is added
with `resume-tool add-evidence --confirmed --content ...`; `validate-truth`
classifies those near-match claims as `USER_CONFIRMED`, while actively refuted
claims remain `CONTRADICTED`. `UNSUPPORTED` means missing evidence, not an
active refutation; each claim carries a machine-readable `reason_code` such as
`missing_evidence`, `strong_evidence_overlap`, or `refuted_by_evidence`.

The full job-specific path is `original → base → structure → standard → refine
→ tailored → perfect`: refine/tailor proposes and commits truthful
job-alignment edits, while perfect only fits that tailored content to the
configured shape and page budgets.

## Release Notes

### Unreleased — perfect fit stage (RIT-T-0153)

- Documents the job-specific `perfect` stage after tailoring: `resume-tool fit`
  / `resume_build_perfect` writes `<name>-<job>-final.json` without mutating the
  `original` / `base` / `structure` / `standard` lineage.
- Clarifies that export enforces the rendered `max_pages` page hard gate after
  the fit pass.

### Unreleased — canonical structure stage (RIT-I-0019)

- Inserts the lossless `structure` stage into resume baselining, making the
  tracked lineage `original → base → structure → standard`.
- Adds shape analysis and `build-structure`: redundant skill/custom sections are
  merged into canonical skills, ambiguous sections are deferred, and writes are
  gated by content-ledger accounting plus whole-resume claim preservation.
- Keeps the wording pass behavior unchanged: `build-standard` now reads
  `structure ?? base ?? original`, projects canonical `structure` back to the
  BuildDoc read model, and writes `standard` as before.

### Package 0.9.0 / plugin 1.2.0 — test-run tightening (RIT-T-0126–0130)

- **Keyword hygiene gate** (`schemas.keyword_hygiene`): full requirement
  sentences are no longer scored as keywords. Applied at the matching scoring
  boundary and at job parse time, so `match` / `check-keywords` / `check-gaps`
  stop counting unmatchable prose in the denominator (fixes artificially
  depressed match scores and cluttered missing/non-injectable lists).
- **check-gaps degeneracy warning**: when the tailored and master resumes resolve
  to near-identical content, the report now warns that the injectable split is
  unreliable instead of presenting every miss as an unfixable gap.
- **set-active path normalization**: a leading `resume-kit/` on a user-supplied
  pointer is stripped, so cwd-relative and working-dir-relative paths resolve
  identically and `build-base` no longer fails on a doubled path.
- **check-best-practices quantification**: `MISSING_QUANTIFICATION` is capped and
  prioritized to the few bullets where a metric adds most (impact-verb bullets
  first), with a single `MISSING_QUANTIFICATION_MORE` note for the remainder —
  replacing the one-prompt-per-bullet wall.
- **job-hunter bridge**: reconciled three stale capability dispatch names left by
  the RIT-A-0005 rename.

### Package 0.8.0 / plugin 1.0.0 — ScoreDoc scoring projection + ATS-view report (RIT-I-0017)

- Separates the scoring representation (`ScoreDoc`) from the build representation
  (`ResumeDocument`) via the deterministic, offline `project_scoredoc`. All
  scoring and matching now read the zoned ScoreDoc (keyword index + segmented
  sections + extracted entities/YoE) rather than the raw resume JSON.
- Fixes the categorized-skills regression: skills in a `stringList` custom
  section are projected into the skills zone, so they earn the same
  keyword-placement credit as `additional.technicalSkills` (no placement penalty
  for categorizing skills).
- Adds the read-only **ats-view** "what the ATS sees" report, rendered off the
  ScoreDoc and identical across the CLI, MCP, API, and facade surfaces.

### Package 0.7.0 / plugin 1.0.0 — initial resume baselining (RIT-I-0016)

- Adds the initial `original → base → standard` baselining lineage as the
  mandatory pre-tailoring phase: `build-base` (auto structural fixes behind the
  claim-preservation gate), `analyze-best-practices` (job-independent report
  classifying each finding `auto_suggestible` vs `needs_user_input`), and
  `build-standard` (best-practices walkthrough behind the same gate). This was
  later extended by the `structure` stage.
- Makes `standard` the default tailoring input — active resolution is
  `standard ?? base ?? original` in the initial lineage, so tailoring and edit
  sessions operate on the best-practices-improved version rather than the raw
  ingest.
- The entire baselining path is deterministic and offline (no LLM, no network),
  proven end-to-end by the lineage integration test.

### Package 0.6.0 / plugin 0.7.0 — enforced edit loop (RIT-I-0015)

- Enforces the human-in-the-loop edit-session write gate across CLI, MCP, API,
  and facade surfaces; bulk unlogged writes and truth-failing accepted changes
  fail with machine-readable errors.
- Fixes truth semantics so `CONTRADICTED` is reserved for structural conflicts
  or active refutations, `UNSUPPORTED` means missing evidence, and every
  provenance claim includes a stable `reason_code`.
- Extends learning with edit feedback, preference refresh, user-confirmed
  evidence, specific-over-vague preference derivation, and project alias growth
  from accepted terminology edits.

## Building & publishing

Build the umbrella wheel and sdist locally with [`uv`](https://docs.astral.sh/uv/):

```bash
uv build            # produces dist/resume_kit-*.whl and dist/resume_kit-*.tar.gz
```

The wheel vendors all import packages (schemas, core, document-parser, job-parser,
ats, matching, policy, evidence, alignment, export, facade, cli, mcp, api, and the
job-hunter bridge) via Hatch `force-include`, so the shipped metadata declares only
third-party dependencies — no internal `resume-kit-*` requirements. The per-package
`pyproject.toml` files remain only for local `uv` workspace development.

Publishing to PyPI uses [Trusted Publishing](https://docs.pypi.org/trusted-publishers/)
(OIDC, no long-lived API tokens). The GitHub Actions workflow in
`.github/workflows/publish.yml` builds and publishes on a `v*` version tag; it is not
triggered by ordinary pushes. To cut a release, push a tag:

```bash
git tag v0.1.0
git push origin v0.1.0
```

As a manual fallback (also Trusted-Publishing-friendly), you can upload from a local
build with twine:

```bash
uv build
python -m twine upload dist/*
```

> `resume-kit` is published on PyPI at <https://pypi.org/project/resume-kit/>.
> Releases are cut by pushing a `vX.Y.Z` tag (Trusted Publishing via GitHub
> Actions); the `twine` commands above are the manual fallback.

## Status

Early development. Built by selectively porting proven behavior from
[Resume-Matcher](https://github.com/srbhr/Resume-Matcher) (Apache 2.0) into a clean, modular
architecture. Resume-Matcher is a **donor codebase and upstream reference**, not the product
architecture. See [`references/`](references/) for the upstream audit, reuse inventory, and
attribution.

## Language & distribution

Implemented in **Python** (the donor codebase and all extractable subsystems are Python:
Pydantic models, MarkItDown extraction, LiteLLM providers). Distribution targets **PyPI**, not
npm — see [ADR-0001](references/architectural-decisions/).

## Principles

- Deterministic parsing, checks, diffs, and scoring **before** any LLM reasoning; LLM usage is
  optional, explicit, and replaceable by local/no-LLM modes.
- **Never fabricate** employers, titles, dates, accomplishments, metrics, certifications, or
  experience. The user is the final authority over truth.
- Original resumes are preserved by default; every change ships with a structured diff, claim
  provenance, and a truth-validation report.

## Repository layout

```
packages/      core, schemas, document-parser, job-parser, matching, alignment,
               evidence, policy, ats, llm, export, cli, mcp, api
plugins/       resume-intelligence agent plugin
integrations/  job-hunter bridge
references/    upstream-audit.md, reuse-inventory.md, attribution.md, ADRs
tests/         fixtures, characterization, unit, integration, evals
```

## License

Apache 2.0. See [LICENSE](LICENSE) and [NOTICE](NOTICE).
