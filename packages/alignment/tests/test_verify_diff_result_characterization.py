"""Characterization tests for local applied-diff verification."""

from __future__ import annotations

import copy
from collections.abc import Mapping

from resume_kit_alignment.verify import verify_diff_result
from resume_kit_schemas import ChangeAction, ChangeProposal, Warning


def _sample_resume() -> dict[str, object]:
    return {
        "summary": "Backend engineer with 6 years of experience building scalable Python APIs.",
        "workExperience": [
            {
                "title": "Senior Backend Engineer",
                "company": "Acme Corp",
                "description": [
                    "Built REST APIs serving 50K requests/day using Python and FastAPI",
                    "Led migration from monolith to microservices architecture",
                ],
            },
            {
                "title": "Software Engineer",
                "company": "StartupCo",
                "description": [
                    "Developed payment processing system handling $2M monthly",
                    "Wrote unit tests improving coverage from 40% to 85%",
                ],
            },
        ],
        "education": [
            {
                "institution": "MIT",
                "degree": "B.S. Computer Science",
                "description": "Graduated with honors",
            }
        ],
        "personalProjects": [
            {
                "name": "OpenAPI Generator",
                "role": "Creator",
                "description": ["CLI tool generating API clients from OpenAPI specs"],
            }
        ],
    }


def _change(
    *,
    path: str = "summary",
    original: str | None = "x",
    value: str = "y",
    action: ChangeAction = "replace",
) -> ChangeProposal:
    return ChangeProposal(
        path=path,
        action=action,
        original=original,
        value=value,
        reason="test",
    )


def _messages(warnings: list[Warning]) -> list[str]:
    return [warning.message for warning in warnings]


def _copy_mapping(data: Mapping[str, object]) -> dict[str, object]:
    return copy.deepcopy(dict(data))


def test_clean_result_has_no_warnings() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    result["summary"] = "Updated summary."
    applied = [
        _change(original=str(original["summary"]), value="Updated summary."),
    ]

    assert verify_diff_result(original, result, applied, {}) == []


def test_warns_on_no_applied_changes_and_returns_early() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    result["workExperience"] = []

    warnings = verify_diff_result(original, result, [], {})

    assert len(warnings) == 1
    assert isinstance(warnings[0], Warning)
    assert warnings[0].code == "no_applied_changes"
    assert "no changes" in warnings[0].message.lower()


def test_warns_on_dropped_work_education_and_projects() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    result["workExperience"] = []
    result["education"] = []
    result["personalProjects"] = []

    warnings = verify_diff_result(original, result, [_change()], {})
    messages = _messages(warnings)

    assert any("work experience" in message.lower() for message in messages)
    assert any("education" in message.lower() for message in messages)
    assert any("project" in message.lower() for message in messages)
    assert [warning.code for warning in warnings].count("section_count_changed") == 3


def test_warns_on_identity_field_changes() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    work = result["workExperience"]
    education = result["education"]
    assert isinstance(work, list)
    assert isinstance(education, list)
    assert isinstance(work[0], dict)
    assert isinstance(education[0], dict)
    work[0]["company"] = "Different Corp"
    work[0]["title"] = "VP of Engineering"
    education[0]["institution"] = "Stanford"

    warnings = verify_diff_result(original, result, [_change()], {})
    messages = _messages(warnings)

    assert any("workExperience[0].company" in message for message in messages)
    assert any("workExperience[0].title" in message for message in messages)
    assert any("education[0].institution" in message for message in messages)


def test_warns_on_word_count_explosion() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    work = result["workExperience"]
    assert isinstance(work, list)
    assert isinstance(work[0], dict)
    assert isinstance(work[1], dict)
    long_text = "word " * 200
    work[0]["description"] = [long_text] * 5
    work[1]["description"] = [long_text] * 5

    warnings = verify_diff_result(original, result, [_change()], {})

    assert any(warning.code == "word_count_explosion" for warning in warnings)
    assert any("word count" in warning.message.lower() for warning in warnings)


def test_no_warning_on_normal_growth() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    work = result["workExperience"]
    assert isinstance(work, list)
    assert isinstance(work[0], dict)
    description = work[0]["description"]
    assert isinstance(description, list)
    description.append("One extra bullet point here")

    warnings = verify_diff_result(
        original,
        result,
        [
            _change(
                path="workExperience[0].description",
                action="append",
                original=None,
                value="One extra bullet point here",
            )
        ],
        {},
    )

    assert [warning for warning in warnings if warning.code == "word_count_explosion"] == []


def test_warns_on_invented_percentage_and_dollar_amount() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    applied = [
        _change(
            path="workExperience[0].description[0]",
            original="Built REST APIs",
            value="Built REST APIs improving throughput by 40%",
        ),
        _change(
            path="workExperience[1].description[0]",
            original="Developed payment processing system handling $2M monthly",
            value="Developed payment processing system handling $5M monthly",
        ),
    ]

    warnings = verify_diff_result(original, result, applied, {})
    messages = _messages(warnings)

    assert any("40%" in message for message in messages)
    assert any("$5" in message for message in messages)
    assert [warning.code for warning in warnings] == ["invented_metric", "invented_metric"]


def test_preserved_metrics_are_ok() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    warnings = verify_diff_result(
        original,
        result,
        [
            _change(
                path="workExperience[0].description[0]",
                original="Built REST APIs serving 50K requests/day using Python and FastAPI",
                value="Designed REST APIs serving 50K requests/day with Python and FastAPI",
            )
        ],
        {},
    )

    assert [warning for warning in warnings if warning.code == "invented_metric"] == []


def test_multiple_warnings_all_reported() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    work = result["workExperience"]
    assert isinstance(work, list)
    result["workExperience"] = work[:1]
    remaining_work = result["workExperience"]
    assert isinstance(remaining_work, list)
    assert isinstance(remaining_work[0], dict)
    remaining_work[0]["company"] = "Different Corp"

    warnings = verify_diff_result(original, result, [_change()], {})

    assert any(warning.code == "section_count_changed" for warning in warnings)
    assert any(warning.code == "identity_field_changed" for warning in warnings)
    assert len(warnings) >= 2


def test_metric_warning_plus_word_count_warning() -> None:
    original = _sample_resume()
    result = _copy_mapping(original)
    work = result["workExperience"]
    assert isinstance(work, list)
    assert isinstance(work[0], dict)
    assert isinstance(work[1], dict)
    long_text = "Improved revenue by 99% " + ("extra words " * 200)
    work[0]["description"] = [long_text] * 5
    work[1]["description"] = [long_text] * 5

    warnings = verify_diff_result(
        original,
        result,
        [
            _change(
                path="workExperience[0].description[0]",
                original="Built REST APIs serving 50K requests/day using Python and FastAPI",
                value=long_text,
            )
        ],
        {},
    )

    assert any(warning.code == "invented_metric" for warning in warnings)
    assert any(warning.code == "word_count_explosion" for warning in warnings)
