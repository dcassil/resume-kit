---
name: job-to-json
description: >
  Convert a job posting (text, URL content, PDF/DOCX/MD, or pasted text) into the
  canonical resume-kit JobDescription JSON, with structured requirements and skill
  keywords. For file inputs, use `resume-tool extract --no-llm <file>` (bundled
  in the base install — no optional extras needed) to extract text, then
  structure it — no LLM provider required. Best run in a subagent.
---

# job-to-json — build a JobDescription from a posting

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required input:** the **job posting** as text, a URL's content, or a
  PDF/DOCX/MD/text file — provided by the caller.
- **If it is missing:** STOP and ask the caller for the posting text, URL, or
  file. There is no upstream skill — this skill is itself the first step that
  produces the `JobDescription` JSON others depend on.

## Purpose

`check-ats-structure`, `check-keyword-match`, and `identify-resume-gaps` score a
resume **against a JobDescription**. The deterministic no-LLM `resume-tool
extract-job` only captures the raw text — it does NOT populate the structured
`requirements` and `keywords`, so `skills_coverage` comes back `0`. This skill
fixes that: **you (the agent) extract the structured skills/requirements** from
the posting so scoring is meaningful — no LLM provider required.

## Run me in a subagent

Self-contained extraction task. The main agent should **dispatch it to a
subagent** with: the posting (file path or pasted text) and the **target save
path**. The subagent extracts → validates → saves → returns only the **saved path
+ a short summary** (counts of required/preferred/keywords). Keep the full
posting text out of the main context.

## Before you start: read prior learnings

Read `resume-kit/learning/job-to-json.md` (if present) first, and append any new
gotcha you hit so future runs benefit.

## Steps

1. **Obtain the posting text:**
   - For a **file input** (PDF/DOCX/MD/text): run `resume-tool extract --no-llm
     <file>` (or `resume-tool extract-text <file>` if available). The base
     install's bundled libraries handle PDF, DOCX, Markdown, and plain-text
     — no optional extra required. Fall back to reading the file directly only
     if the CLI is unavailable.
   - For **pasted text or URL content**: use it directly.
2. Put the **entire posting verbatim** in `raw_text`.
3. Extract **`requirements`** and **`qualifications`** — each a short statement
   plus the concrete **skill/technology keywords** it names.
4. Build a flat **`keywords`** list: every distinct skill, tool, language,
   framework, platform, and hard requirement named in the posting.
5. Validate against the schema, self-check, then **save** to
   `resume-kit/jobs/<orig-basename>-original.json` (or a slug from the title if
   pasted).

## Extraction gates — accurate, not invented

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
- Leave `title`/`company`/`location` from the posting; empty string / `null` if
  absent — do not guess.

## Learnings & gotchas (READ THESE)

- **`kind` uses lowercase values**: `"required"` or `"preferred"` (not the enum
  names). Wrong casing fails validation.
- **`skills_coverage` depends on this skill.** If a downstream ATS/match score
  shows `skills_coverage: 0` with an obviously-matching resume, the JobDescription
  was probably the raw-text-only `extract-job` output — re-extract it here so
  `keywords`/`requirements` are populated.
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

State lives under `resume-kit/` in the current project:

```
resume-kit/
├── config.json          # pointers + preferences (active_resume, active_job, ...)
├── resumes/<orig-basename>-original.json   # resume-to-json output
├── jobs/
│   └── <orig-basename>-original.json        # THIS skill's output
├── working/<session-id>/resume.json         # resume currently being changed/reviewed
└── learning/<skill>.md                      # accumulated hints (read first, append)
```

- **Save to** `resume-kit/jobs/<orig-basename>-original.json` (source file name
  without extension). If the posting was pasted (no file), use a stable slug from
  the job title + company, e.g. `staff-fullstack-acme-original.json`. The name is
  the id back to the source.
- Update `resume-kit/config.json`'s `active_job` to the saved path so downstream
  skills use it.

## Output

The saved path to a valid `JobDescription` JSON with populated `requirements`,
`qualifications`, and `keywords` — ready for `check-ats-structure`,
`check-keyword-match`, and `identify-resume-gaps` to produce meaningful
keyword-match AND skills-coverage scores.
