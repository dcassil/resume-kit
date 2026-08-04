---
id: terminology-alignment-suggestions
level: initiative
title: "Terminology-Alignment Suggestions (mirror employer wording)"
short_code: "RIT-I-0010"
created_at: 2026-08-04T18:50:56+00:00
updated_at: 2026-08-04T18:50:56+00:00
parent: RIT-V-0001
blocked_by: [RIT-I-0008]
archived: false

tags:
  - "#initiative"
  - "#phase/discovery"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: terminology-alignment-suggestions
---

# Terminology-Alignment Suggestions (mirror employer wording) Initiative

## Context **[REQUIRED]**

Synonym-aware scoring (RIT-I-0008) makes OUR report honest — but the **employer's** real ATS is usually
a literal string matcher. So when the resume says "mentoring" and the posting says "mentorship", the
candidate benefits from **mirroring the employer's exact term** — a truthful rewrite that measurably
raises the employer's score. This is distinct from fabrication: mirroring your own true skill in the
posting's vocabulary is allowed; claiming a skill you don't have (Kubernetes, Terraform) is not.

This initiative turns the synonym-match provenance from RIT-I-0008 into a **terminology-alignment
output**: for each JD keyword the resume satisfies via a stem/alias (not an exact match), produce a
suggestion to mirror the JD's exact wording — routed through the existing Phase-4 alignment + truth
gates so it can never introduce an unsupported claim. Genuine gaps (no match at all) are reported as
gaps, never rewritten in.

Relevant substrate:
- RIT-I-0008 annotates each match with `kind` (`exact` | `stem` | `alias:<canonical>`) — this is the
  signal that a keyword is present under a DIFFERENT surface form (the rewrite candidates).
- `packages/alignment` — `align_resume`, `apply_diffs`, `ChangeProposal`, the policy freedom gates, and
  `validate_resume_truth` / evidence gates already enforce "no unsupported claim" and freedom-bounded
  edits. Terminology alignment is a constrained, low-freedom, evidence-trivial case of alignment.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- A deterministic **terminology-alignment analysis**: given a resume + JobDescription (with
  synonym-aware match provenance from RIT-I-0008), produce a list of **TerminologyAlignment
  suggestions** — each: the JD keyword, the resume's current wording, the location(s) in the resume,
  the match kind (stem/alias), and the proposed mirrored wording. Only for stem/alias hits — exact
  matches need no change; no-match keywords are gaps, not suggestions.
- Route acceptance through the existing alignment engine as **low-freedom, truth-safe rewrites**: the
  proposed change swaps the surface term to the JD's wording while preserving the underlying fact;
  `validate_resume_truth` must still pass (the claim is unchanged), and the change must clear the policy
  gate (surface wording of a real skill — allowed; identity/employer/date fields — never touched).
- **Never fabricate**: a JD keyword with no stem/alias match produces a GAP entry (surface it), never a
  terminology suggestion. This is enforced, not advisory.
- Expose the analysis through the facade + the five surfaces consistently with the Phase-5 pattern
  (a capability + thin adapters), and add a plugin skill so the agent can present and apply the
  suggestions section-by-section (human-in-loop friendly).
- Report the expected before/after keyword-match delta for each accepted suggestion (using the
  deterministic engine), so the value is visible.

**Non-Goals:**
- Inventing or broadening skills (fabrication) — categorically excluded; that is the truth gate's job.
- Full resume rewriting / higher-freedom alignment beyond surface-term mirroring (that's general
  `align_resume`, already built).
- LLM/embeddings — deterministic analysis over RIT-I-0008 provenance; no provider required to GENERATE
  the suggestions (applying them may reuse align's deterministic no-LLM path).
- Guaranteeing the employer's ATS behavior — we optimize for literal-match likelihood truthfully; we
  don't model any specific vendor.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-1001: A deterministic function produces `TerminologyAlignment` suggestions from (resume, JD,
    RIT-I-0008 match provenance): only for stem/alias hits, with current wording, location, and
    proposed JD-mirrored wording.
  - REQ-1002: Accepting a suggestion produces a `ChangeProposal` that swaps ONLY the surface term,
    preserving the fact; it must pass `validate_resume_truth` and the policy gate; identity/date/
    employer fields are never targeted.
  - REQ-1003: JD keywords with NO match are emitted as gaps (reuse `analyze_keyword_gaps`), never as
    terminology suggestions.
  - REQ-1004: A capability + CLI/MCP/API adapters + a plugin skill expose the analysis and (optional)
    application, consistent with the Phase-5 facade pattern and human-in-loop review.
  - REQ-1005: Each suggestion reports the deterministic expected keyword-match/skills-coverage delta if
    applied.
- **Non-Functional:**
  - NFR-1001: No fabrication is possible via this path (adversarial test: a no-match keyword can never
    become a terminology rewrite; an accepted rewrite never changes the underlying claim).
  - NFR-1002: Deterministic suggestion generation; `mypy --strict` + `ruff` clean; existing tests green.
  - NFR-1003: Reuses the existing alignment/policy/evidence gates — no parallel truth logic.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
```
RIT-I-0008 match provenance (kind: exact|stem|alias:<canonical>)
        │  (stem/alias hits = "present under a different word")
        ▼
terminology-alignment analysis (deterministic)  ->  [TerminologyAlignment{jd_keyword, current, location, proposed}]
        │  accept
        ▼
ChangeProposal (surface-term swap) -> policy gate (allowed: real-skill wording) -> apply_diffs
        -> validate_resume_truth (claim unchanged) -> before/after score delta
   (no-match JD keywords -> analyze_keyword_gaps -> GAP list, never a rewrite)
```
Suggestions are generated deterministically from RIT-I-0008 data; application reuses the Phase-4
alignment engine at low freedom with the truth gate intact. A new `TerminologyAlignment` result type
(minimal, in `schemas`) carries the suggestions.

## Detailed Design **[REQUIRED]**

1. Add a `TerminologyAlignment` result model (schemas) + the deterministic analyzer (likely in
   `matching`, consuming RIT-I-0008 provenance): for each JD keyword matched via stem/alias, locate the
   resume occurrence(s) and propose the JD-mirrored term.
2. Map an accepted suggestion to a `ChangeProposal` (surface swap only); run it through
   `policy.evaluate_change_policy` + `apply_diffs` + `validate_resume_truth`; compute before/after
   deltas with the deterministic scorers. Add the NFR-1001 adversarial tests.
3. Add a facade capability `align-terminology` (or fold into a `suggest-terminology` +
   apply-through-align path) + CLI/MCP/API adapters + a plugin skill for section-by-section review.
4. Tests: analyzer correctness (only stem/alias hits become suggestions; no-match → gap); truth-safety
   (accepted swap preserves the claim, passes truth validation; a fabricated term can never be
   produced); cross-surface parity; the real `resume-d` case (mentoring→mentorship, ESLint→linting
   surface mirrors) with the score delta.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Analyzer:** stem/alias hits yield suggestions with correct current/proposed wording + location;
  exact matches yield none; no-match keywords yield gaps (never suggestions).
- **Truth-safety (load-bearing):** an accepted terminology swap changes only the surface term and still
  passes `validate_resume_truth`; a no-match JD keyword (Kubernetes) can NEVER be turned into a
  terminology rewrite (adversarial).
- **Score impact:** before/after keyword_match/skills_coverage deltas are deterministic and correct.
- **Interfaces:** capability + CLI/MCP/API parity + plugin skill validate; human-in-loop surfaces the
  suggestions per section.
- Existing engine/alignment tests stay green.

## Alternatives Considered **[REQUIRED]**

- **Just report synonyms; let the user edit manually.** Weaker: the value is in the guided, truth-gated
  rewrite with a measured score delta; still, the analysis output alone is a valid first slice.
- **Do the rewrite with an LLM.** Deferred/unneeded: the swap is a deterministic surface substitution;
  the LLM/alignment-generation path exists for richer rewrites but isn't required to mirror a known term.
- **Auto-apply all terminology suggestions.** Rejected as default: keep human-in-loop (or an explicit
  non-interactive opt-in) so the candidate controls their wording; always truth-gated regardless.
- **Bypass the truth/policy gates for "just wording" changes.** Rejected: even wording changes route
  through the gates so the invariant (no unsupported claim, no identity/date edits) is universal.

## Implementation Plan **[REQUIRED]**

Decompose (later, on approval) into ~4-5 tasks: (1) `TerminologyAlignment` schema + deterministic
analyzer over RIT-I-0008 provenance + tests; (2) accept→ChangeProposal→policy→apply→truth path +
before/after deltas + NFR-1001 adversarial tests; (3) facade capability + CLI/MCP/API adapters +
parity; (4) plugin skill (section-by-section, human-in-loop) + validation; (5) real-resume integration
fixture + exports.

**Exit criteria:** stem/alias match provenance is turned into truth-gated terminology-alignment
suggestions that mirror the employer's exact wording of skills the candidate genuinely has; no-match
keywords remain gaps and can never become rewrites; accepted swaps preserve the claim (truth validation
passes) and report a deterministic score delta; exposed via a capability + all five surfaces + a
human-in-loop plugin skill; `ruff` + `mypy --strict` + `pytest` green.
