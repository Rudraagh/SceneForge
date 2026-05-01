"""
Shared scene pipeline helpers for Streamlit and the FastAPI web UI.

Runs direct_usd_scene.py with the same options as the legacy Streamlit app and
parses logs for metrics, explanation lines, and exported USDA paths.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scene_explainer import SceneObject, list_scene_objects

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))
BLUEPRINT_PATH = os.path.join(PROJECT_ROOT, "blueprint.png")
USD_PATH = os.path.abspath(os.path.join(PROJECT_ROOT, "generated_scene.usda"))
BLENDER_PATH = os.environ.get(
    "SCENEFORGE_BLENDER_PATH",
    r"C:\\Program Files\\Blender Foundation\\Blender 4.0\\blender.exe",
)
PREFERRED_PYTHON = os.environ.get(
    "SCENEFORGE_PREFERRED_PYTHON",
    r"C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe",
)


def resolve_pipeline_python() -> str:
    override = os.getenv("SCENEFORGE_PYTHON", "").strip()
    candidates = [override, PREFERRED_PYTHON, sys.executable]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return os.path.abspath(candidate)
    return "python"


def run_pipeline(prompt: str, options: Dict[str, Any]) -> Tuple[str, int, str]:
    pipeline_python = resolve_pipeline_python()
    cmd = [
        pipeline_python,
        "direct_usd_scene.py",
        "--mode",
        options["mode"],
        "--output",
        options["output_path"],
    ]
    if options.get("use_blueprint"):
        cmd.extend(["--blueprint", "--blueprint-path", BLUEPRINT_PATH])
    if options.get("prefer_local_assets"):
        cmd.append("--prefer-local-assets")
    if options.get("disable_cache"):
        cmd.append("--disable-cache")
    if options.get("disable_objaverse"):
        cmd.append("--disable-objaverse")
    if options.get("disable_free"):
        cmd.append("--disable-free")
    if options.get("disable_procedural"):
        cmd.append("--disable-procedural")
    order = (options.get("asset_source_order") or "").strip()
    if order:
        cmd.extend(["--asset-source-order", order])
    if options.get("objaverse_candidate_limit") is not None:
        cmd.extend(["--objaverse-candidate-limit", str(int(options["objaverse_candidate_limit"]))])
    if options.get("objaverse_min_score") is not None:
        cmd.extend(["--objaverse-min-score", str(float(options["objaverse_min_score"]))])
    cmd.append(prompt)

    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"

    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=PROJECT_ROOT,
        env=env,
    )
    stdout, stderr = process.communicate()
    combined = stdout or ""
    if stderr:
        combined = f"{combined}\n{stderr}" if combined else stderr
    return combined, int(process.returncode), pipeline_python


def extract_metrics(logs: str) -> Optional[Dict[str, Any]]:
    match = re.search(
        r"\[RESULT\] score=([-\d.]+) \| objects=(\d+) \| violations=(\d+) \| iterations=(\d+)",
        logs,
    )
    if not match:
        return None
    return {
        "score": float(match.group(1)),
        "objects": int(match.group(2)),
        "violations": int(match.group(3)),
        "iterations": int(match.group(4)),
    }


def extract_explanation(logs: str) -> List[str]:
    lines = logs.splitlines()
    return [line for line in lines if "[EXPLAIN]" in line or "[DETAIL]" in line]


def extract_output_path(logs: str) -> str:
    path_matches = re.findall(r"\[INFO\] Exported stage path: (.+)", logs)
    if path_matches:
        return os.path.abspath(path_matches[-1].strip())
    matches = re.findall(r"\[INFO\] Exported stage to file: (.+)", logs)
    if matches:
        return os.path.abspath(os.path.join(PROJECT_ROOT, matches[-1].strip()))
    return USD_PATH


def save_blueprint_bytes(data: bytes) -> None:
    Path(BLUEPRINT_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(BLUEPRINT_PATH, "wb") as handle:
        handle.write(data)


def open_in_blender(path: str) -> str:
    if not os.path.exists(BLENDER_PATH):
        return "Blender not found"
    if not os.path.exists(path):
        return "USD file not found"
    subprocess.Popen([BLENDER_PATH, path], cwd=PROJECT_ROOT)
    return "Opened in Blender"


def score_band(score: float) -> str:
    if score > 0.7:
        return "green"
    if score >= 0.5:
        return "orange"
    return "red"


def workspace_temp_dir() -> str:
    return tempfile.gettempdir()


LIST_SCENE_OBJECTS_CLI = os.path.join(PROJECT_ROOT, "list_scene_objects_json.py")


def list_scene_objects_resolved(usd_path: str) -> List[SceneObject]:
    """
    List prims under /World for the Plotly picker.

    Prefer in-process ``pxr`` (fast). If the API server Python lacks USD bindings
    but ``resolve_pipeline_python()`` has them (common when uvicorn uses a slim
    venv while the pipeline uses a Kit or full Python), delegate to
    ``list_scene_objects_json.py`` in a subprocess.
    """
    try:
        return list_scene_objects(usd_path)
    except RuntimeError as exc:
        if "Pixar USD Python bindings" not in str(exc):
            raise
    return _list_scene_objects_subprocess(usd_path)


def _list_scene_objects_subprocess(usd_path: str) -> List[SceneObject]:
    if not os.path.isfile(LIST_SCENE_OBJECTS_CLI):
        raise RuntimeError(
            "Pixar USD (pxr) is not available in the API process, and "
            "list_scene_objects_json.py is missing from the project root."
        ) from None
    py = resolve_pipeline_python()
    r = subprocess.run(
        [py, LIST_SCENE_OBJECTS_CLI, os.path.abspath(usd_path)],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=90,
        env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"},
    )
    if r.returncode != 0:
        tail = (r.stderr or r.stdout or "").strip()[-2000:]
        raise RuntimeError(
            "Could not list scene objects via the pipeline Python interpreter "
            f"({py}). Install pxr/usd-core there, or run uvicorn with the same Python.\n"
            f"Exit code {r.returncode}. Output:\n{tail}"
        )
    try:
        rows = json.loads(r.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Scene object helper returned invalid JSON:\n" + (r.stdout or "")[:800]
        ) from exc
    out: List[SceneObject] = []
    for o in rows:
        pos = o["position"]
        out.append(
            SceneObject(
                prim_path=str(o["prim_path"]),
                prim_name=str(o["prim_name"]),
                kind=str(o["kind"]),
                label=str(o["label"]),
                position=(float(pos[0]), float(pos[1]), float(pos[2])),
            )
        )
    return out
