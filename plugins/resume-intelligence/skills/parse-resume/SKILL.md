---
name: parse-resume
description: >
  Parse a resume file (PDF, DOCX, Markdown, or plain text) into the canonical
  resume-kit ResumeDocument JSON, faithfully and losslessly. This skill
  ORCHESTRATES a deterministic pipeline: `resume-tool extract-text` pulls the raw
  text (no LLM), a confined interpretation subagent maps that text into the
  schema, and `resume-tool validate-faithfulness` HARD-GATES the result before it
  is saved. The agent is an interpreter between two deterministic gates — not the
  extractor and not the self-checker of record. Run FIRST whenever another
  resume-intelligence skill or tool needs a resume but you only have a document
  file.
---

> **Renamed:** `parse-resume` was `resume-to-json` before v1.0.0 (see RIT-A-0005).


# parse-resume — build a ResumeDocument from a resume file

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** a **source resume file path** (PDF, DOCX, Markdown, or
  plain text) provided by the caller.
- **If it is missing:** STOP and ask the caller for the source resume file path.
  There is no upstream skill — this skill is itself the first step that produces
  the `ResumeDocument` JSON others depend on.

## Purpose

Every resume-intelligence capability that takes a resume (check-structure,
check-keywords, validate-facts, select-resume,
compare-versions, check-gaps, extract-evidence,
export-resume) operates on a structured **ResumeDocument JSON** — not on a raw
PDF/DOCX/MD file. This skill turns a document into that JSON.

**You are the interpreter, not the converter.** The pipeline is deterministic on
both ends:

1. `resume-tool extract-text <source>` performs the extraction (no LLM, no
   guessing at binary formats).
2. A confined interpretation subagent maps the **extracted text** into the
   `ResumeDocument` schema. This is the only step where judgment is applied.
3. `resume-tool validate-faithfulness` is the **authoritative machine gate** — it
   exits non-zero if the JSON drifts from the source, and nothing is saved until
   it passes.

Your role is confined to step 2. Do not treat your own eyeballing as the final
faithfulness check — the CLI gate is.

## Before you start: read prior learnings

Read `resume-kit/learning/parse-resume.md` (if it exists) first — it accumulates
gotchas from earlier runs. When you discover a NEW gotcha, append it there so the
next agent does not rediscover it.

## Steps (orchestration spine)

1. **Ensure the working dir exists.** If `resume-kit/` is not present in the
   current project, run:

   ```
   resume-tool init
   ```

   (`resume-tool init [--root .]` is idempotent — safe to run even if some of
   `resume-kit/` already exists. It scaffolds `config.json`, `resumes/`, `jobs/`,
   `working/`, and `learning/`.)

2. **Extract text deterministically** from the source file:

   ```
   resume-tool extract-text <source>
   ```

   `resume-tool extract-text <file|->` handles PDF, DOCX, Markdown, and plain
   text with the base install's bundled libraries — no optional extra and no LLM
   provider required. `-` reads bytes from stdin. Capture the extracted text; it
   is the ONLY input the interpretation subagent gets.

   *Fallback only:* if `resume-tool` is genuinely unreachable, read the file with
   your own file-reading capability. Do NOT improvise raw binary/XML parsing.
   Raw file reading is the exception, never the primary path — if neither works,
   tell the user rather than guessing.

3. **Dispatch the confined interpretation subagent** (see **Interpretation
   subagent contract** below). Hand it the extracted text, the ResumeDocument
   schema, the Faithfulness guidance, and the target save path
   `resume-kit/resumes/<orig-basename>-original.json`. It returns a **candidate
   JSON** — but does NOT write `-original.json` yet.

4. **Run the blocking faithfulness gate** against the candidate:

   ```
   resume-tool validate-faithfulness --source <source> --json <candidate.json>
   ```

   This is a HARD GATE. It exits **non-zero** and prints a `FaithfulnessReport`
   JSON when the candidate drifts from the source. Error-level findings
   (`BULLET_COUNT_MISMATCH`, `DROPPED_SPANS`, `ALTERED_FIELD`) **fail** the gate;
   warning-level findings (`SECTION_COUNT_MISMATCH`, `DROPPED_TOKENS`,
   `ADDED_TOKENS`, `NON_ASCII`) do not fail but should be reviewed.

   Write the candidate to a temporary path (e.g. under
   `resume-kit/working/<session-id>/`) so you can pass it to the gate before it
   becomes the immutable `-original.json`.

5. **On gate FAIL — loop once.** Hand the `FaithfulnessReport` findings back to
   the interpretation subagent with instruction to correct exactly those drifts
   (add the dropped bullets/spans, restore the altered field, etc.), then re-run
   step 4 on the corrected candidate. Loop **at most once**. If the gate still
   fails after this single retry, **surface the report findings to the user** and
   stop — do not save a resume that fails the gate.

6. **On gate PASS — commit the result:**
   - Move/write the passing candidate to
     `resume-kit/resumes/<orig-basename>-original.json` (immutable, faithful).
   - Record it as the active resume and remember the source path:

     ```
     resume-tool set-active --resume resume-kit/resumes/<orig-basename>-original.json --source <source>
     ```

     `set-active` normalizes the path, so either the cwd-relative form shown
     above (`resume-kit/resumes/...`) or the working-dir-relative form
     (`resumes/...`) is accepted and stored as the same pointer.

   **Do NOT hand-edit `config.json`.** `set-active` is code-owned and preserves
   unknown keys; always use it to record pointers and source paths.

## Interpretation subagent contract

The interpretation step MUST run as a confined subagent so the large intermediate
document text stays out of the main context.

- **Inputs the subagent receives:**
  1. the **extracted text** (from `extract-text`),
  2. the **ResumeDocument schema** (below),
  3. the **Faithfulness guidance** (below),
  4. the **target save path**
     (`resume-kit/resumes/<orig-basename>-original.json`), and — on a retry —
  5. the **`FaithfulnessReport` findings** from the failed gate.
- **The subagent's ONLY job** is text → `ResumeDocument` JSON mapping. It does not
  extract from binaries, does not touch `config.json`, and does not run
  `set-active`.
- **Output the subagent returns:** the **candidate JSON path** + a short
  **summary** (counts of roles/bullets/sections) + the gate result once known. It
  does NOT stream the whole resume back into the main conversation.
- **Hard rule:** the subagent MUST NOT write `-original.json` until
  `validate-faithfulness` passes. It produces a candidate; the orchestrator (this
  skill) runs the gate and only then promotes the candidate to `-original.json`.

## Faithfulness guidance (for the interpretation subagent)

These rules tell the subagent HOW to map text into the schema without introducing
drift. They are **guidance**; `resume-tool validate-faithfulness` is the
**authoritative machine gate** that decides pass/fail. Follow the guidance so the
gate passes on the first try.

- **Never invent, embellish, summarize, shorten, or paraphrase.** Every bullet,
  sentence, and phrase is copied **verbatim**.
- **Never drop content.** Every job, bullet, date, employer, title, school,
  degree, skill, language, certification, award, project, and section in the
  source MUST appear in the JSON.
- **Preserve facts exactly**: employer names, job titles, institutions, degrees,
  dates/date-ranges, locations, URLs, and metrics — character-for-character
  (including the exact date format).
- **Preserve order** — keep sections, jobs, and bullets in source order.
- **No merging or splitting** of bullets or entries.
- **Anything that does not fit the standard sections goes into `customSections`**
  (never discard it) — a `stringList` (lines/bullets) or `text` block.
- **Leave unknown optional fields empty** (`""`, `null`, or `[]`) — do not guess
  emails, phones, links, or dates that are not present.
- Before returning the candidate, **self-check** against the same intent the gate
  enforces: count the bullets per job in the extracted text and in the candidate
  JSON and confirm they match; confirm every section heading maps to a field or a
  `customSections` entry. This self-check reduces gate failures but does not
  replace the gate.

If the source is ambiguous/unreadable in places, transcribe what is present and
tell the user — never fill gaps with invented content.

## Learnings & gotchas (from real conversions — READ THESE)

- **`sectionType` uses lowercase serialized values**, NOT the enum names:
  `"text"`, `"stringList"`, `"itemList"` (never `TEXT`/`STRING_LIST`). Wrong
  casing fails schema validation.
- **`CustomSection` has no `displayName` field.** Its only fields are
  `sectionType`, `strings`, `text`, `items`. The section's dict key is its id;
  put the human heading nowhere schema-invalid — if you need the heading text,
  keep it inside the content (or a `text` block).
- **`id` is a plain 1-based integer** per list (workExperience, education,
  personalProjects, customSection items).
- **Skills:** put a flat, ATS-friendly list in `additional.technicalSkills`
  (this feeds scoring). If the source groups skills by category
  (Frontend/Backend/…), ALSO preserve the categorized lines verbatim in a
  `customSections` `stringList` so nothing is lost.
- **Non-ASCII punctuation is a real ATS risk.** Résumés often use `·` middots,
  “curly quotes”, en/em dashes, and `~`. The ATS engine flags these
  ("Non-ASCII characters detected — some ATS systems may mis-parse them"), and
  `validate-faithfulness` emits a `NON_ASCII` **warning** for them. Do NOT
  silently rewrite them in the `-original.json` (that would violate the gates and
  can trip `ALTERED_FIELD`/`DROPPED_SPANS`) — preserve verbatim; normalization is
  an *alignment/export* decision, not a conversion one.
- **Sub-headed groupings** like "Ventures & Consulting" / "Professional
  Experience" that bucket multiple roles: put each role as its own
  `workExperience` entry, and preserve any intro/among-the-group text as a small
  `customSections` `text` block so it is not lost.
- **A "Career Break" line** with a date range and no bullets is still content:
  add it as a `workExperience` entry (title = the line, `company: ""`,
  `description: []`).
- **Always round-trip validate** the schema before handing the candidate to the
  gate: `ResumeDocument.model_validate(json.load(...))`. If you cannot import the
  package, validate structurally against the schema below. Schema validity is
  separate from faithfulness — the candidate must pass BOTH.

## ResumeDocument schema

```jsonc
{
  "personalInfo": {
    "name": "", "title": "", "email": "", "phone": "", "location": "",
    "website": null, "linkedin": null, "github": null
  },
  "summary": "",
  "workExperience": [
    { "id": 1, "title": "", "company": "", "location": null, "years": "",
      "description": ["bullet 1 verbatim", "bullet 2 verbatim"] }
  ],
  "education": [
    { "id": 1, "institution": "", "degree": "", "years": "", "description": null }
  ],
  "personalProjects": [
    { "id": 1, "name": "", "role": "", "years": "", "github": null,
      "website": null, "description": ["bullet verbatim"] }
  ],
  "additional": {
    "technicalSkills": [], "languages": [],
    "certificationsTraining": [], "awards": []
  },
  "customSections": {
    "<key>": {
      "sectionType": "stringList",           // exactly one of: "text" | "stringList" | "itemList"
      "strings": ["line verbatim"],          // when sectionType == "stringList"
      "text": null,                          // when sectionType == "text"
      "items": null                          // when sectionType == "itemList": [{title, subtitle, location, years, description:[...]}]
    }
  }
}
```

## resume-kit working directory (file convention)

All resume-kit state lives under `resume-kit/` in the current project. Create it
with `resume-tool init` (step 1) rather than by hand:

```
resume-kit/
├── config.json          # pointers + preferences (active_resume, active_job, ...) — CODE-OWNED, use set-active
├── resumes/
│   └── <orig-basename>-original.json   # THIS skill's output — immutable, faithful
├── jobs/
│   └── <orig-basename>-original.json   # parse-job's output
├── working/
│   └── <session-id>/resume.json        # the candidate + the mutable copy being changed/reviewed
└── learning/
    └── <skill>.md                      # accumulated hints; read first, append when you learn something
```

- **Save the passing conversion to**
  `resume-kit/resumes/<orig-basename>-original.json`, where `<orig-basename>` is
  the source file name without extension (e.g. `resume-d.pdf` →
  `resume-kit/resumes/resume-d-original.json`). The `-original.json` name is the
  **id back to the source file** and marks it as the untouched conversion — never
  edit it in place, and never create it before the gate passes.
- To then review or modify a resume, COPY it to
  `resume-kit/working/<session-id>/resume.json` and work on the copy; leave the
  `-original.json` pristine.
- Record the saved path and source with `resume-tool set-active` (never by
  hand-editing `config.json`).

## Command reference (exact signatures)

- `resume-tool init [--root .]` — idempotent scaffold of `resume-kit/`.
- `resume-tool extract-text <file|->` — deterministic text extraction
  (docx/pdf/md/txt), no LLM; `-` reads stdin bytes.
- `resume-tool validate-faithfulness --source <file|-> --json <ResumeDocument.json>`
  — HARD GATE; exits non-zero on drift and prints a `FaithfulnessReport`.
- `resume-tool set-active --resume <json> --source <file> [--root .]` — records
  `active_resume` + its source path in `config.json` (code-owned; preserves
  unknown keys).

## Output

The saved path to a valid `ResumeDocument` JSON at
`resume-kit/resumes/<orig-basename>-original.json` that **passed
`validate-faithfulness`**, with `active_resume` and its source path recorded via
`set-active` — a faithful, lossless representation ready for check-structure,
check-keywords, validate-facts, and the other resume-intelligence
capabilities.
