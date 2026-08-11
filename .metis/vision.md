---
id: resume-kit
level: vision
title: "Resume Intelligence Toolkit Product Vision"
short_code: "RIT-V-0001"
created_at: 2026-08-03T21:11:07.335788+00:00
updated_at: 2026-08-11T19:15:00.000000+00:00
archived: false

tags:
  - "#vision"
  - "#phase/draft"


exit_criteria_met: false
strategy_id: NULL
initiative_id: NULL
---

# Resume Intelligence Toolkit Vision

> **Rewritten 2026-08-11** to reflect the toolkit as actually built and shipped (resume-kit 0.15.3,
> plugin 1.8.3). The original 2026-08-03 draft described a pre-build spec ("not yet implemented") and a
> `freedom 0–10` alignment model that was superseded during construction. This version describes the
> real architecture: a deterministic, truth-gated, staged transformation pipeline with a human-in-the-loop
> edit-session. See "What Changed From the Original Vision" near the end for the delta.

## Purpose **[REQUIRED]**

Resume Intelligence Toolkit (resume-kit) is a reusable, trustworthy system for evaluating, comparing,
tailoring, and validating resume materials against specific jobs — without fabrication. It answers five
questions for a job seeker or a calling system:

- Can an ATS reliably parse this resume?
- How closely does this resume match a specific job, and why?
- Which relevant qualifications are missing or under-represented?
- What **truthful** changes would improve alignment, and can the user approve each one?
- Did the revised resume actually improve, and does it fit the page budget?

It serves both as a standalone local tool (CLI + agent plugin) and as the lower-level resume-intelligence
capability behind the `job-hunter` plugin. Its defining property is that every change is deterministic
where possible, evidence-backed, gate-checked, and user-authorized — the toolkit tailors resumes, it does
not invent careers.

## Product/Solution Overview **[CONDITIONAL: Product/Solution Vision]**

resume-kit is a Python 3.12 uv workspace distributed on PyPI as `resume-kit` (NOT npm; the donor is
Python — see the repository strategy section). It exposes one shared engine through four thin surfaces —
a `resume-tool` CLI (the authoritative surface the plugin skills drive), a FastAPI service, an MCP server,
and an agent plugin of single-responsibility skills — plus a library bridge for `job-hunter`. No business
rule lives only in a surface; surfaces adapt I/O and orchestrate user interaction over the same
capabilities.

The product is built as a **controlled-transformation system, not an unconstrained LLM rewriter.** Its
value comes from canonical models, deterministic analysis, explainable scoring, a staged version lineage
with a specific validation gate at each stage, structured evidence, a code-owned human-in-the-loop
edit-session with a hard write gate, claim provenance, and truth validation. LLM usage is optional,
confined to interpretation (mapping raw document text into the schema), and always sits between
deterministic rails.

The primary audience is an individual job seeker using `job-hunter` or the standalone tooling. Secondary
audiences are agent plugins, coding/desktop agents, and automation systems that need structured resume
analysis without duplicating resume-specific logic.

## Current State **[REQUIRED]**

**The toolkit is implemented, published, and in active use.** Phases 0–6 of the original roadmap plus a
large second wave of initiatives are complete and shipped (current release: resume-kit 0.15.3 / plugin
1.8.3 / marketplace 0.10.3 on PyPI + the plugin marketplace). What exists today:

- **Canonical schemas & core contracts** (`packages/schemas`, `packages/core`): `ResumeDocument`,
  canonical `Resume`, `JobDescription`, `CandidateEvidence`, `ChangeProposal`, `ScoreDoc`, analysis
  reports, provenance, and a stable interface-response envelope with structured error codes.
- **Deterministic ingest boundary** (`packages/document-parser`, `packages/ats`): a no-LLM
  `extract-text` primitive (markitdown/pdfminer/python-docx), ONE confined interpretation agent that maps
  text→schema, and a `validate-faithfulness` **hard gate** (bullet-count / dropped-span / altered-field
  hard-fails; non-ASCII and token warnings by design). Code-owned `ProjectConfig` (`init` / `set-active`)
  records active resume/job/evidence and source paths.
- **Deterministic matching & analysis** (`packages/matching`, `packages/ats`, `packages/terms`): exact +
  synonym-alias keyword matching (stemming OFF by design), explainable job-match scoring, ATS structural
  checks, a job-independent best-practices analyzer, "what the ATS sees" reporting, and gap analysis with
  a shared injectability proof contract (master resume and/or confirmed learning-evidence).
- **A staged version lineage** (the spine of the product): `original → base → structure → refine →
  tailored → perfect → export`, each stage owning a specific gate (below).
- **ScoreDoc/BuildDoc separation** (`RIT-A-0002`): scoring reads a deterministically-projected `ScoreDoc`
  (zoned, recency-weighted) rather than the build representation, so scoring and building never drift.
- **Code-owned edit-session + hard write gate** (`RIT-A-0001`, `packages/facade`): the ONLY sanctioned
  way to mutate a resume. It enforces a logged decision per change path and refuses CONTRADICTED claims;
  modes are interactive / review-at-end / auto.
- **Truth semantics**: claims are classified verified / supported / user-confirmed / ambiguous /
  UNSUPPORTED / CONTRADICTED with a `reason_code`; validation is synonym- and inflection-aware.
- **Preference learning** (`packages/feedback`, no-LLM): an append-only edit-feedback log, diff-aware
  preference derivation, Preference-RAG retrieval, and a pluggable heuristic ranker with a truth
  hard-block.
- **Composable flows** (plugin skills): `prepare-base-resume` (Flow 1), `ingest-job` (Flow 2),
  `tailor-resume` (Flow 3), `finalize-resume` (Flow 4), and `complete-resume-flow` (sequences 1–4),
  learning-first, with a durable full-resume evidence seed.
- **Perfect/fit + export** (`packages/export`): job-aware budget enforcement via ranked, decision-driven
  trims (compress-before-remove, no truncation), a rendered page-budget hard gate with an auditable
  override, and deterministic ReportLab (PDF) + python-docx (DOCX) export with no Chromium/frontend.
- **Uniform verb-noun skill lexicon and shared change-application runbook** (`RIT-A-0005`).

Known open work is tracked in Metis as backlog bugs and the discovery-phase initiative RIT-I-0025
(canonical post-tailoring state/path/fit model). The toolkit is not "done" — it is a working product with
an active hardening backlog.

## Future State **[REQUIRED]**

resume-kit remains the canonical resume analysis and controlled-transformation layer for local and
agent-driven job search. Near-to-mid-term direction:

- **First-class post-tailoring state model (RIT-I-0025):** explicit `tailored` / `final` pointers, a
  job-scoped edit-session, and a `fit` step that consumes the committed tailored resume rather than
  re-resolving baseline lineage. This closes the current highest-value engine gap.
- **Robust custom-section handling:** custom/non-standard sections are always omitted from output and
  their content seeded into evidence first — never carried into the rendered resume, never silently lost.
- **Iterative editing without friction:** multiple edit rounds on one resume without tamper-wedge
  recovery dances; the truth gates stay, the incidental safety checks that block normal iteration are
  simplified away.
- **Diagnosability without leakage:** internal errors are dumped to a local diagnostics sink the user
  controls, while transported responses stay content-free (no exception strings that could leak secrets).
- **`job-hunter` consumption** through the library bridge / CLI, with the toolkit returning structured
  results, reports, questions, provenance, and artifact references — never mutating `job-hunter` state.

Longer term: optional hosted API usage with strict retention/privacy controls, broader schema support,
and richer explanations — without weakening the local-first, deterministic, truth-safety model.

## Major Features **[CONDITIONAL: Product Vision]**

- **Canonical data models** shared across plugin, MCP, CLI, API, and packages.
- **Deterministic parsing** for PDF/DOCX/Markdown/text and job descriptions, behind a faithfulness gate.
- **ATS compatibility checks** (structure, sections, contact/date detection, keyword placement, skills
  readability, Unicode risk) and a "what the ATS sees" report.
- **Explainable job-match scoring** over required/preferred qualifications, keywords, recency, and
  placement — never rewarding keyword repetition alone.
- **Synonym-aware matching** with an agent-grown, truth-gated alias index and employer-terminology
  mirroring suggestions.
- **Staged, gated version lineage** (`original → base → structure → refine → tailored → perfect`).
- **Code-owned human-in-the-loop edit-session** with a hard write gate, per-change decisions, evidence,
  score-impact, and truth validation.
- **Truth validation & claim provenance** (verified / supported / user-confirmed / ambiguous /
  unsupported / contradicted); tailoring may not emit unsupported claims.
- **Missing-requirement interview** (RIT-I-0022): a truth-gated elicit-and-prove loop with durable answer
  memory so future jobs never re-ask.
- **Deterministic preference learning** and heuristic ranking of edit candidates (truth-blocked).
- **Perfect/fit budget enforcement** and **deterministic PDF/DOCX export** with a rendered page gate.
- **Composable flows** and a single-purpose, self-gating skill surface.

## The Version Lineage and Its Gates

The heart of the product is a staged transformation where each stage is immutable once written and guarded
by a specific deterministic gate:

- **original** — faithful, lossless capture of the source document. Gate: `validate-faithfulness`
  (hard-fail on dropped spans / bullet-count mismatch / altered fields). Non-ASCII is preserved verbatim
  and normalized only at export. Custom sections are retained here.
- **base** — structural normalization (strip PII/placeholders, normalize dates/formatting). Gate:
  claim-preservation. Cosmetic normalization must be claim-neutral.
- **structure** — lossless canonicalization to the jsonresume-style canonical schema. Gate:
  content-ledger + cross-section claim preservation. Custom sections are omitted from output and their
  content is seeded to evidence first (never carried into the resume, never silently lost).
- **refine** — job-independent wording improvements (mechanical best-practice rewrites + truthful,
  user-supplied facts). Gate: best-practices analyzer + claim preservation; destructive rules are
  reclassified out.
- **tailored** — job-aware, evidence-backed changes applied ONLY through the edit-session hard write gate
  (logged decision per path, refuse CONTRADICTED). Missing-but-true keywords are injectable only when
  proved by a master resume and/or confirmed evidence.
- **perfect / fit** — job-aware budget enforcement via ranked trims (compress before remove, no
  truncation). Gate: content ledger + rendered page-budget hard gate (auditable override).
- **export** — deterministic PDF/DOCX render; non-ASCII normalized here.

## Safety Model: Deterministic, Truth-Gated, Human-Authorized

The safety model is NOT a freedom dial; it is a set of enforced invariants:

- **Deterministic-first.** Extraction, ATS checks, matching, scoring inputs, diffs, ledgers, and
  validation run without an LLM. The one LLM touchpoint is a confined interpretation agent that maps raw
  document text into the schema, sandwiched between the deterministic extractor and the faithfulness gate.
- **Truth gates everywhere.** Claims are classified with provenance and a reason code; tailoring may not
  emit UNSUPPORTED claims and must refuse CONTRADICTED ones. Validation is synonym/inflection-aware.
- **Code-owned edit-session with a hard write gate.** Every mutation is logged, decided per path, and
  gate-checked before write. Direct hand-editing of the working JSON is unsupported unless reconciled.
- **Never fabricate.** Employers, titles, dates, responsibilities, metrics, certifications, education,
  clearances, and technical/management/industry experience are never invented.
- **Preserve originals.** The original is immutable and faithful; every stage produces a new version plus
  structured diffs, provenance, and validation reports.
- **User is the final authority** over claim truth, voice, saving, and use.

Historical note: the original vision proposed a `freedom: 0–10` alignment scale with LLM auto-rewrite at
higher levels. That model was **superseded** during construction — LLM auto-rewrite was disabled
(RIT-I-0011) in favor of the deterministic, truth-gated edit-session above. Freedom-level descriptors
survive only vestigially as scope tags on a few specific change types (e.g. terminology/summary/education
edits); they are not the product's control model.

## Architecture and Engine Boundary

```text
Agent skills --\
MCP server ------> Resume Intelligence Core (packages/*)
CLI ------------/     canonical models · parsing contracts · ATS · matching · scoring (ScoreDoc)
API -----------/      lineage stages · edit-session + hard write gate · evidence · truth validation
job-hunter ---/       preference learning · export contracts
```

The core owns all business rules; surfaces only adapt I/O and orchestrate interaction. Dependencies
(LLM providers, storage) are injected explicitly so the same service runs from plugin, MCP, CLI, API,
tests, and local or hosted providers. `resume-tool` (CLI) is the authoritative surface the plugin skills
drive. The MCP server is registered and available but is a secondary surface (kept, not currently
invested in — see the tracked MCP-surface decision). The `job-hunter` bridge is a Python library import.

## Package & Surface Architecture

`packages/`: `schemas`, `core`, `document-parser`, `job-parser`, `matching`, `ats`, `terms`, `scoring`
(ScoreDoc projection + shape/ledger), `alignment` (diff apply/verify), `evidence`, `policy`, `feedback`,
`facade` (capabilities + edit-session), `export`, `cli`, `mcp`, `api`. `plugins/resume-intelligence`
holds the single-responsibility skills (verb-noun lexicon, `RIT-A-0005`) and `_shared` gate/pointer docs.
`integrations/job-hunter` is the library bridge. Donor code lives behind interfaces with attribution.

## Business Requirements Overview **[CONDITIONAL: Business Vision]**

- Provide reusable resume intelligence that powers `job-hunter` without coupling to its job-search state.
- Preserve trust: never fabricate, never overwrite originals, explain every score, require human authority
  over truth and final use.
- Local-first, deterministic no-LLM where practical, explicit privacy boundaries.
- Reuse proven open-source behavior from Resume-Matcher where safe/legal/maintainable; avoid inheriting
  its web-app architecture.
- Deliver the same core through skills, MCP, CLI, API, and library integration with no rule duplicated in
  a surface.

## Success Criteria **[REQUIRED]**

MVP success — **achieved**: the toolkit parses real resume variants with no meaningful content loss,
detects ATS risks, compares variants against a job, explains the strongest match, identifies missing
qualifications, produces truthful tailored revisions through a gated edit-session, avoids unsupported
claims, shows every change via diff + provenance, produces before/after score deltas, enforces a page
budget, exports PDF/DOCX deterministically, and is consumable by `job-hunter` — all without inheriting
Resume-Matcher's web/persistence/tracker architecture. (Verified end-to-end via the automation test run
against a real custom-section resume at v0.15.2.)

Ongoing success: the post-tailoring state model (RIT-I-0025) lands; custom-section omission + evidence
seeding is the default; iterative editing is friction-free; and the backlog of hardening bugs is worked
down without weakening any truth or faithfulness gate.

## Principles **[REQUIRED]**

- Use Resume-Matcher as a donor/reference, not the permanent architecture.
- Never fabricate; require evidence or user confirmation before broadening or adding claims.
- Prefer deterministic parsing, checks, diffs, validation, and scoring before any LLM reasoning.
- Explain every score with dimensions, evidence, gaps, and recommendations.
- Preserve originals; produce new versions with diffs, provenance, and validation.
- Keep the user the final authority over truth, voice, and use.
- Keep skills thin; put contracts, scoring rules, safety policy, and executable logic in packages.
- Keep `job-hunter` orchestration separate from resume-intelligence responsibilities.
- Apply dependency inversion; protect ported behavior with tests before changing it.
- One authoritative surface (CLI); no business rule lives only in a surface.

## Constraints and Technical Risks **[REQUIRED]**

- No guarantee of ATS outcomes or reproduction of proprietary vendor scores.
- No automatic application submission, job-board scraping, job-search state, or hiring decisions.
- Generated claims must trace to the source resume, validated profile, approved evidence, or a direct
  user answer.
- Remote LLM calls are opt-in, disclosed, and avoidable via local-model or deterministic no-LLM modes.
- Generated artifacts are explicit outputs and never overwrite originals by default.
- Scoring requires presence + meaningful support + placement + aligned scope, not keyword repetition.
- Open technical risks (tracked in Metis backlog): base-stage non-ASCII handling vs the claim gate; the
  post-tailoring pointer model (RIT-I-0025); schema strictness vs real "date-bucket" resume shapes; and
  edit-session iteration ergonomics. None weaken the core truth/faithfulness invariants.

## What Changed From the Original Vision (2026-08-03 → 2026-08-11)

- **"Not yet implemented" → shipped.** Phases 0–6 plus initiatives RIT-I-0008..0024 are complete and
  published (0.15.3).
- **`freedom 0–10` alignment model → deterministic truth-gated edit-session.** LLM auto-rewrite was
  disabled (RIT-I-0011); freedom levels survive only as vestigial change-scope tags.
- **New architecture the original didn't name:** the staged version lineage (`original→base→structure→
  refine→tailored→perfect`) with per-stage gates; ScoreDoc/BuildDoc separation (RIT-A-0002); the
  code-owned edit-session + hard write gate (RIT-A-0001); the deterministic ingest boundary + faithfulness
  gate (RIT-I-0014); the synonym/alias engine (RIT-I-0008..0010); preference learning (RIT-I-0013); the
  missing-requirement interview (RIT-I-0022); and composable flows (RIT-I-0023/0024).
- **Skill lexicon** moved to the uniform verb-noun naming (RIT-A-0005): e.g. `extract-resume`→
  `parse-resume`, `improve-resume-section`→`update-*`, plus `check-*`/`update-*`/`validate-facts` families.
- **Distribution** is PyPI (`resume-kit`), Python 3.12 uv workspace — not npm (ADR-0001).
- **Custom sections** are always omitted from output and seeded to evidence (decided 2026-08-11).
</content>
