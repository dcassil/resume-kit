"""FastAPI application for the Resume Kit REST API (Phase 5 transport).

The API is a thin HTTP adapter over ``resume_kit_facade``: it exposes exactly
one ``POST`` endpoint per Phase 5 capability, delegates all work to the facade,
and returns the canonical :class:`~resume_kit_core.InterfaceResponse` envelope.
No persistence, authentication, async job queue, or provider SDK is added, and
no engine package is imported here — see :mod:`resume_kit_api.routes` for the
per-endpoint adapters and the HTTP status policy.
"""

from __future__ import annotations

from fastapi import FastAPI

from resume_kit_api.routes import register_routes


def create_app() -> FastAPI:
    """Build and return the configured Resume Kit FastAPI application."""
    application = FastAPI(
        title="Resume Kit API",
        version="0.0.0",
        description="Thin REST transport over the Resume Kit capability facade.",
    )
    register_routes(application)
    return application


app = create_app()
