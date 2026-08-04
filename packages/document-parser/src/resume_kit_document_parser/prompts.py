"""LLM prompt constants for resume parsing.

# ---------------------------------------------------------------------------
# Derived from apps/backend/app/prompts/templates.py
# Upstream repository: https://github.com/srbhr/Resume-Matcher
# Upstream SHA: 116f9cc3b00e1ac91734a6c2679bf41ea64a0edc
# License: Apache-2.0
# Modified: Extracted PARSE_RESUME_PROMPT and RESUME_SCHEMA_EXAMPLE as
#   standalone pure-string constants with no app.*, LiteLLM, or network
#   coupling. All other templates (improve, diff, cover-letter, etc.) are
#   deliberately omitted; add them here only when document-parser needs them.
# ---------------------------------------------------------------------------
"""

# Schema with example values — used in prompts to show the LLM the expected
# output format. Ported verbatim from upstream templates.py lines 21-94.
RESUME_SCHEMA_EXAMPLE = """{
  "personalInfo": {
    "name": "John Doe",
    "title": "Software Engineer",
    "email": "john@example.com",
    "phone": "+1-555-0100",
    "location": "San Francisco, CA",
    "website": "https://johndoe.dev",
    "linkedin": "linkedin.com/in/johndoe",
    "github": "github.com/johndoe"
  },
  "summary": "Experienced software engineer with 5+ years...",
  "workExperience": [
    {
      "id": 1,
      "title": "Senior Software Engineer",
      "company": "Tech Corp",
      "location": "San Francisco, CA",
      "years": "Jan 2020 - Present",
      "description": [
        "Led development of microservices architecture",
        "Improved system performance by 40%"
      ],
      "descriptionStyles": ["bullet", "bullet"]
    }
  ],
  "education": [
    {
      "id": 1,
      "institution": "University of California",
      "degree": "B.S. Computer Science",
      "years": "2014 - 2018",
      "description": "Graduated with honors"
    }
  ],
  "personalProjects": [
    {
      "id": 1,
      "name": "Open Source Tool",
      "role": "Creator & Maintainer",
      "years": "Mar 2021 - Present",
      "description": [
        "Built CLI tool with 1000+ GitHub stars",
        "Used by 50+ companies worldwide"
      ],
      "descriptionStyles": ["bullet", "bullet"]
    }
  ],
  "additional": {
    "technicalSkills": ["Python", "JavaScript", "AWS", "Docker"],
    "languages": ["English (Native)", "Spanish (Conversational)"],
    "certificationsTraining": ["AWS Solutions Architect"],
    "awards": ["Employee of the Year 2022"]
  },
  "customSections": {
    "publications": {
      "sectionType": "itemList",
      "items": [
        {
          "id": 1,
          "title": "Paper Title",
          "subtitle": "Journal Name",
          "years": "Jun 2023",
          "description": ["Brief description of the publication"],
          "descriptionStyles": ["bullet"]
        }
      ]
    },
    "volunteer_work": {
      "sectionType": "text",
      "text": "Description of volunteer activities..."
    }
  }
}"""

# Prompt used to instruct the LLM to parse a resume into structured JSON.
# Ported verbatim from upstream templates.py lines 162-186.
# Placeholders: {schema} — RESUME_SCHEMA_EXAMPLE, {resume_text} — raw text.
PARSE_RESUME_PROMPT = (
    "Parse this resume into JSON. Output ONLY the JSON object, no other text.\n"
    "\n"
    "Map content to standard sections when possible. For non-standard sections"
    " (like Publications, Volunteer Work, Research, Hobbies), add them to"
    " customSections with an appropriate type.\n"
    "\n"
    "Example output format:\n"
    "{schema}\n"
    "\n"
    "Custom section types:\n"
    '- "text": Single text block (e.g., objective, statement)\n'
    '- "itemList": List of items with title, subtitle, years, description'
    " (e.g., publications, research)\n"
    '- "stringList": Simple list of strings (e.g., hobbies, interests)\n'
    "\n"
    "Rules:\n"
    '- Use "" for missing text fields, [] for missing arrays, null for optional fields\n'
    "- Number IDs starting from 1\n"
    "- For workExperience, personalProjects, and custom itemList items, include"
    " descriptionStyles with one value for each description row. Use"
    ' "bullet" for normal bullet rows and "plain" for rows that should render'
    " without a bullet marker (for example subheadings or standalone labels).\n"
    "- Format dates preserving the original precision. Keep months when present:"
    ' "Jan 2020 - Dec 2023", "May 2021 - Present".'
    ' Use "YYYY - YYYY" only when the source has no months.\n'
    '- Use snake_case for custom section keys (e.g., "volunteer_work", "publications")\n'
    "- Preserve the original section name as a descriptive key\n"
    '- Normalize date separators: "2020-2021" → "2020 - 2021",'
    ' "Current"/"Ongoing" → "Present". Do NOT discard months.\n'
    '- For ambiguous dates like "3 years experience", infer approximate years'
    ' from context or use "~YYYY"\n'
    "- Flag overlapping dates (concurrent roles) by preserving both, don't merge\n"
    "\n"
    "Resume to parse:\n"
    "{resume_text}"
)
