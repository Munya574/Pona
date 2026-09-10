"""
Pona API Server

FastAPI app that serves:
- Profile management
- Food scanning (placeholder for now)
- Verdict generation (core ML endpoint)
- Substitutions (placeholder for now)
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import scan, verdict, profile, substitutions, conditions
from app.database import init_db

app = FastAPI(
    title="Pona API",
    version="0.1.0",
    description="Food sensitivity checking API"
)

# ── Initialize database on startup ─────────────────────────────────────────────
@app.on_event("startup")
async def startup_event():
    """
    Called when the server starts up.

    We initialize the database here (create tables if they don't exist).
    In production, you'd use Alembic for schema migrations instead.
    """
    init_db()
    print("[API] Database initialized")


# ── CORS middleware ────────────────────────────────────────────────────────────
# Why CORS?
# - Frontend (localhost:5173) calls backend (localhost:8000)
# - Without CORS, browser blocks the request for security
# - We allow localhost for development, restrict in production

# Local dev origins, plus whatever the deployment sets. CORS_ORIGINS is a
# comma-separated list, e.g. "https://pona.vercel.app".
#
# Deliberately not "*": a wildcard here would let any site call this API
# with a user's profile id and read their health conditions back.
_DEFAULT_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]
_EXTRA_ORIGINS = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_DEFAULT_ORIGINS + _EXTRA_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Include routers ────────────────────────────────────────────────────────────
# Routes are organized by concern (scan, verdict, profile, substitutions)
# Each router has its own logic + database queries

app.include_router(scan.router, prefix="/scan", tags=["scan"])
app.include_router(verdict.router, prefix="/verdict", tags=["verdict"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(conditions.router, prefix="/conditions", tags=["conditions"])
app.include_router(substitutions.router, prefix="/substitutions", tags=["substitutions"])


# ── Health check ───────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    """Health check endpoint for load balancers."""
    return {"status": "ok", "service": "pona-api"}


# ── Startup message ────────────────────────────────────────────────────────────

@app.on_event("startup")
async def print_startup():
    print("\n" + "=" * 80)
    print("PONA API SERVER STARTING")
    print("=" * 80)
    print("\nEndpoints:")
    print("  POST   /profile           - Create sensitivity profile")
    print("  GET    /profile/{id}      - Get profile details")
    print("  PUT    /profile/{id}      - Update profile")
    print("  GET    /conditions        - List checkable conditions")
    print("  POST   /verdict           - Check a food against a profile")
    print("  POST   /scan/photo        - Scan food from photo (stub)")
    print("  POST   /scan/ocr          - Scan food from label (stub)")
    print("  POST   /scan/url          - Scan food from recipe (stub)")
    print("  POST   /substitutions     - Get ingredient substitutes (stub)")
    print("\nDocs:")
    print("  http://localhost:8000/docs (Swagger UI)")
    print("  http://localhost:8000/redoc (ReDoc)")
    print("\n" + "=" * 80 + "\n")
