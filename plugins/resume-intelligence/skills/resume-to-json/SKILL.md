---
name: resume-to-json
description: >
  Convert a resume file (PDF, DOCX, Markdown, or plain text) into the canonical
  resume-kit ResumeDocument JSON, faithfully and losslessly. Text extraction is
  deterministic and bundled in the base install (no optional extras needed).
  Structuring is done under strict no-alteration gates — no LLM provider
  required. Run FIRST whenever another resume-intelligence skill or tool needs a
  resume but you only have a document file. Best run in a subagent.
---

# resume-to-json — build a ResumeDocument from a resume file

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** a **source resume file path** (PDF, DOCX, Markdown, or
  plain text) provided by the caller.
- **If it is missing:** STOP and ask the caller for the source resume file path.
  There is no upstream skill — this skill is itself the first step that produces
  the `ResumeDocument` JSON others depend on.

## Purpose

Every resume-intelligence capability that takes a resume (check-ats-structure,
check-keyword-match, validate-resume-truth, select-best-resume,
compare-resume-versions, identify-resume-gaps, build-candidate-evidence,
export-resume) operates on a structured **ResumeDocument JSON** — not on a raw
PDF/DOCX/MD file. This skill turns a document into that JSON.

**The primary extraction path is the deterministic CLI** — `resume-tool extract
--no-llm <file>` (or `resume-tool extract-text <file>` if available). This
extracts raw text from PDF, DOCX, Markdown, and plain-text files using the base
install's bundled libraries (`markitdown`, `pdfminer.six`, `python-docx`) — **no
optional extra and no LLM provider required.** Direct agent file-reading is a
fallback when the CLI is unavailable. Your job is to take the extracted text and
transcribe the resume into the schema **without changing or losing anything**.

## Run me in a subagent

This is a self-contained, high-token transcription task. The main agent should
**dispatch it to a subagent** (e.g. the Task tool / a general-purpose agent) so
the large intermediate document text stays out of the main context. Hand the
subagent: the **source file path**, the **target save path** (see working dir
below), and this skill. The subagent reads → converts → self-checks → saves →
returns only the **saved path + a short summary** (counts of roles/bullets/
sections). Do NOT stream the whole resume back into the main conversation.

## Before you start: read prior learnings

Read `resume-kit/learning/resume-to-json.md` (if it exists) first — it accumulates
gotchas from earlier runs. When you discover a NEW gotcha, append it there so the
next agent does not rediscover it.

## Steps

1. **Extract text from the source file** using `resume-tool extract --no-llm
   <file>` (preferred) or `resume-tool extract-text <file>` if available. Both
   work with the base install for PDF, DOCX, Markdown, and plain-text — nothing
   extra to install. Fall back to reading the file directly only if the CLI is
   not reachable.
2. **Transcribe** the content into the ResumeDocument schema below.
3. **Apply the Faithfulness Gates** — this is the whole point.
4. **Validate** the JSON against the schema, **self-check** completeness, then
   **save** it to `resume-kit/resumes/<orig-basename>-original.json` (see below).

## Faithfulness Gates — DO NOT VIOLATE

The conversion must be **lossless and non-altering**. Treat the source as ground
truth:

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
- After building, **verify**: count the bullets per job in the source and in your
  JSON and confirm they match; confirm every section heading maps to a field or a
  `customSections` entry. Fix any loss before saving.

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
  ("Non-ASCII characters detected — some ATS systems may mis-parse them"). Do NOT
  silently rewrite them in the `-original.json` (that would violate the gates) —
  preserve verbatim; normalization is an *alignment/export* decision, not a
  conversion one. Just be aware the ATS check will (correctly) warn.
- **Sub-headed groupings** like "Ventures & Consulting" / "Professional
  Experience" that bucket multiple roles: put each role as its own
  `workExperience` entry, and preserve any intro/among-the-group text as a small
  `customSections` `text` block so it is not lost.
- **A "Career Break" line** with a date range and no bullets is still content:
  add it as a `workExperience` entry (title = the line, `company: ""`,
  `description: []`).
- **Always round-trip validate** before saving:
  `ResumeDocument.model_validate(json.load(...))`. If you cannot import the
  package, validate structurally against the schema below.

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

All resume-kit state lives under `resume-kit/` in the current project (create on
demand):

```
resume-kit/
├── config.json          # pointers + preferences (active_resume, active_job, ...)
├── resumes/
│   └── <orig-basename>-original.json   # THIS skill's output — immutable, faithful
├── jobs/
│   └── <orig-basename>-original.json   # job-to-json's output
├── working/
│   └── <session-id>/resume.json        # the resume currently being changed/reviewed (mutable copy)
└── learning/
    └── <skill>.md                      # accumulated hints; read first, append when you learn something
```

- **Save the conversion to** `resume-kit/resumes/<orig-basename>-original.json`,
  where `<orig-basename>` is the source file name without extension (e.g.
  `resume-d.pdf` → `resume-kit/resumes/resume-d-original.json`). The
  `-original.json` name is the **id back to the source file** and marks it as the
  untouched conversion — never edit it in place.
- To then review or modify a resume, COPY it to
  `resume-kit/working/<session-id>/resume.json` and work on the copy; leave the
  `-original.json` pristine.
- Record the saved path (and update `resume-kit/config.json`'s `active_resume`)
  so downstream skills know which file to use.

## Deterministic text extractor

Use `resume-tool extract --no-llm <file>` (or `resume-tool extract-text <file>`
if available) as the **primary extraction path**. The base install bundles
`markitdown`, `pdfminer.six`, and `python-docx`, so PDF, DOCX, Markdown, and
plain-text extraction all work out of the box — **no optional extra is required**.

If the CLI is genuinely unavailable (e.g. running in an environment where
`resume-tool` was not installed), fall back to reading the file directly with
your own file-reading capability. Do not improvise raw binary/XML parsing — if
neither path works, tell the user rather than guessing.

## Output

The saved path to a valid `ResumeDocument` JSON at
`resume-kit/resumes/<orig-basename>-original.json` — a faithful, lossless
representation ready for check-ats-structure, check-keyword-match, validate-resume-truth,
and the other resume-intelligence capabilities.
