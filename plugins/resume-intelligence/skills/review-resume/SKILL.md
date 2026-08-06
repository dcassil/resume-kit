---
name: review-resume
description: >
  Dispatch a subagent to review a resume against the original resume and the
  target job, then write STRUCTURED, parseable findings to
  `resume-kit/review/<session>.md`. The reviewer checks truthfulness (claims not
  supported by the original), missed JD requirements, over/under-claims,
  terminology-mirroring opportunities, and structure/ATS readability, and gives an
  overall verdict. ADVICE-ONLY — it never edits the resume; it points the user at
  update-keywords / update-terminology / validate-facts to act on findings.
  The shared review step both the optional workflow step and the dev refine loop
  build on. Best run in a subagent.
---

> **Renamed:** `review-resume` was `review-tailored-resume` before v1.0.0 (see RIT-A-0005).


# review-resume — subagent critique → structured findings (advice-only)

Take the (NEW tailored resume, ORIGINAL resume, JOB description) triple, hand it
to a reviewer subagent, and capture that reviewer's critique as a consistent,
machine-parseable markdown file under `resume-kit/review/`. This skill does ONE
thing: produce a review. It **never** mutates the resume — it only writes advice.

All state lives under `resume-kit/` in the current project. `config.json` tracks
`active_resume` and `active_job`; the mutable in-progress resume lives at
`resume-kit/working/<session>/resume.json`.

## Prerequisites

Run the shared **Prerequisites gate** first — see
[`_shared/prerequisites.md`](../_shared/prerequisites.md).

- **Required inputs (all three):**
  1. The **NEW / tailored** resume JSON — `resume-kit/working/<session>/resume.json`
     (a `ResumeDocument` produced by the tailoring skills).
  2. The **ORIGINAL** resume JSON — `config.json` `active_resume` (the pristine
     `resume-kit/resumes/<name>-original.json`).
  3. The **JOB** JSON — `config.json` `active_job` (a `JobDescription` under
     `resume-kit/jobs/`).
- **If any is missing:** STOP. Do not guess or review on partial inputs. Name the
  specific upstream skill to run first:
  - No original resume JSON → run **parse-resume**.
  - No job JSON → run **parse-job**.
  - No tailored `working/<session>/resume.json` yet → run the tailoring skills
    first (see **resume-workflow** — `update-keywords` / `update-terminology`).

Determine `<session>` from the tailored resume's path
(`resume-kit/working/<session>/resume.json`); reuse that same `<session>` for the
review filename so review and working copy stay paired.

## Run me in a subagent

This is a self-contained, high-token critique task. The main agent should
**dispatch it to a subagent** (the Task tool / a general-purpose agent),
consistent with `parse-resume`, `parse-job`, and `learn-terminology`. Hand the
subagent: the three resolved JSON paths, the rubric below, and this skill. The
subagent reads the documents, critiques them, writes
`resume-kit/review/<session>.md`, and returns only a short summary (the overall
verdict + counts) — do NOT stream the full resume/job text back into the main
context.

### Reviewer: default subagent, optional codex

- **Default (portable, no external dependency):** a Task subagent is the reviewer.
  This path MUST work with no `codex` present — never make the review depend on it.
- **Optional (dev / power users):** a fully-independent `codex exec` reviewer may
  be used instead, for a second perspective outside the main model. This is an
  optional enhancement only; the default subagent path is authoritative and always
  available. If `codex` is not installed, silently use the subagent.

## The critique the reviewer performs

Give the reviewer this exact framing:

> You are reviewing a tailored resume. You are giving **ADVICE ONLY** — you do NOT
> edit the resume or any file other than the review file described below. Compare
> the NEW tailored resume against the ORIGINAL resume and the JOB description and
> report:
>
> 1. **Truthfulness concerns** — any claim in the NEW resume that is **not
>    supported by the ORIGINAL** (a skill, metric, title, scope, or dated
>    experience that appears in NEW but has no basis in ORIGINAL). These are the
>    highest-priority findings; a tailored resume must never claim more than the
>    original truthfully supports.
> 2. **Missed JD requirements** — requirements/keywords in the JOB that the NEW
>    resume, though genuinely satisfied by the ORIGINAL, still fails to surface.
> 3. **Over-claims / under-claims** — where NEW overstates (inflated scope/impact
>    vs. ORIGINAL) or understates (real, relevant ORIGINAL experience left buried).
> 4. **Terminology-mirroring opportunities** — where the resume uses a variant
>    term for a skill the JOB names differently, and mirroring the employer's exact
>    wording (truthfully) would improve match.
> 5. **Structure / ATS readability** — parse-hostile formatting, ordering, section
>    naming, or density issues that hurt ATS or human readability.
> 6. **Overall verdict** — a concise ship / revise-first judgment with the top 1–3
>    things to fix.
>
> Every item must be **concrete and located** — point at the specific resume
> section and bullet (e.g. "Experience → Acme, bullet 2"). Do not invent facts and
> do not propose fabrications; if the ORIGINAL lacks support for a JD requirement,
> that is a real gap — report it, do not paper over it.

## Findings file — EXACT parseable layout (REQ-1204)

Write the review to **`resume-kit/review/<session>.md`** and NOWHERE else. Use
these EXACT top-level section headings, in this order, so downstream tooling (the
dev refine loop) can parse it deterministically. Every heading must be present
even if a section is empty (write `_None._` under an empty section — never omit
the heading):

```markdown
# Review — <session>

## Strengths
- <concrete, located item> (e.g. "Summary — leads with the JD's exact primary skill")

## Weaknesses
- <concrete, located item> (resume section / bullet)

## Truthfulness risks
- <claim in NEW not supported by ORIGINAL> — location + why it's unsupported

## Missed JD requirements
- <JD requirement the ORIGINAL satisfies but NEW doesn't surface> — where to add it

## Terminology suggestions
- <resume term> → <JD term> — location + why they are the same skill (truthful)

## Overall verdict
<one short paragraph: ship / revise-first + top 1–3 fixes>
```

Rules for the file:
- Headings must match **character-for-character** (`## Strengths`, `## Weaknesses`,
  `## Truthfulness risks`, `## Missed JD requirements`,
  `## Terminology suggestions`, `## Overall verdict`).
- Each bullet is concrete and located (names a resume section/bullet), not generic.
- Empty section → `_None._` under the heading (heading still present).

## Advice-only guarantee (NFR-1203)

- This skill and its reviewer write **ONLY** under `resume-kit/review/`. They must
  **never** edit `working/<session>/resume.json`, the `-original.json` files, the
  job JSON, `config.json`, or any other resume state.
- The review does not tailor or fix anything — it produces advice. To ACT on the
  findings, point the user at the right single-purpose skill:
  - Truthfulness risks / over-claims → **validate-facts** (then remove or
    correct the unsupported claim in the working copy).
  - Missed JD requirements → **update-keywords** (surface missing-but-true
    keywords into the working copy).
  - Terminology suggestions → **update-terminology** (mirror the employer's exact
    wording for a synonym the resume already satisfies).
- After acting, re-run this review on the updated working copy to confirm the
  findings closed.

## resume-kit working directory (file convention)

```
resume-kit/
├── config.json                        # active_resume / active_job pointers
├── resumes/<name>-original.json        # ORIGINAL (pristine) resume
├── jobs/<name>-original.json           # JOB description JSON
├── working/<session>/resume.json       # NEW tailored resume (reviewed, never edited here)
└── review/<session>.md                 # THIS skill's ONLY write target (parseable findings)
```

## Output

The written `resume-kit/review/<session>.md` (exact layout above) plus a short
returned summary: the overall verdict and the count of items under each section.
Nothing in the resume state is changed — this is advice only.
