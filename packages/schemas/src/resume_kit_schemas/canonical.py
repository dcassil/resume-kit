"""Canonical resume schema from ``references/jsonresume.md``."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

_DATE_RE = re.compile(r"^\d{4}(?:-(?:0[1-9]|1[0-2])(?:-(?:0[1-9]|[12]\d|3[01]))?)?$")


def _has_text(value: str | None) -> bool:
    return value is not None and value.strip() != ""


def _has_items(value: list[Any] | None) -> bool:
    return value is not None and len(value) > 0


def _validate_required_text(value: str) -> str:
    if value.strip() == "":
        raise ValueError("field must contain text")
    return value


def _validate_resume_date(value: str) -> str:
    if not _DATE_RE.fullmatch(value):
        raise ValueError("resume date must use YYYY, YYYY-MM, or YYYY-MM-DD")
    return value


type ResumeDate = Annotated[str, AfterValidator(_validate_resume_date)]


class CanonicalBaseModel(BaseModel):
    """Base for strict canonical resume data models."""

    model_config = ConfigDict(extra="forbid")


class EmploymentType(StrEnum):
    """Allowed employment type values."""

    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    CONSULTING = "consulting"
    FREELANCE = "freelance"
    INTERNSHIP = "internship"
    FOUNDER = "founder"
    OTHER = "other"


class LinkType(StrEnum):
    """Allowed link type values."""

    LINKEDIN = "linkedin"
    GITHUB = "github"
    PORTFOLIO = "portfolio"
    WEBSITE = "website"
    PROJECT = "project"
    PUBLICATION = "publication"
    CREDENTIAL = "credential"
    OTHER = "other"


class MetricType(StrEnum):
    """Allowed metric type values."""

    PERCENTAGE = "percentage"
    CURRENCY = "currency"
    COUNT = "count"
    DURATION = "duration"


class DurationUnit(StrEnum):
    """Allowed duration metric units."""

    HOURS = "hours"
    DAYS = "days"
    WEEKS = "weeks"
    MONTHS = "months"


class CanonicalSection(StrEnum):
    """Canonical top-level resume sections."""

    BASICS = "basics"
    WORK = "work"
    EXPERIENCE = "work"
    SKILLS = "skills"
    PROJECTS = "projects"
    EDUCATION = "education"
    CERTIFICATIONS = "certifications"
    AWARDS = "awards"
    PUBLICATIONS = "publications"
    VOLUNTEER = "volunteer"
    LANGUAGES = "languages"
    INTERESTS = "interests"
    REFERENCES = "references"
    OTHER = "other"


class Location(CanonicalBaseModel):
    """Candidate location, preserving only known precision."""

    city: str | None = None
    region: str | None = None
    countryCode: str | None = None
    postalCode: str | None = None
    address: str | None = None


class Link(CanonicalBaseModel):
    """Common link structure used across sections."""

    type: LinkType
    url: str
    label: str | None = None

    @field_validator("url")
    @classmethod
    def _url_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)


class Metric(CanonicalBaseModel):
    """Structured metric evidence."""

    type: MetricType
    value: float
    currency: str | None = None
    unit: DurationUnit | str | None = None
    label: str | None = None

    @model_validator(mode="after")
    def _enforce_metric_shape(self) -> Metric:
        if self.type is MetricType.CURRENCY:
            if not _has_text(self.currency):
                raise ValueError("currency metrics require currency")
            if self.unit is not None:
                raise ValueError("currency metrics cannot include unit")
        elif self.currency is not None:
            raise ValueError("only currency metrics may include currency")

        if self.type is MetricType.DURATION:
            if self.unit is None or str(self.unit) not in {unit.value for unit in DurationUnit}:
                raise ValueError("duration metrics require a duration unit")
        elif self.type is MetricType.PERCENTAGE and self.unit is not None:
            raise ValueError("percentage metrics cannot include unit")

        return self


class Achievement(CanonicalBaseModel):
    """Verbatim achievement text plus optional future structured evidence."""

    text: str
    action: str = ""
    result: str = ""
    metrics: list[Metric] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    keywords: list[str] = Field(default_factory=list)

    @field_validator("text")
    @classmethod
    def _text_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)


class Basics(CanonicalBaseModel):
    """Required identity and contact block."""

    name: str
    headline: str | None = None
    summary: str | None = None
    email: str | None = None
    phone: str | None = None
    location: Location | None = None
    links: list[Link] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)

    @model_validator(mode="after")
    def _must_have_contact(self) -> Basics:
        if not (_has_text(self.email) or _has_text(self.phone)):
            raise ValueError("basics requires at least one of email or phone")
        return self


class Experience(CanonicalBaseModel):
    """Canonical work experience entry."""

    # Empty organization is intentionally legal, mirroring the source schema
    # ``ResumeDocument.Experience.company`` (which defaults to "" for date-grouped
    # umbrella headings / career-break lines where the group is carried in ``title``).
    # See RIT-T-0156. Only ``title`` is required-non-empty here.
    organization: str = ""
    title: str
    employmentType: EmploymentType | None = None
    location: Location | str | None = None
    startDate: ResumeDate | None = None
    endDate: ResumeDate | Literal["present"] | None = None
    summary: str | None = None
    achievements: list[Achievement] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def _required_fields_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)

    @model_validator(mode="after")
    def _must_have_summary_or_achievement(self) -> Experience:
        if not (_has_text(self.summary) or _has_items(self.achievements)):
            raise ValueError("experience requires summary or achievements")
        return self


class SkillGroup(CanonicalBaseModel):
    """Named skill group with one or more keywords."""

    name: str
    keywords: list[str]

    @field_validator("name")
    @classmethod
    def _name_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)

    @field_validator("keywords")
    @classmethod
    def _keywords_must_have_items(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("skill group requires at least one keyword")
        return value


class Project(CanonicalBaseModel):
    """Canonical project entry."""

    name: str
    description: str | None = None
    achievements: list[Achievement] = Field(default_factory=list)
    roles: list[str] = Field(default_factory=list)
    technologies: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    links: list[Link] = Field(default_factory=list)
    startDate: ResumeDate | None = None
    endDate: ResumeDate | Literal["present"] | None = None

    @field_validator("name")
    @classmethod
    def _name_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)

    @model_validator(mode="after")
    def _must_have_description_or_achievement(self) -> Project:
        if not (_has_text(self.description) or _has_items(self.achievements)):
            raise ValueError("project requires description or achievements")
        return self


class Education(CanonicalBaseModel):
    """Canonical education entry."""

    institution: str
    degree: str | None = None
    field: str | None = None
    startDate: ResumeDate | None = None
    endDate: ResumeDate | None = None
    score: str | None = None
    courses: list[str] = Field(default_factory=list)
    highlights: list[str] = Field(default_factory=list)

    @field_validator("institution")
    @classmethod
    def _institution_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)

    @model_validator(mode="after")
    def _must_have_degree_field_or_highlight(self) -> Education:
        if not (_has_text(self.degree) or _has_text(self.field) or _has_items(self.highlights)):
            raise ValueError("education requires degree, field, or highlights")
        return self


class Certification(CanonicalBaseModel):
    """Canonical certification entry."""

    name: str
    issuer: str | None = None
    date: ResumeDate | None = None
    expirationDate: ResumeDate | None = None
    credentialId: str | None = None
    links: list[Link] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def _name_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)


class NamedSectionItem(CanonicalBaseModel):
    """Minimal item shape for optional named collections."""

    name: str

    @field_validator("name")
    @classmethod
    def _name_must_have_text(cls, value: str) -> str:
        return _validate_required_text(value)


class Award(NamedSectionItem):
    """Canonical award entry."""


class Publication(NamedSectionItem):
    """Canonical publication entry."""


class Volunteer(NamedSectionItem):
    """Canonical volunteer entry."""


class Language(NamedSectionItem):
    """Canonical language entry."""


class Interest(NamedSectionItem):
    """Canonical interest entry."""


class Reference(NamedSectionItem):
    """Canonical reference entry."""


class Resume(CanonicalBaseModel):
    """Canonical source-of-truth resume."""

    basics: Basics
    work: list[Experience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[SkillGroup] = Field(default_factory=list)
    projects: list[Project] = Field(default_factory=list)
    certifications: list[Certification] = Field(default_factory=list)
    awards: list[Award] = Field(default_factory=list)
    publications: list[Publication] = Field(default_factory=list)
    volunteer: list[Volunteer] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    interests: list[Interest] = Field(default_factory=list)
    references: list[Reference] = Field(default_factory=list)
