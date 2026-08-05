"""original -> base build path with the claim-preservation gate (RIT-T-0115)."""

from __future__ import annotations

import json
from pathlib import Path

from resume_kit_facade.baseline import build_base
from resume_kit_facade.project_config import (
    init_project,
    load_config,
    resolve_active_resume,
    set_active,
    working_dir,
)
from resume_kit_schemas import ResumeDocument


def _setup(root: Path, resume: dict) -> None:
    init_project(root)
    (working_dir(root) / "resumes" / "jane-original.json").write_text(
        json.dumps(resume), encoding="utf-8"
    )
    set_active(root, resume="resumes/jane-original.json")


def _resume_with_pii() -> dict:
    return {
        "personalInfo": {"name": "Jane", "email": "j@x.com", "phone": "555"},
        "summary": "Engineer. SSN 123-45-6789.",
        "workExperience": [
            {"title": "Staff Engineer", "company": "Acme", "years": "Jan 2020 - Present",
             "description": ["Built billing."]},
            {"title": "Engineer", "company": "Beta", "years": "2016 - 2019", "description": ["Shipped API."]},
        ],
        "education": [{"institution": "MIT", "degree": "BS CS", "years": "2016"}],
        "additional": {"technicalSkills": ["Python"]},
    }


def test_build_base_writes_base_and_sets_pointer(tmp_path: Path) -> None:
    _setup(tmp_path, _resume_with_pii())
    result = build_base(tmp_path, mode="auto")

    assert result.base_path == "resumes/jane-base.json"
    assert "PII_SSN" in result.applied
    assert "INCONSISTENT_DATES" in result.applied

    base_file = working_dir(tmp_path) / "resumes" / "jane-base.json"
    assert base_file.exists()
    base = ResumeDocument.model_validate(json.loads(base_file.read_text(encoding="utf-8")))
    # PII stripped, dates normalized, claims preserved
    assert "123-45-6789" not in base.summary
    assert "Jan" not in base.workExperience[0].years
    assert base.workExperience[0].company == "Acme"

    # config points base at the new artifact; resolution prefers it
    config = load_config(tmp_path)
    assert config.base_resume == "resumes/jane-base.json"
    assert config.base_derived_from == "resumes/jane-original.json"
    assert resolve_active_resume(config) == "resumes/jane-base.json"


def test_build_base_defers_needs_judgment(tmp_path: Path) -> None:
    resume = _resume_with_pii()
    resume["personalInfo"] = {"name": "Jane", "phone": "555"}  # missing email -> needs_judgment
    resume["customSections"] = {"My Superpowers": {"sectionType": "text", "text": "x"}}
    _setup(tmp_path, resume)
    result = build_base(tmp_path, mode="auto")
    assert "MISSING_EMAIL" in result.deferred
    assert "NONSTANDARD_SECTION" in result.deferred


def test_clean_resume_base_equals_original_content(tmp_path: Path) -> None:
    clean = {
        "personalInfo": {"name": "Jane", "email": "j@x.com", "phone": "555"},
        "summary": "Engineer.",
        "workExperience": [{"title": "A", "company": "X", "years": "2020 - 2022", "description": ["Built."]}],
        "education": [{"institution": "M", "degree": "BS", "years": "2016"}],
        "additional": {"technicalSkills": ["Python"]},
    }
    _setup(tmp_path, clean)
    result = build_base(tmp_path, mode="auto")
    assert result.applied == []
    base = json.loads((working_dir(tmp_path) / "resumes" / "jane-base.json").read_text())
    assert ResumeDocument.model_validate(base) == ResumeDocument.model_validate(clean)
