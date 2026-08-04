---
id: synonym-aware-deterministic
level: initiative
title: "Synonym-Aware Deterministic Matching (engine core)"
short_code: "RIT-I-0008"
created_at: 2026-08-04T18:50:56+00:00
updated_at: 2026-08-04T21:33:24.797435+00:00
parent: RIT-V-0001
blocked_by: []
archived: false

tags:
  - "#initiative"
  - "#phase/completed"


exit_criteria_met: false
estimated_complexity: L
strategy_id: NULL
initiative_id: synonym-aware-deterministic
---

# Synonym-Aware Deterministic Matching (engine core) Initiative

## Context **[REQUIRED]**

The deterministic keyword/skills matching in `packages/matching` and `packages/ats` compares terms by
whole-term, casefolded, punctuation-naive string matching. Real ATS runs on a resume (`resume-d`)
against a Staff Full-Stack posting surfaced the limitation directly: `skills_coverage` was correct
once a structured `JobDescription` existed (89.1), but genuine matches were still missed —
`"mentorship"` (resume says "mentoring"), `"linting"` (resume says ESLint / static analysis) — because
the matcher cannot bridge **morphological variants** (mentor/mentoring/mentorship) or **known
synonyms** (k8s ↔ Kubernetes, JS ↔ JavaScript, Node ↔ Node.js, Postgres ↔ PostgreSQL, RLS ↔ row-level
security). This under-reports the score and pollutes the gap list with false gaps.

This initiative makes the **deterministic** matcher synonym-aware so the score is honest — with NO
LLM and NO new heavy dependency — keeping the product's core "deterministic where practical" guarantee.
It is the foundation the other two synonym initiatives build on (agent-grown alias index; terminology
alignment). The optional LLM/embeddings semantic tier is explicitly OUT of scope (deferred).

Integration points already identified:
- `packages/matching/src/resume_kit_matching/keywords.py` — `_keyword_in_text` (:44),
  `_normalize_skill_key` (:58, currently `casefold` + whitespace collapse), `_extract_jd_skill_keys`,
  `calculate_keyword_match` (:196), `analyze_keyword_gaps` (:232). These are where a normalized,
  synonym-expanded comparison must slot in.
- `packages/ats/src/resume_kit_ats/engine.py` — `_keyword_in_text` (:69), `_compute_skills_coverage`
  (:82). `compute_ats_score` weights keyword_match 0.55 / skills_coverage 0.25 / section_completeness
  0.20; both keyword paths must use the same normalization so scores are consistent.

## Goals & Non-Goals **[REQUIRED]**

**Goals:**
- Add a **shared deterministic term-normalizer** used by BOTH `matching` and `ats` (single source of
  truth — no divergent matching between the two packages). It performs, in order: Unicode/ASCII fold
  (so `·`, curly quotes, en/em dashes don't defeat matching), casefold, punctuation/whitespace
  normalization, and **stemming/lemmatization** (Snowball/Porter — pure Python, e.g. a vendored or
  light dependency) so `mentor / mentoring / mentorship / mentored`, `test / testing / tested`,
  `architect / architecture` collapse to a common stem.
- Add a **curated alias lexicon** (versioned data in the package — a JSON/py mapping) for genuine
  synonyms that stemming cannot bridge: canonical-skill → alias set. Seed it with the high-frequency
  tech vocabulary (k8s↔Kubernetes, JS↔JavaScript, Node↔Node.js, Postgres/PostgreSQL, RLS↔row-level
  security, GH Actions↔GitHub Actions, CI/CD↔continuous integration, TS↔TypeScript, …). The lexicon is
  extensible (Layer-2 agent-grown index appends to the same format).
- Wire `_keyword_in_text` / `_normalize_skill_key` / `_compute_skills_coverage` to compare via
  (normalize → stem → alias-expand), so `keyword_match`, `skills_coverage`, and `analyze_keyword_gaps`
  all become synonym-aware and consistent.
- Every match remains **explainable**: the report can say WHY a JD keyword counted as present (exact,
  stem, or alias `<canonical>`), so downstream (terminology alignment) knows it was a synonym hit.
- Deterministic, offline, characterization-tested. Existing tests stay green; add tests proving the
  specific real-world cases (mentoring↔mentorship, ESLint/linting, k8s↔Kubernetes) now match and that
  true non-matches (Kubernetes when truly absent, React≠Vue) still do NOT match (no over-matching).

**Non-Goals:**
- LLM- or embeddings-based semantic matching (the optional tier) — deferred; must not be required.
- The agent-grown alias index (Layer 2 = separate initiative RIT-I-0009) — this initiative only
  defines the lexicon FORMAT + seed and consumes it; it does not add agent tooling.
- Terminology-alignment / resume-rewrite suggestions (RIT-I-0010) — this initiative surfaces the
  synonym-match provenance those suggestions need, but does not generate rewrites.
- Fuzzy/edit-distance matching (typo tolerance) — out of scope; risks false positives.

## Requirements **[CONDITIONAL: Requirements-Heavy Initiative]**

### System Requirements
- **Functional:**
  - REQ-801: A single normalization function (Unicode-fold → casefold → punctuation/space normalize →
    stem) lives in one place and is imported by both `matching` and `ats`; there is no second,
    divergent normalizer.
  - REQ-802: A curated alias lexicon ships as versioned package data with a documented, append-only
    format (canonical → aliases), seeded with the common tech-synonym set.
  - REQ-803: `_keyword_in_text`, `_normalize_skill_key`, `_extract_jd_skill_keys`, and
    `_compute_skills_coverage` match via normalize+stem+alias-expand; `calculate_keyword_match`,
    `analyze_keyword_gaps`, `check_job_match`, and `compute_ats_score` reflect the synonym-aware result.
  - REQ-804: Each keyword match is annotated with its match KIND (`exact` | `stem` | `alias:<canonical>`)
    so callers can distinguish exact vs synonym hits (feeds RIT-I-0010).
  - REQ-805: `analyze_keyword_gaps` no longer lists a JD keyword as missing when the resume contains a
    stem/alias equivalent.
- **Non-Functional:**
  - NFR-801: No LLM, no network, no embeddings model; the stemmer is pure Python (vendored or a light,
    well-established dependency confined to `matching`/a shared low-level package).
  - NFR-802: Deterministic — identical inputs yield identical matches and annotations.
  - NFR-803: `mypy --strict` + `ruff` clean; existing matching/ats tests stay green; no over-matching
    regressions (guard tests for React≠Vue, Java≠JavaScript-as-distinct-where-intended).
  - NFR-804: Normalization is O(terms) with a precompiled alias index; no measurable slowdown on the
    existing suites.

## Architecture **[CONDITIONAL: Technically Complex Initiative]**

### Overview
```
shared normalizer + alias index  (new module; home = matching, or a tiny shared util both import)
   normalize(term) -> canonical form: ascii-fold -> casefold -> punct/space -> stem
   alias_index: canonical -> {aliases}; expand(term) -> {st's canonical + alias canonicals}
   match(a, b) -> (bool, kind)  where kind ∈ {exact, stem, alias:<canonical>}
        ▲                                   ▲
packages/matching (_keyword_in_text,   packages/ats (_keyword_in_text,
  _normalize_skill_key, gaps, match)      _compute_skills_coverage)
```
Both engine packages call the shared normalizer/matcher, so keyword_match and skills_coverage agree.
The alias lexicon is data (JSON) loaded once; RIT-I-0009 appends to the same file/format. Match
provenance (`kind`) is threaded through the gap/keyword results (a small schema addition if needed, or
carried in existing structures) so RIT-I-0010 can find synonym hits.

## Detailed Design **[REQUIRED]**

1. **DECIDED (2026-08-04):** The normalizer lives in a new dedicated package
   **`resume-kit-terms`** (workspace member under `packages/terms`), depending only on `schemas`.
   Both `ats` and `matching` add a dependency on it. Rationale: `matching` already depends on `ats`
   (matching → ats → core → schemas), so `ats` is the lower package; putting shared term-matching in
   `ats` would name "matching" primitives under `ats`, and putting it in `core` would pollute the
   LLM-provider/storage infra module. A dedicated tiny package gives the clearest ownership and keeps
   the dependency graph acyclic: `schemas ← terms ← {ats, matching}`. The **stemmer** is the
   pure-Python **`snowballstemmer`** PyPI dependency (offline, deterministic, no compiled deps),
   confined to `resume-kit-terms`. This package must be added to `packaging/` + PyPI publish flow.
2. Implement `normalize(term)` (ascii-fold via `unicodedata`, casefold, punctuation/space collapse,
   Snowball stem) and an `AliasIndex` built from the seed lexicon data file; expose `match(a,b) ->
   (bool, kind)`.
3. Seed `aliases.json` with the common tech-synonym set (documented format + a test that it loads and
   round-trips).
4. Rewire `matching` (`_keyword_in_text`, `_normalize_skill_key`, `_extract_jd_skill_keys`,
   `analyze_keyword_gaps`, `calculate_keyword_match`) and `ats` (`_keyword_in_text`,
   `_compute_skills_coverage`) to use it; thread the `kind` annotation through the gap/keyword outputs.
5. Characterization + new tests: keep upstream parity where behavior is unchanged; add the synonym
   cases and the anti-over-match guards.

## Testing Strategy **[CONDITIONAL: Separate Testing Initiative]**

- **Unit** the normalizer/matcher: ascii-fold (`·`/curly quotes), casefold, stem families
  (mentor/mentoring/mentorship), alias hits (k8s↔Kubernetes, JS↔JavaScript, RLS↔row-level security),
  and match `kind` correctness.
- **Anti-over-match guards:** React≠Vue, Kubernetes-truly-absent stays a gap, distinct skills not
  collapsed by aggressive stemming.
- **Integration:** `analyze_keyword_gaps` drops false gaps (mentoring, linting) for the real
  `resume-d` vs Staff-FS fixture; `compute_ats_score` skills_coverage/keyword_match rise appropriately
  and remain deterministic.
- Existing 900+ matching/ats tests stay green (characterization).
- Gate: `uv run ruff check packages tests && uv run mypy <engine packages> && uv run pytest`.

## Alternatives Considered **[REQUIRED]**

- **Pure hand-maintained synonym index (no stemming).** Rejected as the sole approach: morphological
  variants (mentor*) explode the index and are better handled by a stemmer; the lexicon is reserved for
  true synonyms stemming can't reach.
- **Embeddings / semantic similarity.** Deferred (the excluded optional tier): heavy dependency,
  threshold tuning, false positives (React~Vue), and it breaks the deterministic/offline guarantee.
- **LLM judge per keyword.** Rejected here: needs a provider, non-deterministic, slow/costly — wrong
  tool for token matching; reserved for qualitative match reasoning elsewhere.
- **Edit-distance/fuzzy matching.** Rejected: typo tolerance risks false positives on short skill
  tokens (Java/JavaScript, Go/Golang vs unrelated).
- **Duplicating the normalizer in each package.** Rejected: matching and ats must agree; one shared
  normalizer prevents score divergence.

## Implementation Plan **[REQUIRED]**

Decompose (later, on approval) into ~4-6 file-disjoint tasks: (1) scaffold shared normalizer + alias
index module + decide home; (2) seed `aliases.json` + format doc + loader tests; (3) rewire `matching`
(+ thread `kind`) with characterization + synonym tests; (4) rewire `ats` skills_coverage/keyword paths
+ tests; (5) integration test on the real resume-d/Staff-FS fixture + anti-over-match guards; (6)
exports/attribution if any upstream logic is touched.

**Exit criteria:** a single deterministic normalize+stem+alias matcher is used by matching and ats;
`skills_coverage`/`keyword_match`/`analyze_keyword_gaps` are synonym-aware and consistent; each match
carries an explainable `kind`; the real-world misses (mentoring↔mentorship, ESLint/linting,
k8s↔Kubernetes) now match while true gaps and unrelated terms do not; no LLM/embeddings/network; `ruff`
+ `mypy --strict` + `pytest` green with existing tests passing.