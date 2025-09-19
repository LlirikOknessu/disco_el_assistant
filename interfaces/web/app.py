"""FastAPI application that exposes the Disco EL assistant."""
from __future__ import annotations

from pathlib import Path
from typing import Dict

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from core.orchestrator import Orchestrator

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(title="Disco EL Assistant", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class ChatRequest(BaseModel):
    message: str
    profile: str = "work"


orchestrators: Dict[str, Orchestrator] = {}


def get_orchestrator(profile: str) -> Orchestrator:
    profile = profile.lower()
    if profile not in orchestrators:
        try:
            orchestrators[profile] = Orchestrator.from_profile(profile)
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return orchestrators[profile]


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    if not STATIC_DIR.exists():
        raise HTTPException(status_code=404, detail="Web UI is not available.")
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="index.html is missing.")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/healthz")
async def healthcheck() -> dict:
    return {"status": "ok"}


@app.post("/api/chat")
async def chat(request: ChatRequest) -> dict:
    orchestrator = get_orchestrator(request.profile)
    responses = orchestrator.handle_message(request.message)
    return {
        "profile": request.profile,
        "responses": [response.to_dict() for response in responses],
        "history": orchestrator.get_history(),
    }


@app.get("/api/history")
async def history(profile: str = "work") -> dict:
    orchestrator = get_orchestrator(profile)
    return {"profile": profile, "history": orchestrator.get_history()}
