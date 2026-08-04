"""resume_kit_export — resume export package (PDF and DOCX).

Public surface at this scaffold stage:

- :class:`ExportFormat` — ``pdf`` / ``docx`` StrEnum.
- :class:`ExportOptions` — deterministic, typed render options.
- :func:`render` — format-dispatching entry point.

``render_pdf`` and ``render_docx`` are deferred to the public-exports task
once the individual renderer modules exist.
"""

from resume_kit_export.models import ExportFormat, ExportOptions
from resume_kit_export.render import render

__all__ = [
    "ExportFormat",
    "ExportOptions",
    "render",
]
