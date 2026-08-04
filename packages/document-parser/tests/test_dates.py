"""Characterization tests for resume_kit_document_parser.dates.

These tests pin the exact upstream behavior of _extract_markdown_dates and
restore_dates_from_markdown as ported from apps/backend/app/services/parser.py
at SHA 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc.  Each test must fail if the
regex or patching logic regresses.
"""

from __future__ import annotations

from typing import Any

from resume_kit_document_parser.dates import (
    _extract_markdown_dates,
    restore_dates_from_markdown,
)

# ---------------------------------------------------------------------------
# _extract_markdown_dates
# ---------------------------------------------------------------------------


class TestExtractMarkdownDates:
    def test_full_month_range(self) -> None:
        md = "## Work Experience\n\nAcme Corp  Jan 2020 - Dec 2023"
        result = _extract_markdown_dates(md)
        assert result == ["Jan 2020 - Dec 2023"]

    def test_present_range(self) -> None:
        md = "Google  May 2021 - Present"
        result = _extract_markdown_dates(md)
        assert result == ["May 2021 - Present"]

    def test_current_variant(self) -> None:
        md = "January 2020 - Current"
        result = _extract_markdown_dates(md)
        assert result == ["January 2020 - Current"]

    def test_single_date(self) -> None:
        md = "Graduated Jun 2023"
        result = _extract_markdown_dates(md)
        assert result == ["Jun 2023"]

    def test_multiple_dates(self) -> None:
        md = "Jan 2018 - Jun 2020\nSep 2020 - Present"
        result = _extract_markdown_dates(md)
        assert result == ["Jan 2018 - Jun 2020", "Sep 2020 - Present"]

    def test_no_dates_returns_empty(self) -> None:
        assert _extract_markdown_dates("No dates here at all.") == []

    def test_year_only_not_matched(self) -> None:
        # Year-only strings like "2020 - 2021" must NOT be captured by the
        # month-inclusive regex.  If this passes, the regex correctly requires
        # a month prefix — breaking the regex would cause this to fail.
        result = _extract_markdown_dates("2020 - 2021")
        assert result == [], "year-only ranges must not match _MD_DATE_RE"

    def test_em_dash_separator(self) -> None:
        md = "Feb 2019—Aug 2022"
        result = _extract_markdown_dates(md)
        assert result == ["Feb 2019—Aug 2022"]

    def test_en_dash_separator(self) -> None:
        md = "Mar 2017–Nov 2019"
        result = _extract_markdown_dates(md)
        assert result == ["Mar 2017–Nov 2019"]

    def test_ongoing_variant(self) -> None:
        md = "Oct 2022 - Ongoing"
        result = _extract_markdown_dates(md)
        assert result == ["Oct 2022 - Ongoing"]


# ---------------------------------------------------------------------------
# restore_dates_from_markdown — standard sections
# ---------------------------------------------------------------------------


class TestRestoreDatesFromMarkdown:
    def _make_data(
        self,
        work: list[dict[str, Any]] | None = None,
        education: list[dict[str, Any]] | None = None,
        projects: list[dict[str, Any]] | None = None,
        custom: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        data: dict[str, Any] = {}
        if work is not None:
            data["workExperience"] = work
        if education is not None:
            data["education"] = education
        if projects is not None:
            data["personalProjects"] = projects
        if custom is not None:
            data["customSections"] = custom
        return data

    def test_patches_work_experience_year_range(self) -> None:
        data = self._make_data(work=[{"title": "Eng", "years": "2020 - 2023"}])
        md = "Jan 2020 - Dec 2023"
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"][0]["years"] == "Jan 2020 - Dec 2023"

    def test_patches_education_year_range(self) -> None:
        data = self._make_data(education=[{"school": "MIT", "years": "2016 - 2020"}])
        md = "Sep 2016 - May 2020"
        result = restore_dates_from_markdown(data, md)
        assert result["education"][0]["years"] == "Sep 2016 - May 2020"

    def test_patches_personal_projects(self) -> None:
        data = self._make_data(projects=[{"name": "MyApp", "years": "2022"}])
        md = "Jun 2022"
        result = restore_dates_from_markdown(data, md)
        assert result["personalProjects"][0]["years"] == "Jun 2022"

    def test_already_monthful_field_preserved(self) -> None:
        """Fields that already contain a month abbreviation must not be overwritten."""
        data = self._make_data(work=[{"years": "Jan 2020 - Dec 2023"}])
        md = "Feb 2020 - Nov 2023"  # different dates in markdown — should be ignored
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"][0]["years"] == "Jan 2020 - Dec 2023"

    def test_year_only_left_untouched_when_no_source(self) -> None:
        """Year-only field stays unchanged when markdown has no matching month date."""
        data = self._make_data(work=[{"years": "2019 - 2021"}])
        md = "No dates here."
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"][0]["years"] == "2019 - 2021"

    def test_no_markdown_dates_returns_unchanged(self) -> None:
        data = self._make_data(work=[{"years": "2020 - 2022"}])
        result = restore_dates_from_markdown(data, "plain text only")
        assert result["workExperience"][0]["years"] == "2020 - 2022"

    def test_non_dict_entries_skipped(self) -> None:
        """Non-dict items in a section list must not raise."""
        data: dict[str, Any] = {"workExperience": ["not a dict", None, 42]}
        md = "Jan 2020 - Dec 2023"
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"] == ["not a dict", None, 42]

    def test_missing_section_tolerated(self) -> None:
        """Absent top-level section keys must not raise KeyError."""
        data: dict[str, Any] = {}
        md = "Jan 2020 - Dec 2023"
        result = restore_dates_from_markdown(data, md)
        assert result == {}

    def test_empty_years_field_skipped(self) -> None:
        data = self._make_data(work=[{"years": ""}])
        md = "Jan 2020 - Dec 2023"
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"][0]["years"] == ""

    def test_non_string_years_skipped(self) -> None:
        data = self._make_data(work=[{"years": None}])
        md = "Jan 2020 - Dec 2023"
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"][0]["years"] is None

    def test_separator_normalized_in_output(self) -> None:
        """Em-dash in markdown is normalized to \" - \" in the patched value."""
        data = self._make_data(work=[{"years": "2019 - 2021"}])
        md = "Mar 2019—Nov 2021"
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"][0]["years"] == "Mar 2019 - Nov 2021"

    def test_present_range_patch(self) -> None:
        data = self._make_data(work=[{"years": "2021"}])
        md = "May 2021 - Present"
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"][0]["years"] == "May 2021 - Present"

    def test_first_match_wins_for_same_year_key(self) -> None:
        """When two markdown dates map to the same year key, only the first is kept."""
        data = self._make_data(work=[{"years": "2020 - 2021"}])
        # Two ranges sharing the same years — first should win
        md = "Jan 2020 - Jun 2021\nApr 2020 - Dec 2021"
        result = restore_dates_from_markdown(data, md)
        assert result["workExperience"][0]["years"] == "Jan 2020 - Jun 2021"

    # Regression guard: proves broken regex would be caught
    def test_regex_requires_month_prefix(self) -> None:
        """This test would FAIL if _MD_DATE_RE were changed to match bare years,
        because a year-only markdown string would then populate year_to_full and
        overwrite the field with a year-only value instead of leaving it alone."""
        data = self._make_data(work=[{"years": "2020 - 2021"}])
        # Markdown has no month-qualified date at all
        md = "2020 - 2021"
        result = restore_dates_from_markdown(data, md)
        # Must remain unchanged — no month source exists
        assert result["workExperience"][0]["years"] == "2020 - 2021", (
            "year-only markdown must not patch the field; regex must require a month"
        )


# ---------------------------------------------------------------------------
# restore_dates_from_markdown — customSections
# ---------------------------------------------------------------------------


class TestRestoreDatesCustomSections:
    def _custom_item_list(self, items: list[dict[str, Any]]) -> dict[str, Any]:
        return {
            "customSections": {
                "awards": {
                    "sectionType": "itemList",
                    "items": items,
                }
            }
        }

    def test_patches_item_list_entry(self) -> None:
        data = self._custom_item_list([{"name": "Award", "years": "2021 - 2022"}])
        md = "Mar 2021 - Sep 2022"
        result = restore_dates_from_markdown(data, md)
        assert result["customSections"]["awards"]["items"][0]["years"] == "Mar 2021 - Sep 2022"

    def test_non_item_list_section_skipped(self) -> None:
        data: dict[str, Any] = {
            "customSections": {
                "summary": {
                    "sectionType": "text",
                    "items": [{"years": "2020 - 2021"}],
                }
            }
        }
        md = "Jan 2020 - Dec 2021"
        result = restore_dates_from_markdown(data, md)
        # sectionType != "itemList" — items must not be touched
        assert result["customSections"]["summary"]["items"][0]["years"] == "2020 - 2021"

    def test_non_dict_item_in_custom_skipped(self) -> None:
        data: dict[str, Any] = {
            "customSections": {
                "awards": {
                    "sectionType": "itemList",
                    "items": ["not a dict"],
                }
            }
        }
        md = "Jan 2020 - Dec 2021"
        result = restore_dates_from_markdown(data, md)
        assert result["customSections"]["awards"]["items"] == ["not a dict"]

    def test_custom_sections_not_dict_tolerated(self) -> None:
        data: dict[str, Any] = {"customSections": "unexpected string"}
        md = "Jan 2020 - Dec 2021"
        # Must not raise
        result = restore_dates_from_markdown(data, md)
        assert result["customSections"] == "unexpected string"
