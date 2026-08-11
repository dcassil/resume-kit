"""Table-driven tests for the deterministic faithfulness gate (RIT-T-0092).

Each case proves a specific tolerance rule: a faithful conversion passes with no
error findings; dropped bullets / dropped spans / altered high-signal fields /
fabricated content produce the right codes and severities; and a résumé using
non-ASCII punctuation (middots, curly quotes) passes content parity with only a
NON_ASCII warning — never a content-loss failure.
"""

from __future__ import annotations

from resume_kit_ats import check_faithfulness
from resume_kit_schemas import (
    FaithfulnessCode,
    FaithfulnessReport,
    ResumeDocument,
)


def _error_codes(report: FaithfulnessReport) -> set[FaithfulnessCode]:
    return {f.code for f in report.findings if f.severity == "error"}


# One shared faithful source + JSON: two bullets, one employer, one date range.
_SOURCE = (
    "Experience\n"
    "Senior Engineer, Acme Corp, 2020 - Present\n"
    "- Built scalable payment APIs handling millions of requests\n"
    "- Led a team of five engineers across two continents\n"
    "Education\n"
    "BS Computer Science, State University, 2016\n"
)


def _faithful_resume() -> ResumeDocument:
    return ResumeDocument.model_validate(
        {
            "summary": "",
            "workExperience": [
                {
                    "title": "Senior Engineer",
                    "company": "Acme Corp",
                    "years": "2020 - Present",
                    "description": [
                        "Built scalable payment APIs handling millions of requests",
                        "Led a team of five engineers across two continents",
                    ],
                }
            ],
            "education": [
                {
                    "institution": "State University",
                    "degree": "BS Computer Science",
                    "years": "2016",
                }
            ],
        }
    )


def test_faithful_conversion_passes() -> None:
    report = check_faithfulness(_SOURCE, _faithful_resume())
    assert report.passed is True
    assert _error_codes(report) == set()


def test_dropped_bullet_fails_with_count_and_span() -> None:
    resume = _faithful_resume()
    # Remove the second bullet entirely (a multi-word span drop).
    resume.workExperience[0].description = [
        "Built scalable payment APIs handling millions of requests"
    ]
    report = check_faithfulness(_SOURCE, resume)
    assert report.passed is False
    errors = _error_codes(report)
    assert FaithfulnessCode.BULLET_COUNT_MISMATCH in errors
    assert FaithfulnessCode.DROPPED_SPANS in errors


def test_altered_date_fails_with_altered_field() -> None:
    resume = _faithful_resume()
    resume.workExperience[0].years = "2018 - 2019"  # not in source
    report = check_faithfulness(_SOURCE, resume)
    assert report.passed is False
    assert FaithfulnessCode.ALTERED_FIELD in _error_codes(report)


def test_altered_employer_fails_with_altered_field() -> None:
    resume = _faithful_resume()
    resume.workExperience[0].company = "Globex Corporation"  # not in source
    report = check_faithfulness(_SOURCE, resume)
    assert report.passed is False
    assert FaithfulnessCode.ALTERED_FIELD in _error_codes(report)


def test_fabricated_bullet_reports_added_tokens_warning() -> None:
    resume = _faithful_resume()
    resume.workExperience[0].description.append(
        "Architected a quantum blockchain moonshot"
    )
    report = check_faithfulness(_SOURCE, resume)
    codes = {f.code for f in report.findings}
    # Extra bullet changes the count (hard-fail) AND adds fabricated tokens (warn).
    assert FaithfulnessCode.BULLET_COUNT_MISMATCH in _error_codes(report)
    assert FaithfulnessCode.ADDED_TOKENS in codes
    added = next(
        f for f in report.findings if f.code == FaithfulnessCode.ADDED_TOKENS
    )
    assert added.severity == "warning"
    assert "quantum" in added.items


def test_non_ascii_punctuation_passes_with_only_warning() -> None:
    # Source uses plain ASCII; JSON mirrors it verbatim but with curly quotes,
    # a middot separator and an en-dash date range. Content parity must hold —
    # only NON_ASCII is reported, and as a warning, so passed stays True.
    source = (
        "Experience\n"
        "Senior Engineer, Acme Corp, 2020 - Present\n"
        "- Built payment APIs and shipped features\n"
    )
    resume = ResumeDocument.model_validate(
        {
            "workExperience": [
                {
                    "title": "Senior Engineer",
                    "company": "Acme Corp",
                    "years": "2020 – Present",  # en dash
                    "description": [
                        "Built payment APIs · and “shipped” features"
                    ],
                }
            ],
        }
    )
    report = check_faithfulness(source, resume)
    codes = {f.code for f in report.findings}
    assert FaithfulnessCode.NON_ASCII in codes
    non_ascii = next(
        f for f in report.findings if f.code == FaithfulnessCode.NON_ASCII
    )
    assert non_ascii.severity == "warning"
    # No content-loss / alteration hard-fail from the unicode punctuation.
    assert FaithfulnessCode.DROPPED_SPANS not in _error_codes(report)
    assert FaithfulnessCode.ALTERED_FIELD not in _error_codes(report)
    assert report.passed is True


def _added_tokens(report: FaithfulnessReport) -> set[str]:
    for f in report.findings:
        if f.code == FaithfulnessCode.ADDED_TOKENS:
            return set(f.items)
    return set()


# --- RIT-T-0131: content-string set realignment ---------------------------


def test_custom_sections_do_not_leak_schema_tokens() -> None:
    """F1: schema machinery (descriptionStyles/sectionType) must not be scanned.

    ``bullet`` / ``stringList`` / ``text`` / ``itemList`` are enum / literal
    members serialized by ``model_dump`` — they are NOT user content and must
    never appear in ADDED_TOKENS for a document that does not contain them.
    """
    source = (
        "Experience\n"
        "Senior Engineer, Acme Corp, 2020 - Present\n"
        "- Built scalable payment systems for global commerce\n"
        "Domains and Industries\n"
        "Fintech and Healthcare\n"
    )
    resume = ResumeDocument.model_validate(
        {
            "summary": "",
            "workExperience": [
                {
                    "title": "Senior Engineer",
                    "company": "Acme Corp",
                    "years": "2020 - Present",
                    "description": [
                        "Built scalable payment systems for global commerce"
                    ],
                }
            ],
            "customSections": {
                "Domains and Industries": {
                    "sectionType": "stringList",
                    "strings": ["Fintech and Healthcare"],
                }
            },
        }
    )
    report = check_faithfulness(source, resume)
    added = _added_tokens(report)
    # Phantom schema/enum/example tokens must be absent.
    assert "bullet" not in added
    assert "stringlist" not in added
    assert "text" not in added
    assert "itemlist" not in added
    assert "personalinfo" not in added


def test_key_only_custom_section_heading_not_dropped() -> None:
    """F2: a heading stored ONLY in the customSection dict key is preserved.

    ``CustomSection`` has no ``displayName``; the dict KEY holds the heading.
    Scanning only values reported the heading as a DROPPED_SPANS error and
    hard-failed the gate. Scanning keys must recognize it as preserved.
    """
    source = (
        "Domains and Industries\n"
        "Financial services technology platforms\n"
    )
    resume = ResumeDocument.model_validate(
        {
            "summary": "",
            "customSections": {
                # Heading lives ONLY here — not duplicated into any value.
                "Domains and Industries": {
                    "sectionType": "stringList",
                    "strings": ["Financial services technology platforms"],
                }
            },
        }
    )
    report = check_faithfulness(source, resume)
    assert FaithfulnessCode.DROPPED_SPANS not in _error_codes(report)
    # And no phantom-fabrication of the heading either.
    added = _added_tokens(report)
    assert "domains" not in added
    assert "industries" not in added


def test_no_custom_original_dropping_custom_heading_is_rejected() -> None:
    """An ``-original.json`` projection may not omit custom section headings.

    The no-custom transform belongs after parse. At source-faithfulness time,
    the custom section dict key is authored content and dropping it must be a
    hard failure, not a tolerated structure decision.
    """
    source = (
        "Experience\n"
        "Engineer, Acme, 2020 - Present\n"
        "- Built payment services\n"
        "Technical Skills\n"
        "Python\n"
        "PostgreSQL\n"
    )
    no_custom_original = ResumeDocument.model_validate(
        {
            "workExperience": [
                {
                    "title": "Engineer",
                    "company": "Acme",
                    "years": "2020 - Present",
                    "description": ["Built payment services"],
                }
            ],
            "additional": {"technicalSkills": ["Python", "PostgreSQL"]},
            "customSections": {},
        }
    )

    report = check_faithfulness(source, no_custom_original)

    assert report.passed is False
    assert FaithfulnessCode.DROPPED_SPANS in _error_codes(report)
    dropped = next(
        finding
        for finding in report.findings
        if finding.code is FaithfulnessCode.DROPPED_SPANS
    )
    assert "technical skills" in dropped.items
