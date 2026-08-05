---
id: industry-guidance-audit-for-resume
level: initiative
title: "Industry Guidance Audit for Resume Grooming Tools"
short_code: "RIT-I-0018"
created_at: 2026-08-05T16:56:34.879671+00:00
updated_at: 2026-08-05T16:56:34.879671+00:00
parent: RIT-V-0001
blocked_by: [RIT-I-0016, RIT-I-0017]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: industry-guidance-audit-for-resume
---

# Industry Guidance Audit for Resume Grooming Tools Initiative

## Context **[REQUIRED]**

After the current in-flight and already-planned initiatives complete, resume-kit should run a focused discovery/design initiative to evaluate industry-suggested resume tailoring do's and don'ts against the toolkit's existing capabilities. The goal is not to blindly add every checklist item as a rule. The goal is to decide which guidance belongs in code, which belongs in skills/workflow copy, which should remain human judgment, and which requires genuinely new source-document inspection capability.

The user-provided guidance spans five existing capability areas:

- Job-tailoring phase: `check-keyword-match`, `resume_check_job_match`, `identify-resume-gaps`, `inject-keywords`, `resume_align`, and composite ATS checks.
- Terminology/synonym tools: `manage-synonyms`, `resume_align_terminology`, and `resume_suggest_terminology`.
- Export: `export-resume` and `resume_export`.
- Truth/faithfulness gates: `resume_validate_truth`, `candidate_evidence_build`, and `resume_validate_faithfulness`.
- Review/version selection: `review-tailored-resume`, `compare-resume-versions`, and `select-best-resume`.

Existing truth and faithfulness capabilities are treated as guardrails to reuse, not as a reason to rebuild the same capability. Existing terminology, review, export, and match tooling should be audited before adding new tools.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Build an evidence-backed decision matrix that maps industry resume guidance to current resume-kit capabilities, gaps, proposed changes, and non-actions.
- Decide which guidance should become deterministic checks, which should become LLM/reviewer prompts, which should become skill workflow steps, and which should remain user education or human judgment.
- Audit job-tailoring tools for role-specific tailoring, full-JD reading, employer terminology mirroring, keywords-in-context, required-vs-optional prioritization, seniority/scope reflection, natural repetition of important skills, and relevance framing for increasing-responsibility or transferable-experience items.
- Audit keyword-optimization guardrails: no keyword stuffing, no pasted JD content, no white-text or hidden keywords, no skills the candidate lacks, no tool claims based only on the JD, no over-optimization past readability, and no treating an ATS score as proof of recruiter advancement.
- Audit terminology/synonym tools for recruiter-search variants, spelled-out plus abbreviation alignment, and safe alias growth.
- Audit export tooling for application-stated format, DOCX vs digital/selectable PDF, upload confirmation reminders, parsed/autopopulated-field review, no password-protected/corrupted/tracked-changes files, and the distinction between editable DOCX and correct PDF output.
- Reuse truth/faithfulness gates to keep all grooming suggestions honest, interview-defensible, ownership-aware, and compliant with confidential-information restrictions.
- Audit review/version workflows for human readability after parser optimization, coherent voice, another-person review, multiple resume variants, and best-variant selection.
- Explicitly flag capabilities that require new ingest/export inspection rather than stretching current parsed-JSON checks beyond what they can know.

**Non-Goals:**
- Do not implement grooming behavior during discovery.
- Do not decompose implementation tasks until the audit and design choices are reviewed by the human.
- Do not duplicate existing truth validation or candidate evidence behavior unless the audit finds concrete gaps.
- Do not claim layout/rendering-level ATS checks are covered by the current structure engine when they require source PDF/DOCX inspection.
- Do not turn generic resume advice into noisy hard failures without evaluating false positives, user control, and readability impact.

## Discovery Questions

- What industry guidance sources should be treated as authoritative enough to influence product behavior, and how should each source be cited or preserved?
- For each guidance item, is the correct product expression a check, warning, recommendation, rewrite constraint, export validation, workflow prompt, documentation note, or explicit non-goal?
- Which existing public surfaces need updates: core engine, facade, CLI, MCP, API, plugin skills, README, or workflow docs?
- Which checks can be deterministic from `ResumeDocument`, `JobDescription`, `CandidateEvidence`, and existing reports, and which require source file inspection?
- Where should severity live: hard gate, warning, advice, or review finding?
- How should the system prevent advice conflicts, such as keyword optimization versus human readability?
- How should the tools avoid implying that any ATS score guarantees recruiter advancement?

## Candidate Guidance Map

### Job Tailoring
- Tailor per role and read the full job description before suggesting edits.
- Match employer terminology where it is semantically identical and truthful.
- Prefer keywords in context over keyword lists.
- Prioritize required qualifications over optional qualifications.
- Reflect seniority, scope, ownership, and scale when evidence supports it.
- Repeat important skills naturally, not mechanically.
- Frame increasing responsibility and transferable experience by relevance to the target role.

### Keyword Optimization Don'ts
- Do not stuff keywords.
- Do not paste the job description into the resume.
- Do not add white-text, hidden, or non-human keyword content.
- Do not add skills or tools the candidate lacks.
- Do not claim a tool solely because the JD asks for it.
- Do not optimize beyond readability.
- Do not describe an ATS score as a recruiter-advance guarantee.

### Terminology And Synonyms
- Support recruiter-search variants such as PostgreSQL and SQL when truthful.
- Align spelled-out forms and abbreviations where the meaning is equivalent.
- Keep alias growth truth-gated and reviewable.

### Export And Submission Hygiene
- Follow the application-stated format.
- Distinguish DOCX, digital PDF, and selectable-text PDF behavior.
- Warn about password protection, corruption, tracked changes, and non-selectable/scanned files where detectable.
- Remind users to confirm upload success and review parsed/autopopulated fields.
- Ensure filename guidance includes the candidate name and target/context where appropriate.
- Do not assume an editable DOCX rendered correctly as a PDF.

### Truth And Faithfulness
- No fabricated numbers, unsupported AI claims, or inflated ownership.
- Claims should be honest, defensible, and interview-survivable.
- Distinguish team ownership from personal ownership.
- Respect confidential-information restrictions.
- Route uncertain claims through evidence, confirmation, or rejection.

### Review And Version Selection
- Encourage another-person or second-agent review at the right workflow point.
- Write for humans after parser compatibility.
- Preserve a coherent personal voice across edits.
- Support maintaining multiple resume variants.
- Use comparison and selection tools to choose the best truthful variant for a target job.

## Candidate Future Work Outside Current Scope

These items are related but should be explicitly classified as future ingest/export capability unless the design phase chooses to expand this initiative:

- Layout/rendering-level ATS parse checks for multi-column layouts, tables, text boxes, headers/footers, images, and scanned PDFs. The current structure engine works from already-parsed JSON plus text scanning and cannot reliably see original file layout. True detection needs source PDF/DOCX inspection at ingest time.
- PDF text-layer/selectable-text verification and parsed-field round-trip checks. This belongs to export/ingest and does not currently exist as a complete capability.

## Detailed Design **[REQUIRED]**

Discovery should produce a design brief with these artifacts before implementation is decomposed:

- A guidance-to-capability matrix with columns for guidance item, target capability, existing coverage, proposed product behavior, severity, surface area, tests needed, and source/evidence.
- A recommended scope split between near-term tool updates, skill/workflow updates, documentation-only changes, and future initiatives.
- A proposed severity taxonomy for resume grooming findings: hard gate, warning, recommendation, review note, and out-of-scope/future capability.
- Interface-change recommendations for CLI/MCP/API/facade outputs, including whether new structured warning codes are needed.
- A truth-gate integration plan showing where existing `resume_validate_truth`, `candidate_evidence_build`, and `resume_validate_faithfulness` should be invoked or referenced.
- A source-file inspection boundary note for layout/selectable-text checks so current JSON/text-only checks are not overclaimed.

## Alternatives Considered **[REQUIRED]**

- Add all advice directly into existing tools as hard checks. Rejected for discovery because generic resume advice can create noisy false positives and poor user experience if converted to gates without classification.
- Keep the advice only in documentation. Rejected as the default because several items are concrete enough to become structured warnings, rewrite constraints, review prompts, or export checks.
- Create a new all-in-one resume grooming tool immediately. Deferred until discovery determines whether the right shape is a composite report, smaller updates to existing tools, skill workflow changes, or a new wrapper capability.
- Treat source-layout ATS parsing as already solved. Rejected because current parsed JSON and text scans cannot reliably detect columns, text boxes, headers/footers, images, scanned PDFs, or PDF text-layer issues.

## Cross-Initiative Coordination

This initiative is sequenced **after** [[RIT-I-0017]] and [[RIT-I-0016]] (see `blocked_by`) and is the eventual **consolidator/source-of-truth for the full resume-guidance inventory**. To avoid duplicating work those initiatives own, 0018 is **reference-not-duplicate**. Ownership split:

- **Owned by [[RIT-I-0017]] / [[RIT-A-0002]] — consume, do not rebuild:**
  - **ScoreDoc is the scoring read model.** All of 0018's keyword/tailoring/anti-stuffing guidance checks (keywords-in-context, required>optional, natural repetition, no keyword-stuffing/over-optimization) must be designed against **ScoreDoc's zoned keyword index + entities**, never `additional.technicalSkills` or raw BuildDoc field walks. This inherits RIT-A-0002's determinism/offline/no-LLM invariant for anything in the scoring path.
  - **The "what the ATS sees" report** is 0017's single surface; 0018 references/extends it rather than building a second report.
  - The **"an ATS score does not guarantee recruiter advancement"** messaging requirement is specified by 0018 but lands on **0017-owned score + report surfaces**.

- **Owned by [[RIT-I-0016]] / [[RIT-A-0003]] — consume/extend, do not fork:**
  - **Severity taxonomy.** 0016 establishes the grooming-finding severity taxonomy (hard-gate / warning / recommendation / review-note / out-of-scope-future). 0018 **adopts and, if needed, extends** that single taxonomy — it must not define a competing one.
  - **Best-practices engine.** 0016 owns the job-INDEPENDENT best-practices analyzer. In design, 0018 decides whether job-DEPENDENT guidance extends that same engine or lives in the tailoring tools — it does not stand up a parallel rule engine.
  - **Job-independent guidance slice.** 0016 owns the job-INDEPENDENT subset of the consolidated dos/donts. 0018 owns the **job-DEPENDENT** remainder (tailor-per-role, mirror employer terminology, keyword-in-context/anti-stuffing, required>optional, seniority/scope, review/version-selection, export/submission hygiene). The single consolidated list is inventoried once (here); 0016 references its job-independent slice rather than maintaining a copy.
  - **Source-file layout / selectable-text inspection is owned by 0016 REQ-011.** 0018's "Candidate Future Work" layout/render-parse and PDF text-layer/selectable-text items **defer to RIT-I-0016 REQ-011** as the owner; 0018 must not re-scope them into a competing capability. If 0018's design finds export-side selectable-text checks are needed, it coordinates with REQ-011.

- **Shared guardrails (already reused, not rebuilt):** truth/faithfulness gates (`resume_validate_truth`, `candidate_evidence_build`, `resume_validate_faithfulness`) and the [[RIT-I-0015]] edit-session orchestrator. 0018's truth-gate integration references the shared wiring; it adds no parallel gate.

- **LLM-shaped guidance routing:** guidance items that are inherently judgment-based (relevance framing, coherent voice, natural repetition) must be routed to reviewer-prompt / review-note lanes in 0018's severity model, **never into the deterministic scoring path**, preserving RIT-A-0002's invariant.

**Framework ADR:** [[RIT-A-0004]] (draft) records this initiative's two load-bearing framework decisions — the fixed **six-lane guidance-to-capability classification** (deterministic check / LLM-reviewer prompt / skill-workflow copy / documentation / human-judgment / out-of-scope-future) and the **adoption of RIT-I-0016's severity taxonomy** as the single shared finding vocabulary. Both await human review before this initiative exits discovery; the per-item classifications themselves are produced by the audit, not by the ADR.

## Implementation Plan **[REQUIRED]**

1. Wait until the currently active/in-planning initiatives are complete or intentionally paused.
2. In discovery, gather the industry guidance sources and normalize the advice into atomic guidance items.
3. Audit existing resume-kit capabilities and plugin skills against the guidance map.
4. Produce the guidance-to-capability matrix and identify duplicates, gaps, and out-of-scope future work.
5. Review findings with the human before transitioning from discovery to design.
6. In design, choose the product expression for each accepted guidance item and define severity/output contracts.
7. Review the proposed implementation decomposition with the human before creating tasks.

## Exit Criteria

- Every user-provided guidance item is mapped to existing coverage, proposed change, documentation-only handling, or explicit non-goal/future work.
- Truth/faithfulness behavior is represented as reused guardrails, not duplicated new scope.
- Layout/rendering/source-file limitations are clearly documented and separated from JSON/text-only ATS checks.
- The human has reviewed and approved the design direction before task decomposition begins.