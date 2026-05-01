"""
Scene object discovery and Ollama-backed explanations for SceneForge.

Reads transform data from generated USD stages so the Streamlit UI can show
clickable 3D markers and fetch short educational blurbs per object via the
local Ollama HTTP API.
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import List


def _ollama_base_url() -> str:
    raw = os.getenv("OLLAMA_API_URL", "http://localhost:11434").rstrip("/")
    if raw.endswith("/api/generate"):
        raw = raw[: -len("/api/generate")].rstrip("/")
    return raw


def _ollama_generate_url() -> str:
    return f"{_ollama_base_url()}/api/generate"


def _explain_model_name() -> str:
    return os.getenv(
        "OLLAMA_EXPLAIN_MODEL",
        os.getenv("SCENE_GRAPH_OLLAMA_MODEL", "llama3.2:1b"),
    )


def _list_installed_ollama_models() -> List[str]:
    url = f"{_ollama_base_url()}/api/tags"
    try:
        with urllib.request.urlopen(url, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        return []
    return [m.get("name", "") for m in payload.get("models", []) if m.get("name")]


def _resolve_ollama_model(preferred: str) -> str:
    """
    If the configured model is not installed, pick a usable one so /api/generate
    does not return 404 (common when README defaults to llama3.2:1b but only llama3:latest exists).
    """
    installed = _list_installed_ollama_models()
    if not installed:
        return preferred
    if preferred in installed:
        return preferred
    pl = preferred.lower()
    if pl.startswith("llama3") and "llama3:latest" in installed:
        return "llama3:latest"
    family = preferred.split(":", 1)[0].lower()
    for name in installed:
        if name.split(":", 1)[0].lower() == family:
            return name
    return installed[0]


def _object_kind_from_prim_name(prim_name: str) -> str:
    match = re.match(r"^(.+)_(\d+)$", prim_name)
    if match:
        return match.group(1)
    return prim_name


def _humanize_kind(kind: str) -> str:
    return kind.replace("_", " ").strip().title()


def split_explanation_text(raw: str) -> List[str]:
    """Turn a single model response into 2–5 UI steps (paragraphs, lines, or sentences)."""
    raw = (raw or "").strip()
    if not raw:
        return []

    chunks = [p.strip() for p in re.split(r"\n\s*\n+", raw) if p.strip()]
    if len(chunks) < 2:
        chunks = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if len(chunks) < 2:
        sentences = re.split(r"(?<=[.!?])\s+", raw)
        chunks = [s.strip() for s in sentences if len(s.strip()) > 10][:5]
    if len(chunks) > 5:
        chunks = chunks[:5]
    if not chunks:
        chunks = [raw]
    return chunks


@dataclass
class SceneObject:
    prim_path: str
    prim_name: str
    kind: str
    label: str
    position: tuple[float, float, float]


def list_scene_objects(usd_path: str) -> List[SceneObject]:
    try:
        from pxr import Usd, UsdGeom
    except ImportError as exc:
        raise RuntimeError(
            "Pixar USD Python bindings (pxr) are required to read scene objects."
        ) from exc

    def _get_transform_components(prim) -> tuple:
        translate = [0.0, 0.0, 0.0]
        scale = [1.0, 1.0, 1.0]
        rotate = [0.0, 0.0, 0.0]
        xformable = UsdGeom.Xformable(prim)
        for op in xformable.GetOrderedXformOps():
            op_name = op.GetOpName()
            value = op.Get()
            if op_name == "xformOp:translate":
                translate = [float(value[0]), float(value[1]), float(value[2])]
            elif op_name == "xformOp:scale":
                scale = [float(value[0]), float(value[1]), float(value[2])]
            elif op_name == "xformOp:rotateXYZ":
                rotate = [float(value[0]), float(value[1]), float(value[2])]
        return translate, scale, rotate

    if not usd_path or not os.path.isfile(usd_path):
        return []
    stage = Usd.Stage.Open(os.path.abspath(usd_path))
    if stage is None:
        return []
    world = stage.GetPrimAtPath("/World")
    if not world:
        return []

    items: List[SceneObject] = []
    for child in world.GetChildren():
        if not child.IsValid():
            continue
        name = child.GetName()
        translate, _scale, _rot = _get_transform_components(child)
        kind = _object_kind_from_prim_name(name)
        items.append(
            SceneObject(
                prim_path=str(child.GetPath()),
                prim_name=name,
                kind=kind,
                label=_humanize_kind(kind),
                position=(translate[0], translate[1], translate[2]),
            )
        )
    return items


def explain_object_in_scene(
    scene_prompt: str,
    obj: SceneObject,
    timeout_s: float = 120.0,
) -> List[str]:
    """
    Call Ollama once and return 2–5 short explanation steps for display in the UI.
    """
    url = _ollama_generate_url()
    model = _resolve_ollama_model(_explain_model_name())
    user_prompt = (
        f"The user is viewing a 3D scene described as: {scene_prompt.strip()}\n\n"
        f"They selected this object: {obj.label} (asset type: {obj.kind}, USD prim: {obj.prim_name}).\n\n"
        "Write exactly 3 to 5 short educational blurbs. Each blurb is one or two sentences. "
        "Use plain language. If this is a planet, moon, or the Sun, include accurate general astronomy. "
        "If it is furniture or architecture, describe its typical role in this kind of scene.\n\n"
        "Format: one blurb per line, no numbering, no bullet characters, no markdown."
    )
    payload = {
        "model": model,
        "prompt": user_prompt,
        "stream": False,
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        installed = ", ".join(_list_installed_ollama_models()) or "(could not list models)"
        if exc.code == 404:
            raise RuntimeError(
                f"Ollama HTTP 404 — model `{model}` is often missing. "
                f"Run: ollama pull {model}   Installed: {installed}"
            ) from exc
        raise RuntimeError(f"Ollama HTTP {exc.code}: {exc}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Ollama request failed: {exc}") from exc

    raw = (body.get("response") or "").strip()
    if not raw:
        raise RuntimeError("Ollama returned an empty explanation.")
    return split_explanation_text(raw)
