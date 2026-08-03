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
