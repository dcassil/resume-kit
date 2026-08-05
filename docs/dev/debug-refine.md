# Dev Debug/Refine Loop

**Audience**: toolkit contributors only. This is a dev runbook, not a shipped user skill.
**Purpose**: run a real resume + JD trial pair through the pipeline, critique the output with
`review-tailored-resume`, triage findings into TOOLKIT improvements (skills/engine), and track
them in Metis. You are not iterating on the candidate's resume — you are stress-testing the
toolkit itself.

---

## Overview

```
trial pair → pipeline → tailored resume → review → triage → Metis backlog task(s) → dev log
```

The pipeline and review skills are already shipped. This runbook wires them together for dev use
only. No new skill is created here.

---

## Step 1 — Place a trial pair

Create a named slot under `.agents/trials/`:

```
.agents/trials/<name>/
  resume.<ext>        # real resume: .pdf, .docx, or .md
  job.txt             # raw JD text
```

**Personal-data warning**: `.agents/trials/` is git-ignored (see `.gitignore`). Do NOT commit
real resumes or JDs. The trial name is arbitrary (`acme-swe`, `stripe-pm`, etc.).

---

## Step 2 — Set up `config.json`

From `resume-kit/` (the working directory for all skills):

```json
{
  "active_resume": "trials/<name>",
  "active_job":    "trials/<name>",
  "alias_file":    "learning/synonyms.json"
}
```

Pick a `<session>` label (e.g. `debug-<name>-001`). You will use it throughout.

---

## Step 3 — Run the pipeline

Run each skill in order. The working directory for every skill invocation is `resume-kit/`.

| # | Skill | What it produces |
|---|-------|-----------------|
| 1 | `resume-to-json` | `resumes/<name>-original.json` |
| 2 | `job-to-json` | `jobs/<name>-original.json` |
| 3 | `check-ats-structure` | structural ATS report (console / session notes) |
| 4 | `check-keyword-match` | keyword-match report |
| 5 | `identify-resume-gaps` | gap list |
| 6 | `inject-keywords` | `working/<session>/resume.json` with injected terms |
| 7 | `update-terminology` | updates `working/<session>/resume.json` in place |
| 8 | `validate-resume-truth` | truthfulness flags |
| 9 | `export-resume` | `working/<session>/resume.pdf` (or `.md`) |

See `resume-workflow` for the authoritative step guide and flag options.

Record the before/after scores (keyword-match %, ATS pass/fail) — you will need them for the
dev log in Step 6.

---

## Step 4 — Run `review-tailored-resume`

This is the shipped review skill. It dispatches a subagent that reads the tailored resume, the
original resume, and the JD, then writes structured findings to `resume-kit/review/<session>.md`.

### Default path (subagent)

Invoke the skill normally from `resume-kit/`:

```
/review-tailored-resume
```

The skill resolves the session from `config.json` and writes:

```
resume-kit/review/<session>.md
```

### Optional: independent reviewer via `codex exec`

For a second-model perspective (useful when you suspect the subagent shares context with the
pipeline and may be lenient), pipe the three artifacts into `codex exec`:

```bash
codex exec -s workspace-write -- bash -c '
  cat working/<session>/resume.json \
      resumes/<name>-original.json \
      jobs/<name>-original.json \
  | python3 -c "
import sys, json
data = sys.stdin.read()
print(\"Review this tailored resume against the original and JD.\")
print(\"Output sections: Strengths, Weaknesses, Truthfulness risks,\")
print(\"Missed JD requirements, Terminology suggestions, Overall verdict.\")
print(data)
"
' > review/<session>-codex.md
```

Adjust paths to match your session. The `-s workspace-write` sandbox gives read/write access to
the workspace without network. Pipe output to a separate file so the primary review is not
overwritten.

---

## Step 5 — Read the findings

Open `resume-kit/review/<session>.md`. The structured layout (from the `review-tailored-resume`
skill) is:

```markdown
## Strengths
## Weaknesses
## Truthfulness risks
## Missed JD requirements
## Terminology suggestions
## Overall verdict
```

If you ran the codex variant, compare `review/<session>.md` and `review/<session>-codex.md`.
Discrepancies between the two reviewers are especially useful signals.

---

## Step 6 — Triage: findings → Metis backlog

**Goal**: identify TOOLKIT gaps, not resume gaps.

For each finding, ask: _"Does this reveal that a skill missed something, a check is too
weak/strict, or the engine lacks a needed capability?"_ If yes → file a Metis backlog task. If
the finding is "the candidate should have more Python experience" → discard (not a toolkit issue).

### Triage guide

| Finding type | Example | Action |
|---|---|---|
| Skill missed a check | `inject-keywords` added a term the JD never uses | bug → backlog |
| Check too strict | `validate-resume-truth` flagged a reworded (not fabricated) claim | tech-debt → backlog |
| Check too weak | `check-keyword-match` missed a synonym | feature → backlog |
| Engine capability gap | No support for certifications section | feature → backlog |
| Resume content gap | Candidate lacks cloud experience | discard |

### Filing a Metis backlog task

For each actionable toolkit gap, call `mcp__plugin_metis_metis__create_document` with this shape:

```json
{
  "document_type": "task",
  "title": "<short description of the toolkit gap>",
  "backlog_category": "<bug | feature | tech-debt>",
  "content": "## Context\n<which trial, which review section, what the finding was>\n\n## Problem\n<what the toolkit did wrong or is missing>\n\n## Proposed fix\n<what skill or engine change would address it>\n\n## Acceptance criteria\n- [ ] <concrete, testable criterion>"
}
```

Example:

```json
{
  "document_type": "task",
  "title": "inject-keywords: skip terms that do not appear in JD",
  "backlog_category": "bug",
  "content": "## Context\nTrial: acme-swe, session debug-acme-swe-001. Weaknesses section noted injected term 'Kubernetes' absent from JD.\n\n## Problem\ninject-keywords inserted a term from the alias file without verifying it appears in the active JD.\n\n## Proposed fix\nAdd a JD-presence gate in inject-keywords before accepting a synonym substitution.\n\n## Acceptance criteria\n- [ ] inject-keywords only inserts a term if it or a recognized alias appears in jobs/<name>-original.json"
}
```

Record the Metis task ids returned (e.g. `RIT-T-XXXX`) — you will append them to the dev log.

---

## Step 7 — Append to the dev log

Append a trial entry to `.agents/refine-log.md`:

```markdown
## <name> — <YYYY-MM-DD>

- **Session**: `<session>`
- **Pipeline**: full (steps 1–9)
- **Before scores**: keyword-match X%, ATS <pass|fail>
- **After scores**: keyword-match Y%, ATS <pass|fail>
- **Key findings**:
  - [Weakness] <finding>
  - [Missed JD req] <finding>
  - ...
- **Metis tasks filed**: RIT-T-XXXX (<category>: <title>), ...
- **Codex reviewer used**: yes/no
- **Notes**: <anything anomalous>
```

---

## First trial checklist

Run through this before your first real-data trial:

- [ ] `.agents/trials/<name>/resume.<ext>` exists (real file, not fabricated)
- [ ] `.agents/trials/<name>/job.txt` exists (real JD, not fabricated)
- [ ] `config.json` points at the trial slot and a clean session label
- [ ] `resume-kit/working/<session>/` does not already exist (avoid stale artifacts)
- [ ] `resume-kit/review/<session>.md` does not already exist
- [ ] You have a Metis project active (`.metis/` present) so backlog tasks land correctly
- [ ] `.agents/refine-log.md` exists (create it if not; see placeholder below)
- [ ] `codex` is in PATH if you plan to use the optional independent reviewer

---

## Notes

- **Never fabricate trial data.** The runbook requires real resumes and JDs to surface real
  toolkit gaps. Synthetic data produces misleading findings.
- **One session per trial run.** Do not reuse session labels; stale artifacts will confuse the
  review skill.
- **Triage discipline.** File Metis tasks only for TOOLKIT gaps. Resume-content gaps belong in a
  conversation with the candidate, not in the backlog.
- **Codex variant is optional.** Use it when the primary review seems suspiciously charitable or
  when you want adversarial coverage on truthfulness.
