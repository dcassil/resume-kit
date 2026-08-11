"""Conservative fuzzy PROPOSER of terminology-alias candidates (RIT-T-0165).

The deterministic matcher and ``analyze_terminology_alignment`` are CLOSED-lexicon:
they can only mirror pairs the seed lexicon or the project ``alias_file`` already
contains. On a fresh project the project file is empty, so a resume that says
``responsive UI`` scores as missing the JD's ``responsive design`` and coverage is
understated for phrasing differences the candidate genuinely satisfies.

This module adds the one genuinely new bit the seeding/growth flow needs: a
conservative fuzzy/stemmed PRE-FILTER that *proposes* candidate
``(jd_keyword, resume_phrase)`` synonym pairs for a human to confirm. It is a
PROPOSER ONLY — it never writes to the alias file, never mutates the resume, and
its output is always ``confirmed=False``. Every candidate must still pass human
confirmation and the existing truth gate (the ``learn-terminology`` loop) before
an alias is written. Unconfirmed candidates never touch scoring, so the
conservative-lexicon guarantee is preserved.

Determinism: pure, offline, no embeddings. It reuses the same tokenization,
n-gram windowing, and normalization primitives the matcher uses, so its notion of
"already matched" agrees exactly with the deterministic score.
"""

from __future__ import annotations

from resume_kit_schemas import TerminologyCandidate
from resume_kit_terms import surface_form
from resume_kit_terms.normalize import normalize

from .keywords import (
    _alias_windows,
    _extract_all_text,
    _JdKeywordsInput,
    _match_keyword_in_text,
    _ResumeInput,
    _to_jd_keywords_dict,
    _to_resume_dict,
)
from .terminology import _string_leaves

__all__ = [
    "propose_terminology_candidates",
]

# A single-token difference is only proposed when the two tokens are near each
# other: small absolute edit distance AND small relative to length. This catches
# ``postgres`` ↔ ``postgresql`` while rejecting unrelated tokens like
# ``design`` ↔ ``performance``.
_MAX_TOKEN_EDIT_DISTANCE = 3
_MAX_TOKEN_EDIT_RATIO = 0.4

# A multi-token window is only proposed when it aligns POSITIONALLY with the
# keyword: same token count, every position stem-equal EXCEPT exactly one. This
# catches ``responsive design`` ↔ ``responsive UI`` (differ only at position 1)
# while rejecting ``mobile web`` ↔ ``a mobile`` (a shifted window that shares a
# token but does not align) and ``web performance`` ↔ ``web design team``.


def _levenshtein(a: str, b: str) -> int:
    """Return the Levenshtein edit distance between *a* and *b* (iterative DP)."""
    if a == b:
        return 0
    if not a:
        return len(b)
    if not b:
        return len(a)
    previous = list(range(len(b) + 1))
    for i, char_a in enumerate(a, start=1):
        current = [i]
        for j, char_b in enumerate(b, start=1):
            cost = 0 if char_a == char_b else 1
            current.append(
                min(
                    previous[j] + 1,  # deletion
                    current[j - 1] + 1,  # insertion
                    previous[j - 1] + cost,  # substitution
                )
            )
        previous = current
    return previous[-1]


#: A shared anchor token must be at least this long (normalized) to count as a
#: meaningful anchor. This rejects generic short connectors like ``web`` while
#: keeping content anchors like ``respons`` (stem of "responsive").
_MIN_ANCHOR_TOKEN_LEN = 4


def _tokens(term: str) -> list[str]:
    """Return the normalized (stemmed) tokens of *term*, dropping empties."""
    normalized = normalize(term)
    return [tok for tok in normalized.split(" ") if tok]


def _surface_tokens(term: str) -> list[str]:
    """Return the surface-form (unstemmed) tokens of *term*, dropping empties."""
    return [tok for tok in surface_form(term).split(" ") if tok]


def _near_tokens(a: str, b: str) -> bool:
    """Return True if two single tokens are a small-edit near-match.

    Compared on SURFACE forms (unstemmed): stemming would collapse
    ``postgres``/``postgresql`` to one stem and hide the very near-match we want
    to propose. Identical surface tokens are an exact hit, not a candidate.
    """
    if a == b:
        return False
    distance = _levenshtein(a, b)
    longest = max(len(a), len(b))
    return distance <= _MAX_TOKEN_EDIT_DISTANCE and distance <= _MAX_TOKEN_EDIT_RATIO * longest


def _is_candidate_pair(keyword: str, window: str) -> bool:
    """Return True if *window* is a conservative near-match for *keyword*.

    Two acceptance shapes, both requiring a genuine anchor and exactly one
    differing token:

    * **Single-token**: both are one token, differing but within a small SURFACE
      edit distance (``postgres`` ↔ ``postgresql``).
    * **Multi-token**: same token count and POSITIONALLY aligned on stems — every
      position stem-equal except exactly one, AND every shared anchor stem is
      long enough to be meaningful (``respons`` yes, ``web`` no). The aligned,
      specific anchor rejects shifted windows that merely share a token
      (``mobile web`` vs ``a mobile``) and phrases joined only by a generic word
      (``web performance`` vs ``web design``).
    """
    kw_stems = _tokens(keyword)
    win_stems = _tokens(window)
    if not kw_stems or not win_stems:
        return False
    if len(kw_stems) != len(win_stems):
        return False

    if len(kw_stems) == 1:
        kw_surface = _surface_tokens(keyword)
        win_surface = _surface_tokens(window)
        if len(kw_surface) != 1 or len(win_surface) != 1:
            return False
        return _near_tokens(kw_surface[0], win_surface[0])

    differing = 0
    for kw, win in zip(kw_stems, win_stems, strict=True):
        if kw != win:
            differing += 1
        elif len(kw) < _MIN_ANCHOR_TOKEN_LEN:
            # A shared-but-generic short anchor (e.g. "web") does not count.
            return False
    return differing == 1


def _reason(keyword: str, window: str) -> str:
    """Return a human-readable, advisory-only reason string for a candidate."""
    kw_stems = _tokens(keyword)
    win_stems = _tokens(window)
    if len(kw_stems) == 1:
        distance = _levenshtein(_surface_tokens(keyword)[0], _surface_tokens(window)[0])
        return f"single-token near-match (edit distance {distance})"
    anchor = ", ".join(
        f"'{kw}'"
        for kw, win in zip(kw_stems, win_stems, strict=True)
        if kw == win
    )
    return f"aligned shared stem(s) {anchor} with one differing token"


def propose_terminology_candidates(
    job: _JdKeywordsInput,
    resume: _ResumeInput,
) -> list[TerminologyCandidate]:
    """Propose conservative fuzzy alias candidates for review (RIT-T-0165).

    For each JD keyword that is *missing* from *resume* under the current
    (seed + project) alias index, scans the resume's token windows for a
    conservative near-match and PROPOSES it as a ``(jd_keyword, resume_phrase)``
    pair. The output is deterministic, de-duplicated, and always unconfirmed —
    it feeds the human-confirmation + truth gate, it never writes an alias.

    Args:
        job: A ``JobDescription`` or a dict with ``required_skills`` /
            ``preferred_skills`` / ``keywords``.
        resume: The resume to inspect (``ResumeDocument`` or dict). The project
            ``alias_file`` (if any) is already honored via the ambient alias
            index, so pairs it already knows are not re-proposed.

    Returns:
        Sorted, de-duplicated list of :class:`TerminologyCandidate`. Keywords the
        resume already satisfies (exact/alias) and keywords with no conservative
        near-match contribute nothing.
    """
    jd_dict = _to_jd_keywords_dict(job)
    resume_dict = _to_resume_dict(resume)

    all_keywords: set[str] = set()
    all_keywords.update(jd_dict.get("required_skills", []))
    all_keywords.update(jd_dict.get("preferred_skills", []))
    all_keywords.update(jd_dict.get("keywords", []))

    resume_text = _extract_all_text(resume_dict).lower()
    leaves = _string_leaves(resume_dict, "")

    candidates: list[TerminologyCandidate] = []
    for keyword in sorted(all_keywords):
        if not keyword.strip():
            continue
        # Skip keywords the deterministic matcher already satisfies (exact/alias)
        # — those are not missing, so there is nothing to seed.
        if _match_keyword_in_text(keyword, resume_text) is not None:
            continue
        keyword_token_count = len(_tokens(keyword))
        if keyword_token_count == 0:
            continue

        # surface_form(window) key -> (display phrase, locations, reason). Group
        # repeated occurrences of the same resume wording (modulo case/spacing)
        # into one candidate with all its locations. The DISPLAY phrase keeps the
        # resume's original wording so the confirmed alias reads naturally.
        grouped: dict[str, tuple[str, list[str], str]] = {}
        for path, text in leaves:
            for window in _alias_windows(text, keyword_token_count):
                if len(_tokens(window)) != keyword_token_count:
                    continue
                if not _is_candidate_pair(keyword, window):
                    continue
                key = surface_form(window)
                existing = grouped.get(key)
                if existing is None:
                    grouped[key] = (window, [path], _reason(keyword, window))
                elif path not in existing[1]:
                    existing[1].append(path)
        for key in sorted(grouped):
            phrase, locations, reason = grouped[key]
            candidates.append(
                TerminologyCandidate(
                    jd_keyword=keyword,
                    resume_phrase=phrase,
                    locations=sorted(locations),
                    reason=reason,
                )
            )

    candidates.sort(key=lambda c: (c.jd_keyword, c.resume_phrase, c.locations))
    return candidates
