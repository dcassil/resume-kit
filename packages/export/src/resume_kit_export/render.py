"""Top-level render dispatcher for resume-kit-export.

Renderer modules (``resume_kit_export.pdf`` and ``resume_kit_export.docx``)
are imported *lazily* — only at the moment a render call is made for that
format. This keeps the package importable before the renderer tasks land.
"""

from __future__ import annotations

from collections.abc import Callable

from resume_kit_schemas.resume import ResumeDocument

from resume_kit_export.models import ExportFormat, ExportOptions


def render(
    resume: ResumeDocument,
    fmt: ExportFormat,
    options: ExportOptions | None = None,
) -> bytes:
    """Render *resume* to bytes in the requested *fmt*.

    Args:
        resume: The canonical :class:`~resume_kit_schemas.resume.ResumeDocument`
            to export.
        fmt: The desired :class:`ExportFormat` (``pdf`` or ``docx``).
        options: Optional :class:`ExportOptions`; defaults are used when
            ``None`` is passed.

    Returns:
        Raw bytes of the rendered document.

    Raises:
        ImportError: If the renderer module for *fmt* has not been installed
            yet (i.e. the renderer task has not landed).
        NotImplementedError: If *fmt* is not handled by this dispatcher (should
            not occur with the current :class:`ExportFormat` members, but
            guards against future additions before the dispatcher is updated).
    """
    resolved_options = options if options is not None else ExportOptions()

    if fmt is ExportFormat.pdf:
        renderer_fn: Callable[[ResumeDocument, ExportOptions], bytes] = _load_pdf()
        return renderer_fn(resume, resolved_options)

    if fmt is ExportFormat.docx:
        renderer_fn = _load_docx()
        return renderer_fn(resume, resolved_options)

    raise NotImplementedError(f"No renderer registered for format: {fmt!r}")


def _load_pdf() -> Callable[[ResumeDocument, ExportOptions], bytes]:
    """Lazily import and return the PDF renderer callable."""
    try:
        import importlib

        mod = importlib.import_module("resume_kit_export.pdf")
    except ImportError as exc:
        raise ImportError(
            "PDF renderer is not available yet. "
            "Install or await the resume_kit_export.pdf module."
        ) from exc
    fn: Callable[[ResumeDocument, ExportOptions], bytes] = mod.render_pdf
    return fn


def _load_docx() -> Callable[[ResumeDocument, ExportOptions], bytes]:
    """Lazily import and return the DOCX renderer callable."""
    try:
        import importlib

        mod = importlib.import_module("resume_kit_export.docx")
    except ImportError as exc:
        raise ImportError(
            "DOCX renderer is not available yet. "
            "Install or await the resume_kit_export.docx module."
        ) from exc
    fn: Callable[[ResumeDocument, ExportOptions], bytes] = mod.render_docx
    return fn
