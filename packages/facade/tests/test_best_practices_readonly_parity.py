"""Read-only best-practices parity + report identity (RIT-T-0163, RIT-T-0164).

Guards two defects observed on a canonical ``structure`` resume:

- RIT-T-0163: the read-only ``analyze-best-practices`` capability must read the
  canonical ``structure`` format the same way ``build_refine`` does (single
  shared projection), so it detects experience bullets and reports the same
  findings instead of a false "zero findings".
- RIT-T-0164: the emitted report stamps a non-null ``resume_version`` and every
  finding carries its stable rule identifier (non-null) under the serialized
  ``code`` key as well as ``rule_code``.
"""

from __future__ import annotations

import asyncio
import json
from datetime import date
from pathlib import Path

from resume_kit_facade import capabilities as caps
from resume_kit_facade import normalize_resume_input
from resume_kit_facade.baseline import (
    _PLACEMENT_REF_DATE,
    build_base,
    build_structure,
)
from resume_kit_facade.models import AnalyzeBestPracticesRequest, CapabilityOptions
from resume_kit_facade.project_config import (
    init_project,
    set_active,
    working_dir,
)
from resume_kit_schemas import ResumeDocument
from resume_kit_schemas.canonical import Resume
from resume_kit_scoring import (
    analyze_best_practices,
    project_builddoc_from_canonical,
    project_scoredoc,
)

_REF = date(2000, 1, 1)


def _fixture() -> dict:
    return {
        "personalInfo": {
            "name": "Riley Refine",
            "email": "riley@example.com",
            "phone": "555-0199",
            "location": "Chicago, IL",
            "title": "Platform Engineer",
        },
        "summary": "Platform engineer.",
        "workExperience": [
            {
                "id": 1,
                "title": "Platform Engineer",
                "company": "Acme Systems",
                "years": "2021-2024",
                "description": [
                    "Improved onboarding dashboards for support managers.",
                    "Reduced incident review delays for operations partners.",
                    "Maintained deployment checklist for release managers.",
                    "Helped with release planning across product teams.",
                ],
            },
            {
                "id": 2,
                "title": "Software Engineer",
                "company": "Beta Apps",
                "years": "2018-2021",
                "description": [
                    "Coordinated accessibility fixes across product surfaces.",
                    "Documented customer escalation workflows for account teams.",
                    "Was responsible for maintaining partner intake reviews.",
                ],
            },
        ],
        "education": [
            {
                "id": 1,
                "institution": "State University",
                "degree": "BS Computer Science",
                "years": "2018",
            }
        ],
        "additional": {
            "technicalSkills": ["Python", "SQL"],
            "certificationsTraining": [],
            "awards": [],
            "languages": [],
        },
    }


def _structure_raw(root: Path) -> dict:
    """Build the canonical ``structure`` JSON payload from the fixture."""
    init_project(root)
    (working_dir(root) / "resumes").mkdir(parents=True, exist_ok=True)
    (working_dir(root) / "resumes" / "riley-original.json").write_text(
        json.dumps(_fixture()), encoding="utf-8"
    )
    set_active(root, resume="resumes/riley-original.json")
    build_base(root)
    result = build_structure(root)
    assert result.structure_path is not None
    return json.loads(
        (working_dir(root) / result.structure_path).read_text(encoding="utf-8")
    )


def _run(request: AnalyzeBestPracticesRequest) -> object:
    resp = asyncio.run(
        caps.analyze_best_practices_capability(request, CapabilityOptions())
    )
    return resp


def test_readonly_analyze_matches_build_refine_internal_analyzer(tmp_path: Path) -> None:
    """RIT-T-0163: the read-only path and build_refine's analyzer agree.

    On a canonical ``structure`` resume the read-only capability must find the
    same finding set the build_refine internal analyzer finds — specifically the
    metric-less bullets are reported (not zero).
    """
    raw = _structure_raw(tmp_path)

    # The build_refine INTERNAL path: canonical -> BuildDoc projection, analyze.
    internal_doc = project_builddoc_from_canonical(Resume.model_validate(raw))
    internal = analyze_best_practices(
        internal_doc,
        project_scoredoc(internal_doc, reference_date=_PLACEMENT_REF_DATE),
    )
    internal_codes = sorted(f.rule_code for f in internal.findings)

    # There ARE real findings (the reproducer's metric-less bullets).
    assert internal_codes.count("MISSING_QUANTIFICATION") == 7
    assert internal_codes  # not empty

    # The READ-ONLY path routes the same canonical payload through the shared
    # normalization seam and must return the identical finding set.
    resume = normalize_resume_input(raw)
    request = AnalyzeBestPracticesRequest(resume=resume)
    resp = _run(request)
    report = resp.data
    readonly_codes = sorted(f.rule_code for f in report.findings)

    assert readonly_codes == internal_codes


def test_lenient_resumedocument_validate_on_canonical_is_the_bug(tmp_path: Path) -> None:
    """Documents the root cause: naive ResumeDocument.model_validate loses bullets.

    The pre-fix surface path validated canonical JSON directly as a
    ``ResumeDocument`` and returned zero findings. The normalization seam is what
    prevents this regression.
    """
    raw = _structure_raw(tmp_path)
    buggy = ResumeDocument.model_validate(raw)
    buggy_report = analyze_best_practices(
        buggy, project_scoredoc(buggy, reference_date=_REF)
    )
    assert buggy_report.findings == []  # the bug

    fixed = normalize_resume_input(raw)
    fixed_report = analyze_best_practices(
        fixed, project_scoredoc(fixed, reference_date=_REF)
    )
    assert fixed_report.findings  # the fix


def test_report_stamps_resume_version_and_finding_code(tmp_path: Path) -> None:
    """RIT-T-0164: non-null resume_version and non-null per-finding code."""
    raw = _structure_raw(tmp_path)
    resume = normalize_resume_input(raw)
    request = AnalyzeBestPracticesRequest(
        resume=resume, resume_version="resumes/riley-structure.json"
    )
    resp = _run(request)

    dumped = resp.model_dump(mode="json")
    data = dumped["data"]

    assert data["resume_version"] == "resumes/riley-structure.json"
    assert data["findings"], "expected findings on a metric-less structure resume"
    for finding in data["findings"]:
        assert finding["rule_code"], "rule_code must be non-null"
        assert finding["code"] == finding["rule_code"], "code mirrors rule_code, non-null"


def test_report_resume_version_defaults_none_when_not_supplied(tmp_path: Path) -> None:
    """When no version identity is passed the field stays ``None`` (no fabrication)."""
    raw = _structure_raw(tmp_path)
    request = AnalyzeBestPracticesRequest(resume=normalize_resume_input(raw))
    resp = _run(request)
    assert resp.data.resume_version is None
