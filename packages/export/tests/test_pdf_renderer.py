"""Tests for the deterministic ReportLab PDF renderer."""

from __future__ import annotations

import io

from pdfminer.high_level import extract_text
from resume_kit_export.models import ExportOptions
from resume_kit_export.pdf import render_pdf
from resume_kit_schemas.resume import (
    AdditionalInfo,
    CustomSection,
    Education,
    Experience,
    PersonalInfo,
    Project,
    ResumeDocument,
    SectionType,
)


def _full_resume() -> ResumeDocument:
    return ResumeDocument(
        personalInfo=PersonalInfo(
            name="Ada Lovelace",
            title="Software Engineer",
            email="ada@example.com",
            phone="+1-555-0100",
            location="London, UK",
            website="https://ada.example.com",
            linkedin="linkedin.com/in/ada",
            github="github.com/ada",
        ),
        summary="Pioneering analyst and first programmer.",
        workExperience=[
            Experience(
                title="Lead Engineer",
                company="Analytical Engines Ltd",
                location="London",
                years="1842-1852",
                description=[
                    "Authored the first published algorithm.",
                    "Designed looping computation notes.",
                ],
            )
        ],
        education=[
            Education(
                institution="University of London",
                degree="Mathematics",
                years="1830-1834",
                description="Studied analysis and mechanics.",
            )
        ],
        personalProjects=[
            Project(
                name="Note G",
                role="Author",
                years="1843",
                website="https://noteg.example.com",
                description=["Computed Bernoulli numbers."],
            )
        ],
        additional=AdditionalInfo(
            technicalSkills=["Analytical Engine", "Algorithms"],
            languages=["English", "French"],
            certificationsTraining=["Advanced Calculus"],
            awards=["Countess of Lovelace"],
        ),
        customSections={
            "Publications": CustomSection(
                sectionType=SectionType.STRING_LIST,
                strings=["Sketch of the Analytical Engine"],
            )
        },
    )


def test_render_pdf_returns_pdf_bytes() -> None:
    out = render_pdf(_full_resume())
    assert isinstance(out, bytes)
    assert out.startswith(b"%PDF")


def test_render_pdf_is_deterministic() -> None:
    resume = _full_resume()
    opts = ExportOptions()
    first = render_pdf(resume, options=opts)
    second = render_pdf(resume, options=opts)
    assert first == second


def test_render_pdf_structural_content() -> None:
    out = render_pdf(_full_resume())
    text = extract_text(io.BytesIO(out))

    for expected in (
        "Ada Lovelace",
        "Software Engineer",
        "ada@example.com",
        "+1-555-0100",
        "London, UK",
        "Pioneering analyst",
        "first published algorithm",
        "University of London",
        "Note G",
        "Analytical Engine",
        "Sketch of the Analytical Engine",
    ):
        assert expected in text, f"missing: {expected!r}"

    # Deterministic section order.
    order = ["Summary", "Experience", "Education", "Projects", "Additional"]
    positions = [text.find(label) for label in order]
    assert all(p >= 0 for p in positions), positions
    assert positions == sorted(positions), positions


def test_render_pdf_empty_optional_fields() -> None:
    resume = ResumeDocument(
        personalInfo=PersonalInfo(name="Grace Hopper", email="grace@example.com")
    )
    out = render_pdf(resume)
    assert out.startswith(b"%PDF")

    text = extract_text(io.BytesIO(out))
    assert "Grace Hopper" in text
    assert "grace@example.com" in text
    # No placeholders for omitted sections.
    for absent in ("Summary", "Experience", "Education", "Projects", "Additional"):
        assert absent not in text, f"unexpected section: {absent!r}"


def test_render_pdf_dedupes_custom_skills_section() -> None:
    payload = _full_resume().model_dump(mode="json")
    payload["customSections"] = {
        "Technical Skills": {
            "sectionType": "stringList",
            "strings": ["Technical Skills", "Analytical Engine", "Algorithms", "Python"],
        }
    }
    resume = ResumeDocument.model_validate(payload)

    text = extract_text(io.BytesIO(render_pdf(resume)))

    assert text.count("Technical Skills") == 1
    assert "Python" in text
