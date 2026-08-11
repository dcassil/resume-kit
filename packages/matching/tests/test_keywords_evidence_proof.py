"""Evidence-as-proof fold-in for ``analyze_keyword_gaps`` (RIT-T-0158).

Confirmed ``CandidateEvidence`` is projected into the SAME master-equivalent proof
surface the injectable classifier already reads, so a keyword that is missing from
BOTH the tailored and master resumes becomes ``injectable`` once backing evidence
exists — with no second proof mechanism and no change to the injection consumer's
proof logic.

The scoping guarantee is load-bearing: evidence for requirement X must NOT make an
unrelated requirement Y injectable. That is enforced by the same whole-term matcher
the rest of the engine uses — a keyword only becomes injectable if it actually
appears (exact / alias) in the confirmed evidence's own content.
"""

from __future__ import annotations

from resume_kit_matching import analyze_keyword_gaps
from resume_kit_schemas import JobDescription, Requirement, ResumeDocument
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind


def _resume(summary: str) -> ResumeDocument:
    """A minimal resume carrying only a summary line (enough for text matching)."""
    return ResumeDocument.model_validate({"summary": summary})


def _job(*terms: str) -> JobDescription:
    """A job requiring each of ``terms`` as a concrete required keyword."""
    return JobDescription.model_validate(
        {
            "title": "Engineer",
            "company": "Acme",
            "requirements": [
                Requirement(text=term, keywords=[term]).model_dump() for term in terms
            ],
        }
    )


def _evidence(content: str) -> CandidateEvidence:
    """A user-confirmed evidence record whose content is the provable text."""
    return CandidateEvidence(
        id=f"ev-{abs(hash(content))}",
        kind=EvidenceKind.USER_STATEMENT,
        content=content,
        user_confirmed=True,
    )


def test_confirmed_evidence_turns_non_injectable_into_injectable() -> None:
    """Before evidence: kubernetes is non_injectable. After: injectable — same route."""
    job = _job("kubernetes")
    # Neither the tailored nor the master resume mentions kubernetes.
    tailored = _resume("Backend engineer building APIs.")
    master = _resume("Backend engineer with a long history of shipping services.")

    before = analyze_keyword_gaps(job, tailored, master)
    assert "kubernetes" in before.missing_keywords
    assert "kubernetes" in before.non_injectable_keywords
    assert "kubernetes" not in before.injectable_keywords

    # A confirmed answer captured grounding evidence mentioning kubernetes.
    after = analyze_keyword_gaps(
        job,
        tailored,
        master,
        confirmed_evidence=[_evidence("Ran a production Kubernetes cluster at Acme.")],
    )
    assert "kubernetes" in after.missing_keywords  # still absent from the resume
    assert "kubernetes" in after.injectable_keywords
    assert "kubernetes" not in after.non_injectable_keywords


def test_no_evidence_stays_non_injectable() -> None:
    """Without backing evidence a both-missing keyword stays non_injectable."""
    job = _job("kubernetes")
    tailored = _resume("Backend engineer building APIs.")
    master = _resume("Backend engineer shipping services.")

    result = analyze_keyword_gaps(job, tailored, master, confirmed_evidence=[])
    assert "kubernetes" in result.non_injectable_keywords
    assert "kubernetes" not in result.injectable_keywords


def test_evidence_for_x_does_not_make_unrelated_y_injectable() -> None:
    """Evidence proving X must not spuriously make an unrelated keyword Y injectable."""
    job = _job("kubernetes", "fedramp")
    tailored = _resume("Backend engineer building APIs.")
    master = _resume("Backend engineer shipping services.")

    result = analyze_keyword_gaps(
        job,
        tailored,
        master,
        confirmed_evidence=[_evidence("Ran a production Kubernetes cluster at Acme.")],
    )
    # X is proven and becomes injectable...
    assert "kubernetes" in result.injectable_keywords
    # ...but the unrelated Y stays non_injectable — evidence is scoped to its content.
    assert "fedramp" in result.non_injectable_keywords
    assert "fedramp" not in result.injectable_keywords


def test_unconfirmed_evidence_does_not_prove() -> None:
    """Only user-confirmed evidence contributes to the proof surface."""
    job = _job("kubernetes")
    tailored = _resume("Backend engineer building APIs.")
    master = _resume("Backend engineer shipping services.")

    unconfirmed = CandidateEvidence(
        id="ev-unconfirmed",
        kind=EvidenceKind.USER_STATEMENT,
        content="Ran a production Kubernetes cluster at Acme.",
        user_confirmed=False,
    )
    result = analyze_keyword_gaps(job, tailored, master, confirmed_evidence=[unconfirmed])
    assert "kubernetes" in result.non_injectable_keywords
    assert "kubernetes" not in result.injectable_keywords


def test_evidence_matched_keyword_not_forced_injectable_when_in_resume() -> None:
    """A keyword already present in the tailored resume is matched, never re-classified.

    Evidence must only affect the injectable/non_injectable split for MISSING keywords;
    it must never turn a matched keyword into a gap.
    """
    job = _job("kubernetes")
    tailored = _resume("Backend engineer running Kubernetes in production.")
    master = _resume("Backend engineer shipping services.")

    result = analyze_keyword_gaps(
        job,
        tailored,
        master,
        confirmed_evidence=[_evidence("Ran a production Kubernetes cluster.")],
    )
    assert "kubernetes" not in result.missing_keywords
    assert "kubernetes" not in result.injectable_keywords
    assert "kubernetes" not in result.non_injectable_keywords
