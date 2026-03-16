"""
Applicazione FastAPI – Dati 5x1000
===================================
Entry point principale. Monta:
  - API REST su /api/v1/
  - Download file su /download/
  - Documentazione Swagger su /api/docs
  - Frontend Vue (build statico) su /
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from routers import download, enti, status

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Dati 5x1000",
    description=(
        "API pubblica per i dati del 5 per mille italiano.\n\n"
        "Fonte: Agenzia delle Entrate – dati 2006-2025.\n"
        "Licenza dati: CC BY 4.0"
    ),
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ---------------------------------------------------------------------------
# CORS (permissivo di default, limitare in produzione tramite .env)
# ---------------------------------------------------------------------------
origins = settings.cors_origins if settings.cors_origins != ["*"] else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers API
# ---------------------------------------------------------------------------
app.include_router(status.router,   prefix="/api/v1")
app.include_router(enti.router,     prefix="/api/v1")
app.include_router(download.router)  # prefissato internamente su /download

# ---------------------------------------------------------------------------
# Frontend Vue (serve la build Vite)
# ---------------------------------------------------------------------------
_frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(_frontend_dist), html=True), name="frontend")
