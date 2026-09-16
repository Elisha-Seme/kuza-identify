"""FastAPI application entry point — the Kuza Connect Layer 1 backend.

This is a modular monolith: one process, one module per Section 4 service. The
two batch services (Passive Candidate, Bias Audit) run as CLI jobs, not HTTP
routes (see app/cli/). KEMIS is interface-only and has no route.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, nomination, panel, screening
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title="Kuza Connect, Layer 1 (Phase 0 MVP)",
    version="0.1.0",
    description=(
        "Identification engine: Screening Gateway, Adaptive Item Engine, "
        "Nomination, LLM Scoring, Aggregation & Flag Engine, Panel Review. "
        "See README for the full spec-section mapping."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",")],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(screening.router)
app.include_router(nomination.router)
app.include_router(panel.router)
app.include_router(admin.router)


@app.get("/", tags=["meta"])
def root() -> dict:
    """Friendly landing so the base URL isn't a bare 404."""
    return {
        "service": "Kuza Connect, Layer 1 identification engine (Phase 0)",
        "what": "Finds gifted learners (incl. twice-exceptional) via screening, "
        "nomination and passive record-mining; AI flags, a human panel decides.",
        "links": {
            "interactive_api_docs": "/docs",
            "health": "/health",
            "screening_questions": "/screening/items",
            "nomination_form": "/nomination/form",
            "flagged_profiles": "/panel/flagged",
            "dashboard": "https://kuza-identify-dashboard.vercel.app",
        },
    }


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "llm_scoring": "live" if settings.llm_enabled else "mock (no ANTHROPIC_API_KEY)",
        "whatsapp_provider": settings.whatsapp_provider,
    }
