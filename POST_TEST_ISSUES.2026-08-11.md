# Post-Test Issues - 2026-08-11

## Context

This summarizes the post-test feedback from the resume-kit tool run and the
additional plugin notes in
`/Users/danielcassil/Documents/jobs/claude2/resume-kit/review/plugin-notes.md`.
The investigation was read-only. The core read/scoring/truth-validation path
looks solid; most risk is concentrated in write-path state, fit/export handoff,
and plugin skill documentation that can steer agents into inconsistent flows.

## What Worked Well

- `extract-text`, `set-active`, and `init` were deterministic and reliable.
- `validate-faithfulness`, `build-base`, and `build-structure` passed hard gates.
- Keyword match/scoring was the strongest component: deterministic, fast, and
  useful for downstream decisions.
- `validate-truth` was a reliable safety net and did not allow fabricated claims.
- `analyze-best-practices`, second-agent review, and binary export rendering were
  stable in the tested path.

## Judgment-Required Areas

- Resume text to `ResumeDocument` mapping still requires agent judgment by design.
- Job text to `JobDescription` mapping still requires agent judgment by design.
- Terminology candidate review is high risk if unattended. The deterministic
  proposer is low precision and can suggest false aliases such as near-spellings,
  acronyms, or unrelated short-token matches.
- Truthful keyword injection depends on agent/evidence judgment.
- Interviewing missing requirements worked, but depends on careful reading of
  user answers and grounding facts.
- `build-refine` correctly refused to invent metrics, so it may make no wording
  changes when every finding requires user-provided quantification.

## Confirmed / Likely Runtime Issues

### Edit Session And Fit State

Committed tailoring writes to `resume-kit/working/<stem>.tailored.json`, but it
does not promote that file into the active version lineage. `fit` later resolves
the baseline lineage again (`refine -> standard -> structure -> base -> original`)
and can operate from the untailored baseline instead of the committed tailored
resume. This explains fit hash drift and the SoundCloud workaround that polluted
the baseline.

The edit-session model also uses one active `working/edit-session.json` and a
working path derived from the active resume name rather than the job. Multiple
jobs against the same refined resume can collide on the same tailored working
file and trigger `working_resume_tampered` errors.

### `add_skill` List Values

The schema permits `ChangeProposal.value` to be a string or list, but
`add_skill` accepts only one non-empty string. A list value is rejected by the
apply layer, which made skill additions ineffective in testing. The tool should
either validate this earlier with a clear error or intentionally expand list
values into multiple single-skill changes.

### Alias Growth During Commit

Commit-time automatic alias growth can throw `LexiconError` when an accepted
terminology edit would make the alias index ambiguous, for example when edit
text contains an existing alias canonical such as "data models". Alias growth is
currently coupled tightly enough to commit that alias-index failure can block a
resume write. The safer behavior is to validate proposed alias growth against a
copy of the payload and skip/defer unsafe alias additions without failing the
resume commit.

### Evidence File Import Confusion

`add-evidence --evidence-file` means "destination evidence file", not "import
records from this file". The capability always creates one deterministic record
from `--content`, merges it into the destination, and optionally updates the
active pointer. It does not bulk-import or append records from another
multi-record evidence file.

### Page Gate Not Wired To Export

The policy default currently has `max_pages=2`, and a page-gate module exists.
However, facade export calls render directly and does not enforce the page gate.
The plugin docs say export enforces `max_pages`, but current export wiring can
ship over-length resumes without objecting.

### Alias-Aware Scoring Inconsistency

The top-level keyword gap/match path and ATS skills coverage are alias-aware.
Required/preferred coverage and placement in `matching.match` still use a local
exact regex. This can produce cosmetic but confusing artifacts where a keyword
is matched in one slice and missing in another.

## Plugin Notes Findings

The plugin notes add a second layer of issues: some runtime bugs are reinforced
by inconsistent skill documentation.

- The `standard -> refine` rename is only partially applied. Some skills still
  describe `original -> base -> standard` and route deferred work to deprecated
  `update-best-practices`, while the current terminal stage is `refine`.
- Working-copy paths have multiple documented conventions:
  `working/<name>.tailored.json`, `working/<session>/resume.json`, and
  `final_path` from perfect. There is no single pointer contract tying these
  together.
- `check-gaps` requires a distinct master resume to classify injectability, but
  `resume-workflow` describes the gate as only `refine + active_job`.
- Terminology growth and terminology swaps have inconsistent proof posture:
  some docs allow human-confirmed alias growth without evidence, while
  update-terminology requires `CandidateEvidence` for swaps.
- `perfect` claims export enforces `max_pages`, but export docs and facade
  export do not expose or enforce a page failure mode.
- `parse-resume` instructs agents to put categorized skills in
  `customSections` while also putting flat skills in `additional.technicalSkills`.
  Export renders both, causing duplicate Skills sections and contributing to
  over-length output and inflated skill counts.
- Shared prerequisites mention only a subset of config pointers. Several skills
  rely on `base_resume`, `structure_resume`, `refine_resume`, `final_resume`,
  `active_evidence`, and lineage fields without one shared contract.
- Some skills advertise deterministic/no-LLM behavior, while adjacent workflow
  steps rely on subagents or user-interview loops. The end-to-end workflow is
  not fully deterministic even though many individual capabilities are.

## Tasks To Consider

| Task | Priority | Effort | Reason |
|---|---:|---:|---|
| Define one canonical post-tailoring state model and path convention | P0 | Large | Fixes the root cause behind edit-session collisions, fit hash drift, review/export path mismatch, and baseline pollution risk. |
| Make tailored/final outputs first-class config pointers | P0 | Large | `fit`, review, export, and validation need to consume the same intended resume without manually overwriting baseline lineage files. |
| Job-scope edit-session working paths | P0 | Medium | Prevents multiple jobs against one refined resume from sharing `working/<stem>.tailored.json` and stale `edit-session.json` state. |
| Update `fit` to consume the committed tailored resume explicitly | P0 | Medium | Prevents `fit --auto-fit` from re-reading `refine` after tailoring and rejecting or ignoring the committed working copy. |
| Wire page-budget gate into facade/API/CLI/MCP export | P0 | Medium | Current export can ship 3-page resumes even though workflow docs claim a hard `max_pages` gate. |
| Add export override contract for page-budget failures | P1 | Small | Once the gate is wired, users need an explicit, auditable way to override when appropriate. |
| Reconcile duplicate categorized skills before export and fit | P1 | Medium | Prevents duplicate Skills sections, inflated page count, and inflated skills-budget violations. |
| Decide canonical representation for categorized skills | P1 | Medium | The system needs one source of truth for ATS-flat skills plus renderable categories without rendering both as separate sections. |
| Harden commit-time alias growth | P1 | Medium | Alias learning should never corrupt the alias file or block a truthful resume commit because one proposed alias is ambiguous. |
| Validate alias growth against copied payload before write | P1 | Small | Catches `LexiconError` before mutating the alias file and allows unsafe growth to be skipped. |
| Make `add_skill` input contract explicit | P1 | Small | Either reject list values at model/tool validation with a clear message or split list values into multiple single-skill changes. |
| Add regression coverage for `add_skill` list input | P1 | Small | Locks whichever input contract is chosen and prevents silent no-op behavior. |
| Add real evidence bulk-import or rename `--evidence-file` docs/help | P1 | Small | Avoids the observed confusion where a source file path was treated as a destination pointer. |
| Make check-gaps master/evidence contract consistent across skills | P1 | Medium | Prevents agents from running gap analysis without the distinct master/proof surface needed for trustworthy injectability. |
| Make required/preferred coverage alias-aware | P2 | Medium | Aligns composite report slices with the alias-aware keyword gap and ATS skill coverage engines. |
| Make placement scoring alias-aware | P2 | Medium | Removes confusing "matched here, missing there" artifacts in the report. |
| Reduce terminology proposer false positives | P2 | Medium/Large | The current fuzzy pre-filter is deterministic but low precision; stronger acronym, stopword, token-length, and zone-based filters are needed for safer unattended use. |
| Finish `standard -> refine` doc cleanup | P2 | Small | Reduces agent routing mistakes and removes deprecated `update-best-practices` references from active workflow docs. |
| Create a shared config pointer contract doc | P2 | Small/Medium | Centralizes `active_resume`, `base_resume`, `structure_resume`, `refine_resume`, `final_resume`, `active_evidence`, `alias_file`, and lineage semantics. |
| Clarify deterministic vs agent-driven workflow steps | P2 | Small | Sets realistic expectations: many capabilities are deterministic, but parsing, review, terminology truth-gating, and interviews require agent/human judgment. |
| Normalize capability names in docs | P3 | Small | Reduces confusion among `extract-evidence`, `build-evidence`, and `candidate_evidence_build`, plus other renamed surfaces. |

## Recommended Fix Order

1. Establish the state/path contract for tailored and final resumes.
2. Fix `fit` to consume the intended tailored input.
3. Wire export page gating and define override behavior.
4. Reconcile duplicate categorized skills.
5. Harden alias growth and `add_skill` validation.
6. Clean plugin docs so agents follow the fixed code paths.

