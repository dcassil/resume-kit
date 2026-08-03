"""Canonical structured resume domain models.

# ---------------------------------------------------------------------------
# Derived from Resume-Matcher (Apache-2.0)
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream path: apps/backend/app/schemas/models.py (lines 129-423)
# Pinned SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# Modified: Domain resume models (SectionType, PersonalInfo, Experience, Education,
#   Project, AdditionalInfo, SectionMeta, CustomSectionItem, CustomSection, ResumeData)
#   split OUT of the file that mixed them with HTTP/DB DTOs. Re-namespaced under
#   resume_kit_schemas; coercion helpers moved to ``_coercion``. Field shapes,
#   validators, defaults, and descriptionStyles alignment behavior preserved. Added
#   ``Contact``/``Skill`` canonical aliases and ``ResumeDocument`` as the public name.
# ---------------------------------------------------------------------------
"""

from __future__ import annotations

import copy
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator

from ._coercion import (
    DescriptionStyle,
    align_description_styles,
    coerce_description_styles,
    coerce_optional_text,
    coerce_string_list,
    coerce_text,
)


class SectionType(StrEnum):
    """Types of resume sections."""

    PERSONAL_INFO = "personalInfo"  # Always first, not reorderable.
    TEXT = "text"  # Single text block (like summary).
    ITEM_LIST = "itemList"  # Array of items with fields (like experience).
    STRING_LIST = "stringList"  # Array of strings (like skills).


class PersonalInfo(BaseModel):
    """Personal / contact information for a resume."""

    name: str = ""
    title: str = ""
    email: str = ""
    phone: str = ""
    location: str = ""
    website: str | None = None
    linkedin: str | None = None
    github: str | None = None


class Experience(BaseModel):
    """A work-experience entry."""

    id: int = 0
    title: str = ""
    company: str = ""
    location: str | None = None
    years: str = ""
    description: list[str] = Field(default_factory=list)
    descriptionStyles: list[DescriptionStyle] = Field(default_factory=list)

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> list[str]:
        return coerce_string_list(value)

    @field_validator("descriptionStyles", mode="before")
    @classmethod
    def _normalize_description_styles(cls, value: Any) -> list[DescriptionStyle]:
        return coerce_description_styles(value)

    @model_validator(mode="after")
    def _sync_description_styles(self) -> Experience:
        self.descriptionStyles = align_description_styles(
            self.description, self.descriptionStyles
        )
        return self


class Education(BaseModel):
    """An education entry."""

    id: int = 0
    institution: str = ""
    degree: str = ""
    years: str = ""
    description: str | None = None

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> str | None:
        return coerce_optional_text(value)


class Project(BaseModel):
    """A personal / portfolio project entry."""

    id: int = 0
    name: str = ""
    role: str = ""
    years: str = ""
    github: str | None = None
    website: str | None = None
    description: list[str] = Field(default_factory=list)
    descriptionStyles: list[DescriptionStyle] = Field(default_factory=list)

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> list[str]:
        return coerce_string_list(value)

    @field_validator("descriptionStyles", mode="before")
    @classmethod
    def _normalize_description_styles(cls, value: Any) -> list[DescriptionStyle]:
        return coerce_description_styles(value)

    @model_validator(mode="after")
    def _sync_description_styles(self) -> Project:
        self.descriptionStyles = align_description_styles(
            self.description, self.descriptionStyles
        )
        return self


class AdditionalInfo(BaseModel):
    """Additional-information section (skills, languages, certifications, awards)."""

    technicalSkills: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    certificationsTraining: list[str] = Field(default_factory=list)
    awards: list[str] = Field(default_factory=list)

    @field_validator(
        "technicalSkills",
        "languages",
        "certificationsTraining",
        "awards",
        mode="before",
    )
    @classmethod
    def _normalize_string_fields(cls, value: Any) -> list[str]:
        return coerce_string_list(value)


class Skill(BaseModel):
    """A single named skill with an optional category.

    Upstream represented skills only as bare strings inside ``AdditionalInfo``.
    This canonical model lets skills carry a category without changing the
    ported string-list shapes, which remain the primary storage.
    """

    name: str = Field(description="The skill name, e.g. 'Python'.")
    category: str | None = Field(
        default=None, description="Optional grouping, e.g. 'language' or 'framework'."
    )


class SectionMeta(BaseModel):
    """Metadata for a resume section (ordering, visibility, type)."""

    id: str
    key: str
    displayName: str
    sectionType: SectionType
    isDefault: bool = True
    isVisible: bool = True
    order: int = 0


class CustomSectionItem(BaseModel):
    """Generic item for custom item-based sections."""

    id: int = 0
    title: str = ""
    subtitle: str | None = None
    location: str | None = None
    years: str = ""
    description: list[str] = Field(default_factory=list)
    descriptionStyles: list[DescriptionStyle] = Field(default_factory=list)

    @field_validator("description", mode="before")
    @classmethod
    def _normalize_description(cls, value: Any) -> list[str]:
        return coerce_string_list(value)

    @field_validator("descriptionStyles", mode="before")
    @classmethod
    def _normalize_description_styles(cls, value: Any) -> list[DescriptionStyle]:
        return coerce_description_styles(value)

    @model_validator(mode="after")
    def _sync_description_styles(self) -> CustomSectionItem:
        self.descriptionStyles = align_description_styles(
            self.description, self.descriptionStyles
        )
        return self


class CustomSection(BaseModel):
    """Container for a dynamically-typed custom section."""

    sectionType: SectionType
    items: list[CustomSectionItem] | None = None  # For ITEM_LIST.
    strings: list[str] | None = None  # For STRING_LIST.
    text: str | None = None  # For TEXT.

    @field_validator("items", mode="before")
    @classmethod
    def _normalize_items(cls, value: Any) -> Any:
        if value is None:
            return None
        if not isinstance(value, list):
            return value
        result: list[Any] = []
        for i, item in enumerate(value):
            if isinstance(item, str):
                result.append({"id": i + 1, "title": item})
            else:
                result.append(item)
        return result

    @field_validator("strings", mode="before")
    @classmethod
    def _normalize_strings(cls, value: Any) -> list[str] | None:
        if value is None:
            return None
        return coerce_string_list(value)

    @field_validator("text", mode="before")
    @classmethod
    def _normalize_text(cls, value: Any) -> str | None:
        return coerce_optional_text(value)


DEFAULT_SECTION_META: list[dict[str, Any]] = [
    {
        "id": "personalInfo",
        "key": "personalInfo",
        "displayName": "Personal Info",
        "sectionType": SectionType.PERSONAL_INFO,
        "isDefault": True,
        "isVisible": True,
        "order": 0,
    },
    {
        "id": "summary",
        "key": "summary",
        "displayName": "Summary",
        "sectionType": SectionType.TEXT,
        "isDefault": True,
        "isVisible": True,
        "order": 1,
    },
    {
        "id": "workExperience",
        "key": "workExperience",
        "displayName": "Experience",
        "sectionType": SectionType.ITEM_LIST,
        "isDefault": True,
        "isVisible": True,
        "order": 2,
    },
    {
        "id": "education",
        "key": "education",
        "displayName": "Education",
        "sectionType": SectionType.ITEM_LIST,
        "isDefault": True,
        "isVisible": True,
        "order": 3,
    },
    {
        "id": "personalProjects",
        "key": "personalProjects",
        "displayName": "Projects",
        "sectionType": SectionType.ITEM_LIST,
        "isDefault": True,
        "isVisible": True,
        "order": 4,
    },
    {
        "id": "additional",
        "key": "additional",
        "displayName": "Skills & Awards",
        "sectionType": SectionType.STRING_LIST,
        "isDefault": True,
        "isVisible": True,
        "order": 5,
    },
]


def normalize_resume_data(data: dict[str, Any]) -> dict[str, Any]:
    """Ensure resume data has section metadata (lazy-migration helper).

    Fills default ``sectionMeta``/``customSections`` for legacy dicts that
    predate dynamic sections. Uses ``deepcopy`` so resumes never share a
    mutable default list reference.
    """
    if not data.get("sectionMeta"):
        data["sectionMeta"] = copy.deepcopy(DEFAULT_SECTION_META)
    if "customSections" not in data:
        data["customSections"] = {}
    return data


class ResumeDocument(BaseModel):
    """Complete structured resume — the canonical resume domain model.

    This is the domain contract for a parsed/structured resume. It is transport-
    agnostic: no request ids, processing status, DB ids, or response wrappers.
    """

    personalInfo: PersonalInfo = Field(default_factory=PersonalInfo)
    summary: str = ""
    workExperience: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    personalProjects: list[Project] = Field(default_factory=list)
    additional: AdditionalInfo = Field(default_factory=AdditionalInfo)

    sectionMeta: list[SectionMeta] = Field(default_factory=list)
    customSections: dict[str, CustomSection] = Field(default_factory=dict)

    @field_validator("summary", mode="before")
    @classmethod
    def _normalize_summary(cls, value: Any) -> str:
        return coerce_text(value)


# Canonical aliases: resume-kit's public vocabulary maps onto the ported shapes.
Contact = PersonalInfo
"""Canonical name for the contact/personal-information block."""

# Backwards/inventory-name compatibility for the ported model.
ResumeData = ResumeDocument
"""Alias for :class:`ResumeDocument` using the upstream ``ResumeData`` name."""
