---
name: parse-job
description: >
  Parse a job posting (pasted text, URL content, or a PDF/DOCX/MD/text file)
  into the canonical resume-kit JobDescription JSON, with structured requirements
  and skill keywords. This skill ORCHESTRATES a pipeline: for file inputs,
  `resume-tool extract-text <file>` pulls the raw text deterministically (no LLM);
  pasted text / URL content is used directly. A confined interpretation subagent
  then maps the text into the JobDescription schema, and the result is recorded
  with `resume-tool set-active --job`. The agent is an interpreter, not the
  extractor. Run FIRST whenever another skill or tool needs a JobDescription but
  you only have a posting.
---

> **Renamed:** `parse-job` was `job-to-json` before v1.0.0 (see RIT-A-0005).


# parse-job — build a JobDescription from a posting

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** the **job posting** as pasted text, a URL's content, or a
  PDF/DOCX/MD/text file — provided by the caller.
- **If it is missing:** STOP and ask the caller for the posting text, URL, or
  file. There is no upstream skill — this skill is itself the first step that
  produces the `JobDescription` JSON others depend on.

## Purpose

`check-structure`, `check-keywords`, and `check-gaps` score a
resume **against a JobDescription**. Deterministic text extraction only captures
the raw text — it does NOT populate the structured `requirements` and `keywords`,
so `skills_coverage` comes back `0`. This skill fixes that: a confined
interpretation subagent extracts the structured skills/requirements from the
posting so scoring is meaningful — no LLM provider required.

Same shape as `parse-resume`: extraction is deterministic, interpretation is
confined to a subagent, and the pointer is recorded by code (`set-active`), not by
hand-editing `config.json`.

## Which gate applies

`resume-tool validate-faithfulness` targets a **`ResumeDocument`** — it is the
authoritative machine gate for `parse-resume`, **not** for job postings. Do NOT
force the resume faithfulness gate on a `JobDescription`. For jobs, the
faithfulness discipline is enforced by the **prose Extraction gates below**, which
the interpretation subagent must follow (chiefly: `raw_text` is verbatim and no
skills/requirements are invented). If a JSON-schema round-trip is available
(`JobDescription.model_validate(...)`), run it — that is a schema check, still not
the resume faithfulness gate.

## Before you start: read prior learnings

Read `resume-kit/learning/parse-job.md` (if present) first, and append any new
gotcha you hit so future runs benefit.

## Steps (orchestration spine)

1. **Ensure the working dir exists.** If `resume-kit/` is not present, run:

   ```
   resume-tool init
   ```

   (`resume-tool init [--root .]` is idempotent.)

2. **Obtain the posting text:**
   - For a **file input** (PDF/DOCX/MD/text): extract deterministically —

     ```
     resume-tool extract-text <file>
     ```

     `resume-tool extract-text <file|->` handles PDF, DOCX, Markdown, and plain
     text with the base install; `-` reads stdin bytes. *Fallback only:* if
     `resume-tool` is unreachable, read the file with your own capability — do not
     improvise binary parsing.
   - For **pasted text or URL content**: use it directly — **skip extraction**.
     There is no file to extract; the caller-provided text IS the source.

3. **Dispatch the confined interpretation subagent** (see **Interpretation
   subagent contract** below) with the posting text, the JobDescription schema,
   the Extraction gates, and the target save path. It returns a **candidate JSON**
   path + summary.

4. **Validate the candidate against the schema** (not the resume faithfulness
   gate — see "Which gate applies"): `JobDescription.model_validate(json.load(...))`
   if the package is importable, else structurally against the schema below.

5. **Save** the candidate to `resume-kit/jobs/<orig-basename>-original.json` (or a
   stable slug from the title + company if the posting was pasted), then record it
   as the active job and remember the source:

   ```
   resume-tool set-active --job resume-kit/jobs/<orig-basename>-original.json --job-source <file>
   ```

   Use `--job-source <file>` only when there is a source file; for pasted/URL
   input, run `set-active --job <path>` without `--job-source`. **Do NOT hand-edit
   `config.json`** — `set-active` is code-owned and preserves unknown keys.

## Interpretation subagent contract

Run the interpretation as a confined subagent so the full posting text stays out
of the main context.

- **Inputs the subagent receives:**
  1. the **posting text** (from `extract-text`, or the pasted/URL text directly),
  2. the **JobDescription schema** (below),
  3. the **Extraction gates** (below), and
  4. the **target save path** (`resume-kit/jobs/<orig-basename>-original.json` or
     the slug).
- **The subagent's ONLY job** is text → `JobDescription` JSON mapping. It does not
  extract from binaries, does not touch `config.json`, and does not run
  `set-active`.
- **Output the subagent returns:** the **candidate JSON path** + a short
  **summary** (counts of required/preferred/keywords). It does not stream the full
  posting back into the main conversation.
- **Hard rule:** the subagent produces a **candidate**; the orchestrator (this
  skill) validates it and only then records it via `set-active`. The subagent must
  not treat its output as active until the orchestrator has recorded it.

## Extraction gates — accurate, not invented (for the interpretation subagent)

- **`raw_text` is verbatim** — the whole posting, unaltered.
- **Do not invent** skills, requirements, or seniority the posting does not state.
  Every keyword must actually appear in (or be an obvious surface form of) the
  posting text.
- **Classify by the posting's own framing:** items under "Requirements",
  "Must have", "You have" → `kind: "required"`; items under "Preferred", "Nice to
  have", "Bonus", "Plus" → `kind: "preferred"` (put these in `qualifications`).
  When unclear, prefer `required` only for explicitly mandatory items.
- **Keywords are concrete tokens** (e.g. `React`, `TypeScript`, `PostgreSQL`,
  `CI/CD`, `multi-tenant`), matching how they appear on resumes. Normalize
  trivial variants (e.g. `Node`/`Node.js`) but do not drop distinct skills.
  **Never put a full requirement sentence in `keywords` or in a
  `requirements[].keywords` list.** A requirement's `text` may be a whole
  sentence (that is fine — it is for display), but its `keywords` must be the
  concrete tokens extracted from that sentence. A deterministic hygiene gate
  drops sentence-shaped entries from the scored keyword set, so prose there is
  silently discarded — extract the tokens yourself so nothing matchable is lost.
- Leave `title`/`company`/`location` from the posting; empty string / `null` if
  absent — do not guess.

## Learnings & gotchas (READ THESE)

- **`kind` uses lowercase values**: `"required"` or `"preferred"` (not the enum
  names). Wrong casing fails validation.
- **`skills_coverage` depends on this skill.** If a downstream ATS/match score
  shows `skills_coverage: 0` with an obviously-matching resume, the JobDescription
  was probably raw-text-only — re-run this skill so `keywords`/`requirements` are
  populated.
- **`keyword_match` vs `skills_coverage`:** `keyword_match` scores whole-term hits
  against `raw_text` (works even with raw-text-only jobs); `skills_coverage` needs
  the structured `keywords` list. Populate both by filling `raw_text` AND
  `keywords`.
- Round-trip validate: `JobDescription.model_validate(json.load(...))`.

## JobDescription schema

```jsonc
{
  "title": "",
  "company": "",
  "location": null,
  "raw_text": "the ENTIRE posting, verbatim",
  "summary": "",
  "requirements": [
    { "text": "requirement as written or lightly normalized",
      "kind": "required",                         // "required" | "preferred"
      "keywords": ["React", "TypeScript"] }
  ],
  "qualifications": [
    { "text": "preferred/nice-to-have item",
      "kind": "preferred",
      "keywords": ["Docker"] }
  ],
  "keywords": ["React", "TypeScript", "PostgreSQL", "CI/CD"]   // flat union of all skill tokens
}
```

## resume-kit working directory (file convention)

State lives under `resume-kit/` in the current project. Create it with
`resume-tool init` rather than by hand:

```
resume-kit/
├── config.json          # pointers + preferences (active_resume, active_job, ...) — CODE-OWNED, use set-active
├── resumes/<orig-basename>-original.json   # parse-resume output
├── jobs/
│   └── <orig-basename>-original.json        # THIS skill's output
├── working/<session-id>/resume.json         # resume currently being changed/reviewed
└── learning/<skill>.md                      # accumulated hints (read first, append)
```

- **Save to** `resume-kit/jobs/<orig-basename>-original.json` (source file name
  without extension). If the posting was pasted (no file), use a stable slug from
  the job title + company, e.g. `staff-fullstack-acme-original.json`. The name is
  the id back to the source.
- Record `active_job` (and, for file inputs, the source path) with
  `resume-tool set-active --job ... [--job-source ...]` — never by hand-editing
  `config.json`.

## Command reference (exact signatures)

- `resume-tool init [--root .]` — idempotent scaffold of `resume-kit/`.
- `resume-tool extract-text <file|->` — deterministic text extraction
  (docx/pdf/md/txt), no LLM; `-` reads stdin bytes. (File inputs only — skip for
  pasted text / URL content.)
- `resume-tool set-active [--job <json>] [--job-source <file>] [--root .]` —
  records `active_job` + source path in `config.json` (code-owned; preserves
  unknown keys).

Note: `resume-tool validate-faithfulness` targets a `ResumeDocument` and does not
apply here — see "Which gate applies".

## Output

The saved path to a valid `JobDescription` JSON with populated `requirements`,
`qualifications`, and `keywords`, recorded as `active_job` via `set-active` —
ready for `check-structure`, `check-keywords`, and `check-gaps`
to produce meaningful keyword-match AND skills-coverage scores.
