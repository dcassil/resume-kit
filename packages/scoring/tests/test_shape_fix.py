"""Non-destructive shape canonicalizer and gate tests (RIT-T-0136)."""

from __future__ import annotations

from resume_kit_policy import default_shape_policy
from resume_kit_schemas.canonical import CanonicalSection, SkillGroup
from resume_kit_schemas.resume import ResumeDocument
from resume_kit_schemas.shape import (
    ContentFate,
    ContentLedger,
    ContentLedgerEntry,
    ShapeFixResult,
)
from resume_kit_scoring import (
    analyze_resume_shape,
    apply_shape_transforms,
    claims_preserved_across_sections,
    content_ledger_ok,
)


def _resume(
    *,
    skills: list[str] | None = None,
    custom_sections: dict[str, object] | None = None,
    work_bullets: list[str] | None = None,
) -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jane Engineer",
                "email": "jane@example.com",
                "phone": "555-0100",
                "title": "Staff Engineer",
            },
            "summary": "Builds reliable product platforms.",
            "workExperience": [
                {
                    "id": 1,
                    "title": "Staff Engineer",
                    "company": "Acme",
                    "years": "2020-2024",
                    "description": work_bullets or ["Built reliable APIs."],
                }
            ],
            "education": [
                {
                    "institution": "State University",
                    "degree": "BS Computer Science",
                    "years": "2016",
                }
            ],
            "additional": {"technicalSkills": skills or []},
            "customSections": custom_sections or {},
        }
    )


def _apply(resume: ResumeDocument) -> ShapeFixResult:
    report = analyze_resume_shape(resume, default_shape_policy())
    return apply_shape_transforms(resume, report)


def test_empty_company_entry_canonicalizes_without_raising() -> None:
    """RIT-T-0156 B1: an empty ``company`` (legal in ResumeDocument) must not
    crash canonicalization. Date-grouped umbrella headings carry the group in
    ``title`` and leave ``company`` empty."""
    resume = ResumeDocument.model_validate(
        {
            "personalInfo": {
                "name": "Jane Engineer",
                "email": "jane@example.com",
                "phone": "555-0100",
                "title": "Staff Engineer",
            },
            "summary": "Builds reliable product platforms.",
            "workExperience": [
                {
                    "id": 1,
                    "title": "Ventures & Consulting",
                    "company": "",
                    "years": "2020-2024",
                    "description": ["Advised early-stage teams."],
                }
            ],
            "education": [
                {
                    "institution": "State University",
                    "degree": "BS Computer Science",
                    "years": "2016",
                }
            ],
            "additional": {"technicalSkills": []},
            "customSections": {},
        }
    )

    result = _apply(resume)

    assert result.resume.work[0].organization == ""
    assert result.resume.work[0].title == "Ventures & Consulting"


def test_content_ledger_ok_accepts_accounted_tokens() -> None:
    ledger = ContentLedger(
        entries=[
            ContentLedgerEntry(
                token="python",
                fate=ContentFate.MOVED,
                source_path="additional.technicalSkills[0]",
                target_path="skills[0].keywords[0]",
            ),
            ContentLedgerEntry(
                token="skills",
                fate=ContentFate.DROPPED_AS_HEADING,
                source_path="customSections.skills.strings[0]",
                reason="embedded heading",
            ),
        ]
    )

    assert content_ledger_ok(ledger)


def test_content_ledger_ok_refuses_unresolved_or_targetless_tokens() -> None:
    unresolved = ContentLedger(
        entries=[
            ContentLedgerEntry(
                token="rust",
                fate=ContentFate.UNRESOLVED,
                source_path="customSections.core.text",
            )
        ]
    )
    targetless_move = ContentLedger(
        entries=[
            ContentLedgerEntry(
                token="python",
                fate=ContentFate.MOVED,
                source_path="additional.technicalSkills[0]",
            )
        ]
    )

    assert not content_ledger_ok(unresolved)
    assert not content_ledger_ok(targetless_move)


def test_merge_that_loses_a_skill_fails_ledger_gate() -> None:
    ledger = ContentLedger(
        entries=[
            ContentLedgerEntry(
                token="python",
                fate=ContentFate.MOVED,
                source_path="additional.technicalSkills[0]",
                target_path="skills[0].keywords[0]",
            ),
            ContentLedgerEntry(
                token="rust",
                fate=ContentFate.UNRESOLVED,
                source_path="customSections.Technical Skills.strings[1]",
                reason="missing from merged skill group",
            ),
        ]
    )

    assert not content_ledger_ok(ledger)


def test_moving_technical_skills_custom_section_preserves_claims() -> None:
    before = _resume(
        custom_sections={
            "Technical Skills": {
                "sectionType": "stringList",
                "strings": ["Python", "TypeScript"],
            }
        }
    )

    result = _apply(before)

    assert result.resume.skills[0].keywords == ["Python", "TypeScript"]
    assert claims_preserved_across_sections(before, result.resume)


def test_claims_preserved_across_sections_refuses_added_skill() -> None:
    before = _resume(skills=["Python"])
    result = _apply(before)
    after = result.resume.model_copy(
        update={
            "skills": [
                SkillGroup(
                    name="Technical Skills",
                    keywords=["Python", "Rust"],
                )
            ]
        }
    )

    assert not claims_preserved_across_sections(before, after)


def test_redundant_skill_sections_are_canonicalized_and_fully_accounted() -> None:
    before = _resume(
        skills=["Python", "TypeScript"],
        custom_sections={
            "Core Skills": {
                "sectionType": "stringList",
                "strings": ["Python", "React", "AWS"],
            },
            "Technical Skills": {
                "sectionType": "stringList",
                "strings": ["Technical Skills", "Python", "TypeScript", "React", "AWS"],
            },
        },
    )

    result = _apply(before)

    assert result.resume.work[0].achievements[0].text == "Built reliable APIs."
    assert result.resume.skills[0].keywords == ["Python", "TypeScript", "React", "AWS"]
    assert content_ledger_ok(result.ledger)
    assert claims_preserved_across_sections(before, result.resume)
    assert any(
        entry.fate is ContentFate.DROPPED_AS_HEADING and entry.token == "technical"
        for entry in result.ledger.entries
    )
    assert any(entry.fate is ContentFate.DEDUPED for entry in result.ledger.entries)


def test_other_custom_section_and_summary_pass_ledger_gate() -> None:
    # RIT-T-0161: content routed to "other" (no auto/explicit canonical target)
    # plus summary content must reach ledger_ok True without dropping content.
    before = _resume(
        custom_sections={
            "Community": {
                "sectionType": "stringList",
                "strings": ["Mentored bootcamp students", "Organized local meetups"],
            }
        }
    )

    result = _apply(before)

    assert content_ledger_ok(result.ledger)
    assert claims_preserved_across_sections(before, result.resume)
    # No token is silently dropped: every entry is an accounted fate.
    assert all(entry.fate is not ContentFate.UNRESOLVED for entry in result.ledger.entries)
    # The "other" content is preserved as a canonical custom slot (faithful, not dropped).
    preserved_text = " ".join(
        line for section in result.resume.custom for line in section.lines
    )
    assert "Mentored bootcamp students" in preserved_text
    # Summary content lands on basics.summary (shape-stage target exists).
    assert result.resume.basics.summary == "Builds reliable product platforms."
    assert any(
        entry.fate is ContentFate.PRESERVED_AS_OTHER for entry in result.ledger.entries
    )


def test_custom_to_skills_mapping_is_satisfiable_and_tokenized() -> None:
    # RIT-T-0162: explicit custom->skills mapping with a comma-delimited line.
    before = _resume(
        custom_sections={
            "Core Competencies": {
                "sectionType": "stringList",
                "strings": ["Python, CI/CD, A/B testing", "Distributed Systems"],
            }
        }
    )
    report = analyze_resume_shape(before, default_shape_policy())
    result = apply_shape_transforms(
        before,
        report,
        {"Core Competencies": CanonicalSection.SKILLS},
    )

    # B1: mapping is satisfiable (claim sets computed symmetrically).
    assert content_ledger_ok(result.ledger)
    assert claims_preserved_across_sections(before, result.resume)

    # B2: discrete tokens, delimiter-aware; "CI/CD" and "A/B testing" not over-split;
    # neither the heading nor the whole comma-line survives as a single skill.
    keywords = result.resume.skills[0].keywords
    assert "Python" in keywords
    assert "CI/CD" in keywords
    assert "A/B testing" in keywords
    assert "Distributed Systems" in keywords
    assert "Python, CI/CD, A/B testing" not in keywords
    assert "Core Competencies" not in keywords


def test_prose_heavy_mapped_section_is_deferred_and_refused_by_ledger() -> None:
    before = _resume(
        custom_sections={
            "Core Skills": {
                "sectionType": "text",
                "text": "Python, React, and payments platform leadership.",
            }
        }
    )

    result = _apply(before)

    assert not content_ledger_ok(result.ledger)
    assert [finding.section for finding in result.deferred_findings] == ["Core Skills"]
