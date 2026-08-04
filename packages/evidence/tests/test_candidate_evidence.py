"""Tests for deterministic candidate-evidence extraction."""

from __future__ import annotations

from resume_kit_evidence.builder import (
    build_candidate_evidence,
    make_evidence_id,
    normalize_text,
)
from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.evidence import CandidateEvidence, EvidenceKind


def _resume() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {"name": "Ada Lovelace", "email": "ada@example.com"},
            "summary": "Backend engineer with a decade of Python.",
            "workExperience": [
                {
                    "company": "Acme",
                    "title": "Senior Engineer",
                    "description": ["Built a payments API", "Led a team of four"],
                }
            ],
            "personalProjects": [
                {"name": "Ledger", "description": ["Open-source ledger tool"]}
            ],
            "education": [{"degree": "BSc Computer Science", "institution": "MIT"}],
            "additional": {
                "technicalSkills": ["Python", "PostgreSQL"],
                "certificationsTraining": ["AWS Certified Developer"],
            },
        }
    )


def test_extracts_every_section() -> None:
    evidence = build_candidate_evidence(_resume())
    kinds = {ev.kind for ev in evidence}
    assert EvidenceKind.MASTER_RESUME in kinds
    assert EvidenceKind.WORK_HISTORY in kinds
    assert EvidenceKind.PROJECT in kinds
    assert EvidenceKind.EDUCATION in kinds
    assert EvidenceKind.SKILL in kinds
    assert EvidenceKind.CERTIFICATION in kinds

    contents = {ev.content for ev in evidence}
    assert "Built a payments API" in contents
    assert "Python" in contents
    assert "AWS Certified Developer" in contents


def test_never_invents_content() -> None:
    evidence = build_candidate_evidence(_resume())
    # Every record's content must trace back to a source field verbatim.
    resume = _resume()
    allowed = {
        resume.summary,
        "Built a payments API",
        "Led a team of four",
        "Open-source ledger tool",
        "Python",
        "PostgreSQL",
        "AWS Certified Developer",
        "Ledger",
        "Senior Engineer — Acme",
        "BSc Computer Science — MIT",
    }
    for ev in evidence:
        assert ev.content in allowed


def test_ids_are_stable_across_calls() -> None:
    first = build_candidate_evidence(_resume())
    second = build_candidate_evidence(_resume())
    assert [e.id for e in first] == [e.id for e in second]


def test_ids_vary_only_by_content_not_call_order() -> None:
    resume = _resume()
    # Reversing a source list changes iteration order but not the id set.
    reordered = resume.model_copy(deep=True)
    reordered.additional.technicalSkills = list(
        reversed(reordered.additional.technicalSkills)
    )
    ids_a = {e.id for e in build_candidate_evidence(resume)}
    ids_b = {e.id for e in build_candidate_evidence(reordered)}
    assert ids_a == ids_b


def test_id_is_content_addressed() -> None:
    assert make_evidence_id(EvidenceKind.SKILL, "Python") == make_evidence_id(
        EvidenceKind.SKILL, "  python  "
    )
    assert make_evidence_id(EvidenceKind.SKILL, "Python") != make_evidence_id(
        EvidenceKind.CERTIFICATION, "Python"
    )


def test_deduplicates_identical_records() -> None:
    resume = _resume()
    resume.additional.technicalSkills = ["Python", "python", "PYTHON"]
    evidence = build_candidate_evidence(resume)
    skill_ids = [e.id for e in evidence if e.kind is EvidenceKind.SKILL]
    assert len(skill_ids) == len(set(skill_ids)) == 1


def test_approved_string_claims_are_user_confirmed() -> None:
    evidence = build_candidate_evidence(
        _resume(), approved_claims=["Mentored junior engineers"]
    )
    confirmed = [e for e in evidence if e.user_confirmed]
    assert len(confirmed) == 1
    assert confirmed[0].kind is EvidenceKind.USER_STATEMENT
    assert confirmed[0].content == "Mentored junior engineers"


def test_approved_evidence_records_are_forced_confirmed() -> None:
    approved = CandidateEvidence(
        id="ignored",
        kind=EvidenceKind.SKILL,
        content="Rust",
        user_confirmed=False,
    )
    evidence = build_candidate_evidence(_resume(), approved_claims=[approved])
    rust = [e for e in evidence if e.content == "Rust"]
    assert len(rust) == 1
    assert rust[0].user_confirmed is True
    assert rust[0].id == make_evidence_id(EvidenceKind.SKILL, "Rust")


def test_empty_fields_produce_no_evidence() -> None:
    resume = ResumeDocument()
    assert build_candidate_evidence(resume) == []


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  Hello   World  ") == "hello world"
