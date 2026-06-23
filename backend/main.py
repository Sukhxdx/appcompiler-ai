"""AppCompiler AI — FastAPI backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline.evaluator import PipelineOrchestrator, load_results, run_evaluation

STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(
    title="AppCompiler AI",
    description="AI engineer internship demo: NL requirements → validated executable app config",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    prompt: str = Field(..., min_length=1, description="Natural language app requirements")


class GenerateResponse(BaseModel):
    success: bool
    config: Optional[dict[str, Any]] = None
    intent: Optional[dict[str, Any]] = None
    design: Optional[dict[str, Any]] = None
    stage_status: dict[str, str] = Field(default_factory=dict)
    metrics: dict[str, Any] = Field(default_factory=dict)
    runtime_simulation: Optional[dict[str, Any]] = None
    validation_report: Optional[dict[str, Any]] = None
    error: Optional[str] = None


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "appcompiler-ai"}


@app.get("/generate")
async def generate_get() -> RedirectResponse:
    """Browser navigation to /generate uses GET — redirect to the UI."""
    return RedirectResponse(url="/", status_code=302)


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest) -> GenerateResponse:
    orchestrator = PipelineOrchestrator()
    result = await orchestrator.run(request.prompt)
    return GenerateResponse(**result)


@app.get("/evaluation/run")
async def evaluation_run() -> dict[str, Any]:
    try:
        return await run_evaluation()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.get("/evaluation/results")
async def evaluation_results() -> dict[str, Any]:
    return load_results()


@app.get("/")
async def serve_ui() -> FileResponse:
    """Serve the web UI (no separate frontend server required)."""
    return FileResponse(STATIC_DIR / "index.html")


if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
