# Canonical Resume JSON Specification

## Purpose

Define a normalized, source-of-truth resume structure for parsing, storage, ATS analysis, job matching, tailoring, and rendering.

The model is based on JSON Resume conventions but is intentionally stricter and richer where useful for automated resume tooling.

The canonical resume represents **facts and evidence**, not a specific rendered resume. Job-specific resumes should be projections of this source model.

## Cardinality

* `1` — exactly one, required
* `0..1` — optional, at most one
* `1..*` — one or more
* `0..*` — zero or more
* `oneOf(A,B,C)` — exactly one allowed type/value
* `oneOrMore(A,B,C)` — at least one listed field must contain content

---

## Resume

```ts
interface Resume {
  basics: Basics;                    // 1

  work?: Experience[];               // 0..*
  education?: Education[];           // 0..*
  skills?: SkillGroup[];             // 0..*
  projects?: Project[];              // 0..*
  certifications?: Certification[]; // 0..*
  awards?: Award[];                  // 0..*
  publications?: Publication[];      // 0..*
  volunteer?: Volunteer[];           // 0..*
  languages?: Language[];            // 0..*
  interests?: Interest[];            // 0..*
  references?: Reference[];          // 0..*
}
```

---

## Basics

```ts
interface Basics {
  name: string;             // 1

  headline?: string;        // 0..1
  summary?: string;         // 0..1

  email?: string;           // 0..1
  phone?: string;           // 0..1

  location?: Location;      // 0..1
  links?: Link[];           // 0..*
}
```

Rules:

```text
name: 1

contact:
  oneOrMore:
    email
    phone

headline: 0..1
summary: 0..1
location: 0..1
links: 0..*
```

---

## Location

```ts
interface Location {
  city?: string;
  region?: string;
  countryCode?: string;
  postalCode?: string;
  address?: string;
}
```

All fields are `0..1`.

Full street addresses should generally not be required.

Preferred:

```json
{
  "city": "Oklahoma City",
  "region": "OK",
  "countryCode": "US"
}
```

---

## Experience

```ts
interface Experience {
  organization: string;             // 1
  title: string;                    // 1

  employmentType?: EmploymentType; // 0..1

  location?: Location | string;     // 0..1

  startDate?: ResumeDate;           // 0..1
  endDate?: ResumeDate | "present"; // 0..1

  summary?: string;                 // 0..1

  achievements: Achievement[];      // 1..*

  skills?: string[];                // 0..*
  technologies?: string[];          // 0..*
  links?: Link[];                   // 0..*
}
```

```ts
type EmploymentType =
  | "full-time"
  | "part-time"
  | "contract"
  | "consulting"
  | "freelance"
  | "internship"
  | "founder"
  | "other";
```

Rules:

```text
organization: 1
title: 1
employmentType: 0..1 oneOf(enum)

startDate: 0..1
endDate: 0..1

oneOrMore:
  summary
  achievements

achievements: preferably 1..*
skills: 0..*
technologies: 0..*
links: 0..*
```

---

## Achievement

Achievements are structured evidence rather than only rendered bullet strings.

```ts
interface Achievement {
  text: string;             // 1

  action?: string;          // 0..1
  result?: string;          // 0..1

  metrics?: Metric[];       // 0..*
  skills?: string[];        // 0..*
  keywords?: string[];      // 0..*
}
```

Example:

```json
{
  "text": "Reduced infrastructure costs 42%, saving approximately $180K annually.",
  "action": "Optimized infrastructure architecture",
  "result": "Reduced infrastructure costs",
  "metrics": [
    {
      "type": "percentage",
      "value": 42
    },
    {
      "type": "currency",
      "value": 180000,
      "currency": "USD",
      "label": "annual savings"
    }
  ]
}
```

---

## Metric

```ts
type Metric =
  | {
      type: "percentage";
      value: number;
      label?: string;
    }
  | {
      type: "currency";
      value: number;
      currency: string;
      label?: string;
    }
  | {
      type: "count";
      value: number;
      unit?: string;
      label?: string;
    }
  | {
      type: "duration";
      value: number;
      unit: "hours" | "days" | "weeks" | "months";
      label?: string;
    };
```

Metric is:

```text
oneOf:
  percentage
  currency
  count
  duration
```

---

## Skills

```ts
interface SkillGroup {
  name: string;          // 1
  keywords: string[];    // 1..*
}
```

Example:

```json
{
  "name": "Languages",
  "keywords": [
    "TypeScript",
    "JavaScript",
    "C#",
    "Java"
  ]
}
```

Rules:

```text
skills: 0..*

SkillGroup:
  name: 1
  keywords: 1..*
```

Avoid subjective proficiency fields such as `"expert"`, `"advanced"` or `"8/10"` unless explicitly needed.

---

## Project

```ts
interface Project {
  name: string;                    // 1

  description?: string;            // 0..1
  achievements?: Achievement[];    // 0..*

  roles?: string[];                // 0..*
  technologies?: string[];         // 0..*
  skills?: string[];               // 0..*
  links?: Link[];                  // 0..*

  startDate?: ResumeDate;          // 0..1
  endDate?: ResumeDate | "present";// 0..1
}
```

Rules:

```text
name: 1

oneOrMore:
  description
  achievements

roles: 0..*
technologies: 0..*
skills: 0..*
links: 0..*
```

---

## Education

```ts
interface Education {
  institution: string;       // 1

  degree?: string;           // 0..1
  field?: string;            // 0..1

  startDate?: ResumeDate;    // 0..1
  endDate?: ResumeDate;      // 0..1

  score?: string;            // 0..1
  courses?: string[];        // 0..*
  highlights?: string[];     // 0..*
}
```

Rules:

```text
institution: 1

oneOrMore:
  degree
  field
  highlights

courses: 0..*
highlights: 0..*
```

---

## Certification

```ts
interface Certification {
  name: string;                // 1

  issuer?: string;             // 0..1
  date?: ResumeDate;           // 0..1
  expirationDate?: ResumeDate;// 0..1
  credentialId?: string;       // 0..1

  links?: Link[];              // 0..*
}
```

---

## Link

Use a common link structure instead of section-specific URL fields.

```ts
interface Link {
  type: LinkType;          // 1
  url: string;             // 1
  label?: string;          // 0..1
}
```

```ts
type LinkType =
  | "linkedin"
  | "github"
  | "portfolio"
  | "website"
  | "project"
  | "publication"
  | "credential"
  | "other";
```

Links are generally `0..*`.

---

## Dates

Dates should preserve the precision actually known.

```ts
type ResumeDate =
  | "YYYY"
  | "YYYY-MM"
  | "YYYY-MM-DD";
```

Do not invent missing month/day precision.

Use `"present"` for current positions/projects.

---

## Remaining Sections

These are all optional collections:

```text
awards: 0..*
publications: 0..*
volunteer: 0..*
languages: 0..*
interests: 0..*
references: 0..*
```

Each item should have one required identifying field, generally `name`, with supporting fields optional.

---

## Core Cardinality Summary

```text
Resume
  basics                  1
  work                    0..*
  education               0..*
  skills                  0..*
  projects                0..*
  certifications          0..*
  awards                  0..*
  publications            0..*
  volunteer               0..*
  languages               0..*
  interests               0..*
  references              0..*

Basics
  name                    1
  email                   0..1
  phone                   0..1
  headline                0..1
  summary                 0..1
  location                0..1
  links                   0..*

  oneOrMore:
    email
    phone

Experience
  organization            1
  title                   1
  employmentType          0..1 oneOf(enum)
  startDate               0..1
  endDate                 0..1
  summary                 0..1
  achievements            0..*
  skills                  0..*
  technologies            0..*
  links                   0..*

  oneOrMore:
    summary
    achievements

Achievement
  text                    1
  action                  0..1
  result                  0..1
  metrics                 0..*
  skills                  0..*
  keywords                0..*

SkillGroup
  name                    1
  keywords                1..*

Project
  name                    1
  description             0..1
  achievements            0..*
  roles                   0..*
  technologies            0..*
  skills                  0..*
  links                   0..*

  oneOrMore:
    description
    achievements

Education
  institution             1
  degree                  0..1
  field                   0..1
  courses                 0..*
  highlights              0..*

Certification
  name                    1
  issuer                  0..1
  date                    0..1
  expirationDate          0..1
  credentialId            0..1
  links                   0..*

Link
  type                    1 oneOf(enum)
  url                     1
  label                   0..1

Metric
  oneOf:
    percentage
    currency
    count
    duration
```

## Architectural Rules

1. **Canonical data is the source of truth.** Never overwrite factual source data merely to match a job posting.

2. **Rendered resumes are projections.** A job-specific resume selects, orders, condenses, and rewrites canonical evidence.

3. **Separate facts from presentation.** Section order, bullet order, formatting, headings, page limits, and wording belong to the rendered resume layer.

4. **Preserve provenance where possible.** Generated or rewritten claims should remain traceable to the canonical experience, project, achievement, or skill that supports them.

5. **Never invent evidence.** Tailoring may rephrase, prioritize, combine, or omit facts, but should not introduce unsupported skills, metrics, responsibilities, or outcomes.

6. **Prefer structured evidence.** Metrics, technologies, skills, dates, organizations, roles, and links should be represented as data instead of extracted repeatedly from prose.

7. **Preserve original text.** When importing resumes, retain original wording alongside normalized/structured values where useful so transformations can be audited or reversed.

8. **Canonical resume ≠ submitted resume.** One canonical resume may generate many job-specific resume variants without changing the underlying source-of-truth data.
