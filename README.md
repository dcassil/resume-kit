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
