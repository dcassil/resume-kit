---
name: resume-to-json
description: >
  Convert a resume file (PDF, DOCX, Markdown, or plain text) into the canonical
  resume-kit ResumeDocument JSON, faithfully and losslessly. The agent does the
  structuring under strict no-alteration gates — no LLM provider or extra
  dependency required. Use this FIRST whenever another resume-intelligence skill
  or tool needs a resume but you only have a document file.
---

# resume-to-json — build a ResumeDocument from a resume file

## Purpose

Every resume-intelligence capability that takes a resume (check-resume-ats,
check-resume-job-match, align-resume, validate-resume-truth, select-best-resume,
compare-resume-versions, identify-resume-gaps, build-candidate-evidence,
export-resume) operates on a structured **ResumeDocument JSON** — not on a raw
PDF/DOCX/MD file. This skill turns a document into that JSON.

**You (the agent) are the converter.** You already can read PDF/DOCX/Markdown/
text files directly, so no LLM provider and no PDF library are required for the
recommended path. Your job is to transcribe the resume into the schema **without
changing or losing anything**.

## When to use

Use this whenever you have a resume as a `.pdf`, `.docx`, `.md`, or `.txt` file
(or pasted text) and a downstream skill/tool needs a `ResumeDocument`. Produce
the JSON here, then hand the JSON to the downstream skill.

## Steps

1. **Read the source file directly** with your own file-reading capability
   (this handles PDF, DOCX, Markdown, and text — nothing to install).
2. **Transcribe** the content into the ResumeDocument schema below.
3. **Apply the Faithfulness Gates** (next section) — this is the whole point.
4. **Self-check**, then write the JSON to a file (e.g. `resume.json`) and/or
   return it, ready for the downstream capability.

## Faithfulness Gates — DO NOT VIOLATE

The conversion must be **lossless and non-altering**. Treat the source as ground
truth:

- **Never invent, embellish, summarize, shorten, or paraphrase.** Every bullet,
  sentence, and phrase is copied **verbatim**.
- **Never drop content.** Every job, bullet, date, employer, title, school,
  degree, skill, language, certification, award, project, and section in the
  source MUST appear in the JSON.
- **Preserve facts exactly**: employer names, job titles, institutions, degrees,
  dates/date-ranges, locations, URLs, and metrics are copied character-for-
  character (including the exact date format).
- **Preserve order** — keep sections, jobs, and bullets in the source order.
- **No merging or splitting** of bullets or entries.
- **Anything that does not fit the standard sections goes into `customSections`**
  (never discard it) — use a `stringList` (bullets/lines) or `text` block. The
  `sectionType` value is lowercase: `text`, `stringList`, or `itemList`.
- **Leave unknown optional fields empty** (`""`, `null`, or `[]`) — do not guess
  emails, phones, links, or dates that are not present.
- After building, **verify**: count the bullets per job in the source and in your
  JSON and confirm they match; confirm every section heading in the source maps
  to a field or a `customSections` entry. If anything was lost, fix it before
  continuing.

If the source is ambiguous or unreadable in places, transcribe what is present
and note the uncertainty to the user — never fill gaps with invented content.

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

- `id` values are simple 1-based integers within each list.
- Put skills under `additional.technicalSkills`; languages, certs, and awards in
  their matching `additional` lists.
- Use `customSections` for things like "Publications", "Volunteering",
  "Speaking", "Patents", or any heading not covered above.

## Optional: the deterministic text extractor (asks before installing)

The recommended path above (you reading the file) needs nothing installed. If you
specifically want the deterministic `resume-tool extract` output as a cross-check
and it fails on a **PDF** with a missing-dependency error, that is the optional
`markitdown[pdf]` extra. **Do not install it silently — ask the user first**, e.g.:

> "Reading this PDF with the deterministic extractor needs the optional
> `markitdown[pdf]` support. Want me to install it? (`uv tool install
> "resume-kit[all]" --with "markitdown[pdf]"`)"

Only install it if the user agrees. For DOCX/Markdown/text the extractor works
without it. In almost all agent contexts you should just read the file yourself
(step 1) and skip this entirely.

## Output

A valid `ResumeDocument` JSON (written to a file and/or returned) that is a
faithful, lossless representation of the source resume — ready to pass to
check-resume-ats, align-resume, validate-resume-truth, and the other
resume-intelligence capabilities.
