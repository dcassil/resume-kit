"""Deterministic PDF rendering for resume documents via ReportLab.

``render_pdf`` builds a resume PDF using ReportLab Platypus flowables over an
in-memory buffer. Output is deterministic: identical input and options produce
byte-identical results across repeated calls. This is achieved by enabling
ReportLab's ``invariant`` mode, which fixes the embedded ``/CreationDate`` and
``/ModDate`` timestamps and disables the random document ``/ID``. No wall-clock
time, UUID, randomness, or locale-dependent text is emitted.
"""

from __future__ import annotations

import io

from reportlab import rl_config  # type: ignore[import-untyped]
from reportlab.lib.enums import TA_CENTER  # type: ignore[import-untyped]
from reportlab.lib.pagesizes import A4, LETTER  # type: ignore[import-untyped]
from reportlab.lib.styles import (  # type: ignore[import-untyped]
    ParagraphStyle,
    getSampleStyleSheet,
)
from reportlab.lib.units import mm  # type: ignore[import-untyped]
from reportlab.platypus import (  # type: ignore[import-untyped]
    ListFlowable,
    ListItem,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)
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

from .dedupe import dedupe_skill_custom_sections_for_render
from .models import ExportOptions

_PAGE_SIZES = {"letter": LETTER, "a4": A4}


def _styles(options: ExportOptions) -> dict[str, ParagraphStyle]:
    """Build the fixed ParagraphStyle set from *options*."""
    base = getSampleStyleSheet()
    font = options.font_family
    size = options.font_size_pt
    return {
        "name": ParagraphStyle(
            "RKName",
            parent=base["Normal"],
            fontName=font + "-Bold",
            fontSize=size + 7,
            leading=size + 9,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "contact": ParagraphStyle(
            "RKContact",
            parent=base["Normal"],
            fontName=font,
            fontSize=size - 1,
            leading=size + 1,
            alignment=TA_CENTER,
            spaceAfter=6,
        ),
        "section": ParagraphStyle(
            "RKSection",
            parent=base["Normal"],
            fontName=font + "-Bold",
            fontSize=size + 2,
            leading=size + 4,
            spaceBefore=8,
            spaceAfter=3,
        ),
        "entry": ParagraphStyle(
            "RKEntry",
            parent=base["Normal"],
            fontName=font + "-Bold",
            fontSize=size,
            leading=size + 2,
            spaceBefore=3,
        ),
        "meta": ParagraphStyle(
            "RKMeta",
            parent=base["Normal"],
            fontName=font,
            fontSize=size - 1,
            leading=size + 1,
            spaceAfter=1,
        ),
        "body": ParagraphStyle(
            "RKBody",
            parent=base["Normal"],
            fontName=font,
            fontSize=size,
            leading=size + 3,
        ),
        "bullet": ParagraphStyle(
            "RKBullet",
            parent=base["Normal"],
            fontName=font,
            fontSize=size,
            leading=size + 3,
        ),
    }


def _bullets(items: list[str], style: ParagraphStyle) -> ListFlowable:
    """Build a bulleted list flowable from non-empty *items*."""
    entries = [
        ListItem(Paragraph(text.strip(), style))
        for text in items
        if text and text.strip()
    ]
    return ListFlowable(entries, bulletType="bullet", start="•", leftIndent=14)


def _has_bullets(items: list[str]) -> bool:
    return any(bool(t) and bool(t.strip()) for t in items)


def _contact_line(info: PersonalInfo) -> str:
    """Join the present contact fields into a single centred line."""
    parts = [
        info.email,
        info.phone,
        info.location,
        info.website or "",
        info.linkedin or "",
        info.github or "",
    ]
    return "  |  ".join(p.strip() for p in parts if p and p.strip())


def _header(resume: ResumeDocument, styles: dict[str, ParagraphStyle]) -> list[object]:
    """Header flowables: name, optional title, and contact line."""
    info = resume.personalInfo
    out: list[object] = []
    if info.name.strip():
        out.append(Paragraph(info.name.strip(), styles["name"]))
    if info.title.strip():
        out.append(Paragraph(info.title.strip(), styles["contact"]))
    contact = _contact_line(info)
    if contact:
        out.append(Paragraph(contact, styles["contact"]))
    return out


def _section_title(title: str, styles: dict[str, ParagraphStyle]) -> Paragraph:
    return Paragraph(title, styles["section"])


def _summary(text: str, styles: dict[str, ParagraphStyle]) -> list[object]:
    if not text.strip():
        return []
    return [
        _section_title("Summary", styles),
        Paragraph(text.strip(), styles["body"]),
    ]


def _experience_entry(
    exp: Experience, styles: dict[str, ParagraphStyle]
) -> list[object]:
    out: list[object] = []
    head = "  —  ".join(p for p in (exp.title.strip(), exp.company.strip()) if p)
    if head:
        out.append(Paragraph(head, styles["entry"]))
    meta = "  |  ".join(
        p.strip()
        for p in (exp.location or "", exp.years)
        if p and p.strip()
    )
    if meta:
        out.append(Paragraph(meta, styles["meta"]))
    if _has_bullets(exp.description):
        out.append(_bullets(exp.description, styles["bullet"]))
    return out


def _experience(
    items: list[Experience], styles: dict[str, ParagraphStyle]
) -> list[object]:
    entries = [e for e in items if _experience_entry(e, styles)]
    if not entries:
        return []
    out: list[object] = [_section_title("Experience", styles)]
    for exp in entries:
        out.extend(_experience_entry(exp, styles))
    return out


def _education_entry(
    edu: Education, styles: dict[str, ParagraphStyle]
) -> list[object]:
    out: list[object] = []
    head = "  —  ".join(
        p for p in (edu.degree.strip(), edu.institution.strip()) if p
    )
    if head:
        out.append(Paragraph(head, styles["entry"]))
    if edu.years.strip():
        out.append(Paragraph(edu.years.strip(), styles["meta"]))
    if edu.description and edu.description.strip():
        out.append(Paragraph(edu.description.strip(), styles["body"]))
    return out


def _education(
    items: list[Education], styles: dict[str, ParagraphStyle]
) -> list[object]:
    entries = [e for e in items if _education_entry(e, styles)]
    if not entries:
        return []
    out: list[object] = [_section_title("Education", styles)]
    for edu in entries:
        out.extend(_education_entry(edu, styles))
    return out


def _project_entry(proj: Project, styles: dict[str, ParagraphStyle]) -> list[object]:
    out: list[object] = []
    head = "  —  ".join(p for p in (proj.name.strip(), proj.role.strip()) if p)
    if head:
        out.append(Paragraph(head, styles["entry"]))
    meta = "  |  ".join(
        p.strip()
        for p in (proj.years, proj.website or "", proj.github or "")
        if p and p.strip()
    )
    if meta:
        out.append(Paragraph(meta, styles["meta"]))
    if _has_bullets(proj.description):
        out.append(_bullets(proj.description, styles["bullet"]))
    return out


def _projects(
    items: list[Project], styles: dict[str, ParagraphStyle]
) -> list[object]:
    entries = [p for p in items if _project_entry(p, styles)]
    if not entries:
        return []
    out: list[object] = [_section_title("Projects", styles)]
    for proj in entries:
        out.extend(_project_entry(proj, styles))
    return out


def _additional(
    info: AdditionalInfo, styles: dict[str, ParagraphStyle]
) -> list[object]:
    groups = [
        ("Technical Skills", info.technicalSkills),
        ("Languages", info.languages),
        ("Certifications & Training", info.certificationsTraining),
        ("Awards", info.awards),
    ]
    present = [
        (label, [v.strip() for v in values if v and v.strip()])
        for label, values in groups
    ]
    present = [(label, values) for label, values in present if values]
    if not present:
        return []
    out: list[object] = [_section_title("Additional", styles)]
    for label, values in present:
        text = "<b>{}:</b> {}".format(label, ", ".join(values))
        out.append(Paragraph(text, styles["meta"]))
    return out


def _custom_section(
    key: str, section: CustomSection, styles: dict[str, ParagraphStyle]
) -> list[object]:
    """Render one visible custom section deterministically."""
    title = key.strip() or "Additional"
    if section.sectionType == SectionType.TEXT:
        if section.text and section.text.strip():
            return [
                _section_title(title, styles),
                Paragraph(section.text.strip(), styles["body"]),
            ]
        return []
    if section.sectionType == SectionType.STRING_LIST:
        values = [v.strip() for v in (section.strings or []) if v and v.strip()]
        if not values:
            return []
        return [
            _section_title(title, styles),
            _bullets(values, styles["bullet"]),
        ]
    items = section.items or []
    out: list[object] = []
    for item in items:
        head = "  —  ".join(
            p
            for p in (item.title.strip(), (item.subtitle or "").strip())
            if p
        )
        if head:
            out.append(Paragraph(head, styles["entry"]))
        if item.years.strip():
            out.append(Paragraph(item.years.strip(), styles["meta"]))
        if _has_bullets(item.description):
            out.append(_bullets(item.description, styles["bullet"]))
    if not out:
        return []
    return [_section_title(title, styles), *out]


def _custom_sections(
    sections: dict[str, CustomSection], styles: dict[str, ParagraphStyle]
) -> list[object]:
    out: list[object] = []
    for key in sorted(sections):
        out.extend(_custom_section(key, sections[key], styles))
    return out


def render_pdf(
    resume: ResumeDocument, *, options: ExportOptions | None = None
) -> bytes:
    """Render *resume* to deterministic PDF bytes using ReportLab.

    Args:
        resume: The structured resume document to render.
        options: Optional export options; defaults to :class:`ExportOptions`.

    Returns:
        The PDF file contents as bytes, beginning with ``b"%PDF"``.
    """
    resume = dedupe_skill_custom_sections_for_render(resume)
    opts = options or ExportOptions()

    # Determinism (NFR-604): fix the embedded creation/mod timestamps and
    # disable the random document /ID before building any document.
    rl_config.invariant = 1

    styles = _styles(opts)
    margin = opts.margin_mm * mm
    page_size = _PAGE_SIZES.get(opts.page_size.lower(), LETTER)

    story: list[object] = []
    story.extend(_header(resume, styles))
    story.extend(_summary(resume.summary, styles))
    story.extend(_experience(resume.workExperience, styles))
    story.extend(_education(resume.education, styles))
    story.extend(_projects(resume.personalProjects, styles))
    story.extend(_additional(resume.additional, styles))
    story.extend(_custom_sections(resume.customSections, styles))
    if not story:
        story.append(Spacer(1, 1))

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=page_size,
        leftMargin=margin,
        rightMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title="Resume",
        author="",
        subject="",
        creator="resume-kit-export",
    )
    doc.build(story)
    return buffer.getvalue()
