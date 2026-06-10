from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import scan, verdict, profile, substitutions

app = FastAPI(title="Pona API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(scan.router, prefix="/scan", tags=["scan"])
app.include_router(verdict.router, prefix="/verdict", tags=["verdict"])
app.include_router(profile.router, prefix="/profile", tags=["profile"])
app.include_router(substitutions.router, prefix="/substitutions", tags=["substitutions"])


@app.get("/health")
def health():
    return {"status": "ok"}
