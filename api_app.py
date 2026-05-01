"""
SceneForge HTTP API for the responsive React frontend.

Run from project root:
  uvicorn api_app:app --reload --host 127.0.0.1 --port 8765

CORS allows the Vite dev server (default http://localhost:5173).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import base64

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from pipeline_service import (
    BLUEPRINT_PATH,
    extract_explanation,
    extract_metrics,
    extract_output_path,
    list_scene_objects_resolved,
    open_in_blender,
    resolve_pipeline_python,
    run_pipeline,
    save_blueprint_bytes,
    workspace_temp_dir,
)
from scene_explainer import explain_object_in_scene

app = FastAPI(title="SceneForge API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("SCENEFORGE_CORS_ORIGINS", "http://127.0.0.1:5173,http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    prompt: str
    mode: str = "rule"
    use_blueprint: bool = False
    """If set, decode and save as blueprint.png before running (raw base64 or data URL)."""
    blueprint_base64: Optional[str] = None
    output_path: str = ""
    prefer_local_assets: bool = True
    disable_cache: bool = False
    disable_objaverse: bool = False
    disable_free: bool = False
    disable_procedural: bool = False
    asset_source_order: str = ""
    objaverse_candidate_limit: int = Field(5, ge=1, le=50)
    objaverse_min_score: float = Field(0.45, ge=0.0, le=1.0)


class ExplainRequest(BaseModel):
    scene_prompt: str
    usd_path: str
    prim_path: str


class BlenderRequest(BaseModel):
    path: str


@app.get("/api/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "service": "sceneforge-api"}


@app.get("/api/pipeline-python")
def pipeline_python() -> Dict[str, str]:
    return {"python": resolve_pipeline_python()}


@app.get("/api/ollama-status")
def ollama_status() -> Dict[str, Any]:
    from scene_explainer import _list_installed_ollama_models, _ollama_base_url

    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(f"{_ollama_base_url()}/api/tags", timeout=3) as response:
            ok = response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        ok = False
    return {
        "reachable": ok,
        "models": _list_installed_ollama_models() if ok else [],
    }


def _save_blueprint_from_payload(data: GenerateRequest) -> bool:
    if not data.blueprint_base64:
        return False
    raw = data.blueprint_base64.strip()
    if "," in raw[:120]:
        raw = raw.split(",", 1)[1]
    save_blueprint_bytes(base64.b64decode(raw))
    return True


@app.post("/api/generate")
def generate(data: GenerateRequest) -> Dict[str, Any]:
    from pipeline_service import USD_PATH

    saved_blueprint = _save_blueprint_from_payload(data)

    opts: Dict[str, Any] = {
        "mode": data.mode if data.mode in ("ai", "rule") else "rule",
        "use_blueprint": data.use_blueprint,
        "output_path": (data.output_path or "").strip() or USD_PATH,
        "prefer_local_assets": data.prefer_local_assets,
        "disable_cache": data.disable_cache,
        "disable_objaverse": data.disable_objaverse,
        "disable_free": data.disable_free,
        "disable_procedural": data.disable_procedural,
        "asset_source_order": data.asset_source_order,
        "objaverse_candidate_limit": data.objaverse_candidate_limit,
        "objaverse_min_score": data.objaverse_min_score,
    }

    if data.use_blueprint and not saved_blueprint:
        raise HTTPException(
            status_code=400,
            detail="Blueprint mode is on. Send blueprint_base64 with this request or turn blueprint mode off.",
        )

    logs, code, py = run_pipeline(data.prompt.strip(), opts)
    usd = extract_output_path(logs)
    return {
        "return_code": code,
        "logs": logs,
        "metrics": extract_metrics(logs),
        "explanation_lines": extract_explanation(logs),
        "usd_path": usd,
        "usd_exists": os.path.exists(usd),
        "pipeline_python": py,
        "blueprint_path": BLUEPRINT_PATH,
        "temp_dir": workspace_temp_dir(),
    }


@app.get("/api/scene-objects")
def scene_objects(usd_path: str) -> Dict[str, Any]:
    path = os.path.abspath(usd_path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="USD file not found")
    try:
        objs = list_scene_objects_resolved(path)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "objects": [
            {
                "prim_path": o.prim_path,
                "prim_name": o.prim_name,
                "kind": o.kind,
                "label": o.label,
                "position": list(o.position),
            }
            for o in objs
        ]
    }


@app.post("/api/explain-object")
def explain_object(req: ExplainRequest) -> Dict[str, Any]:
    path = os.path.abspath(req.usd_path)
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="USD file not found")
    objs = list_scene_objects_resolved(path)
    obj = next((o for o in objs if o.prim_path == req.prim_path), None)
    if obj is None:
        raise HTTPException(status_code=404, detail="Prim not found in stage")
    try:
        steps = explain_object_in_scene(req.scene_prompt or "", obj)
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {"steps": steps, "prim_path": obj.prim_path, "label": obj.label}


@app.post("/api/open-blender")
def blender_open(req: BlenderRequest) -> Dict[str, str]:
    msg = open_in_blender(os.path.abspath(req.path))
    return {"message": msg}
