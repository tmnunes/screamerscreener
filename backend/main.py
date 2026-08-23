"""FastAPI application entrypoint (Phase 1 smoke health check only)."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__

app = FastAPI(
    title="ScreamerScreener API",
    version=__version__,
    description="Vortex Bands stock screener API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "screamerscreener",
        "version": __version__,
        "phase": "1",
    }
