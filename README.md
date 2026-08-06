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

### Resume baselining (`original → base → standard`)

Before any job-specific tailoring, a resume moves through a fixed, deterministic
baselining lineage that produces three tracked versions:

```bash
resume-tool build-base                              # original → base (auto): strips PII, normalizes
                                                    #   presentation, behind the claim-preservation gate
resume-tool analyze-best-practices \                # job-independent best-practices report; each finding
  --resume resumes/resume-base.json                 #   is auto_suggestible or needs_user_input
resume-tool build-standard --answers answers.json   # base → standard: applies auto-suggestible rewrites
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
- **`standard`** — `base` after the generic best-practices walkthrough: every
  finding is classified `auto_suggestible` (a truthful rewrite is applied now) or
  `needs_user_input` (the user supplies real facts, e.g. a metric). Applied
  behind the same claim-preservation gate.

**All job-specific tailoring runs off `standard`, not `original`.** The active
resume resolves as `standard ?? base ?? original`, so once baselining has run,
downstream tailoring and edit sessions operate on the best-practices-improved
`standard` version by default. The lineage is fully deterministic and offline:
no LLM or network is touched on the baselining path.

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

## Release Notes

### Package 0.7.0 / plugin 1.0.0 — resume baselining (RIT-I-0016)

- Adds the `original → base → standard` baselining lineage as the mandatory
  pre-tailoring phase: `build-base` (auto structural fixes behind the
  claim-preservation gate), `analyze-best-practices` (job-independent report
  classifying each finding `auto_suggestible` vs `needs_user_input`), and
  `build-standard` (best-practices walkthrough behind the same gate).
- Makes `standard` the default tailoring input — active resolution is
  `standard ?? base ?? original`, so tailoring and edit sessions operate on the
  best-practices-improved version rather than the raw ingest.
- The entire baselining path is deterministic and offline (no LLM, no network),
  proven end-to-end by the `original → base → standard` lineage integration test.

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

> Note: `resume-kit` has **not** been published to PyPI yet. The commands above
> describe how a release would be cut once the project is ready.

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
