# Change-application runbook (shared convention)

Every `update-*` skill builds a set of `ChangeProposal` records for its own
reason — a missing-but-true keyword (`update-keywords`), a terminology mirror
(`update-terminology`), an ATS-structure fix (`update-structure`), a
best-practice rewrite (`update-best-practices`) — and then hands them to **this
runbook**. The runbook owns the universal edit spine and is the single place it
is defined; each calling skill points here instead of repeating it.

The runbook does **not** build proposals — that is the caller's `create-change`
step — and it **never writes the resume itself**. The code-owned edit-session
orchestrator performs every write behind the hard write gate; it owns review
state, decision logging, tamper detection, policy application, preference
feedback, and alias growth.

**The five phases:**

`create-change` (caller) → `request-change` → `apply-change` → `validate-facts` → `learn-change`

## Working directory

All project state lives under `resume-kit/`:

```
resume-kit/
├── config.json
├── resumes/<name>-original.json
├── jobs/<name>-original.json
├── working/edit-session.json
├── working/<name>.tailored.json
└── learning/
    └── synonyms.json        # grown aliases (terminology edits)
```

The orchestrator writes the tailored resume to the `working_path` reported by
`commit-session` / `resume-tool review-edits commit`. **Do not create, overwrite,
or bulk-edit that file yourself** — direct hand-editing trips tamper detection.
If the user intentionally edits the working file out of band, the sanctioned
recovery is `resume-tool review-edits reconcile` / `edit_session_reconcile` /
`reconcile-session`, then continue through the gate. After a session is fully
committed, the caller may make the result active via
`resume-tool set-active --resume <working_path>`.

## The edit-session surfaces

- CLI `resume-tool review-edits open --mode <interactive|review_at_end|auto>`
- CLI `resume-tool review-edits prompt`
- CLI `resume-tool review-edits decide --path <path> --action <approve|reject|edit|skip>`
- CLI `resume-tool review-edits commit`
- CLI `resume-tool review-edits status`
- CLI `resume-tool review-edits reconcile`
- MCP `edit_session_open`, `edit_session_prompt`, `edit_session_decide`,
  `edit_session_commit`, `edit_session_status`, `edit_session_reconcile`
- Facade capabilities `open-edit-session`, `session-prompt`, `decide-change`,
  `commit-session`, `session-status`, `reconcile-session`
- Truth validation (phase 4): facade capability `validate-facts` (CLI
  `resume-tool validate-truth`, MCP `resume_validate_truth`).
- Re-score (phase 5): facade capability `check-resume-job-match` (CLI
  `resume-tool match`, MCP `resume_check_job_match`).

## Phase 1 — create-change (owned by the calling skill)

The calling skill produces the `ChangeProposal` records; this runbook states the
contract every proposal must obey:

- Propose only **minimal** `replace`, `append`, or `add_skill` changes against
  truthful, allowed resume paths.
- On `replace`, include the current `original` value plus the proposed `value`.
- Include a `reason` that names what justifies the change (the keyword + its
  evidence, the alias hit, the structural rule, etc.).
- **Never** target identity, employer, title-of-record, or date fields.
- Never bulk-apply a change list or write the working JSON directly — the whole
  point of the phases below is that each change is decided and gated.

## Phase 2 — request-change (mode prompt + decide loop)

**Mode prompt.** Before opening the session, ask the user which review mode they
want — do not choose silently; if the user does not answer, use `interactive`:

- `interactive` — prompt and decide each change before moving on.
- `review_at_end` — collect proposals first, then review at the end. Use this
  exact underscore spelling in CLI/MCP/capability payloads.
- `auto` — let the orchestrator auto-approve only changes its policy can safely
  apply; unsupported/deferred changes are not silently applied.

**Open the session.** Call `open-edit-session` with the change list plus any
evidence, claim provenance, and expected score deltas available. CLI example:

```bash
resume-tool review-edits open \
  --mode interactive \
  --changes <changes.json> \
  --evidence <evidence.json>
```

**Decide each change.** Repeatedly call `session-prompt` / `resume-tool
review-edits prompt`, show the prompt, then record the user's path-correlated
decision with `decide-change` / `resume-tool review-edits decide`. Actions are
`approve`, `reject`, `edit`, or `skip`.

**Reason codes.** On every `reject` or `edit`, offer the `EditFeedbackReasonCode`
enum — not open-ended free text:

`fabrication`, `overclaim`, `unsupported`, `grammar`, `formatting`,
`not_my_voice`, `too_verbose`, `too_vague`, `wrong_emphasis`, `duplicate`,
`other`.

Pass it as `--reason-code <value>` / `reason_code`. A short optional note is
allowed through `--note` / `note`, but never replaces the enum. For `edit`, pass
the user's final wording with `--edited-content` / `edited_content`.

## Phase 3 — apply-change (commit hard gate)

Call `commit-session` / `resume-tool review-edits commit`. This is the hard write
gate — it is the only thing that writes the resume. If it fails because decisions
are missing, claims are contradicted, policy rejects paths, or the working file
was tampered with: **stop and report the gate failure. Do not patch around it.**
If the user made an intentional out-of-band edit, run `reconcile-session` and
then re-commit.

## Phase 4 — validate-facts

Run **validate-facts** on the committed `working_path` (with the evidence list
where the caller has one). Any unsupported or contradicted claim must be resolved
before export — never keep a change blocked by `commit-session` or `validate-facts`.

## Phase 5 — learn-change (automatic) + re-score

Learning is **automatic** and needs no extra step here:

- `decide-change` auto-appends an `EditFeedback` record for every decision (the
  `learn-change` store) — that is what biases future ranking.
- `commit-session` returns `grown_aliases` for accepted terminology edits (the
  `learn-terminology` store) — future deterministic matching picks them up.

Call **learn-change** / **learn-terminology** directly only to log a decision or
grow an alias **outside** an edit session.

**Re-score and report.** Run **check-keywords** (`resume-tool match` /
`resume_check_job_match`), honoring `alias_file`, and report before/after keyword
and ATS deltas from the commit result or the re-score.

## Truth posture (shared)

- Never edit identity, employer, title-of-record, or date fields.
- Never bulk-apply a change list or write the working JSON directly.
- Never keep a change blocked by `commit-session` or `validate-facts`.
- When in doubt, skip and explain what is missing.

The calling skill adds its own posture line (e.g. "only surface a keyword the
candidate can prove", "only mirror wording for a skill already demonstrated").

## Output (shared shape)

Return the committed `working_path`, the session id, the approved/edited changes,
every rejected/skipped item with its reason code when supplied, every hard-gate
rejection, any grown aliases, and the before/after match delta. The calling skill
adds its type-specific fields (e.g. the injected keyword + evidence, or the
`{path, old, new}` wording swap) and states explicitly what it did **not** write.
