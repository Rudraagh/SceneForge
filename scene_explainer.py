"""
Scene object discovery and Ollama-backed explanations for SceneForge.

Reads transform data from generated USD stages so the Streamlit UI can show
clickable 3D markers and fetch short educational blurbs per object via the
local Ollama HTTP API.
"""

from __future__ import annotations

import errno
import json
import os
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


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


_KIND_LABELS = {
    "blackboard": "Board zone (green on blueprint)",
    "door": "Door / exit zone",
    "wooden_desk": "Desk zone",
    "table": "Table zone",
}


def _humanize_kind(kind: str) -> str:
    if kind in _KIND_LABELS:
        return _KIND_LABELS[kind]
    return kind.replace("_", " ").strip().title()


def _build_explain_prompt(
    scene_prompt: str,
    obj: SceneObject,
    compact: bool,
    rag_context: str = "",
) -> str:
    prefix = (rag_context or "").strip()
    if prefix:
        prefix = prefix + "\n\n"

    if compact:
        sp = (scene_prompt or "").strip()
        if len(sp) > 420:
            sp = sp[:417] + "..."
        body = (
            f"Scene: {sp}\n"
            f"Object: {obj.label} (type: {obj.kind}).\n\n"
            "Give 3 to 5 very short educational facts (one sentence each). "
            "Separate facts with one blank line. Plain text only, no markdown or bullets."
        )
        return prefix + body
    body = (
        f"The user is viewing a 3D scene described as: {scene_prompt.strip()}\n\n"
        f"They selected this object: {obj.label} (asset type: {obj.kind}, USD prim: {obj.prim_name}).\n\n"
        "Write exactly 3 to 5 short educational blurbs. Each blurb is one or two sentences. "
        "Use plain language. If this is a planet, moon, or the Sun, include accurate general astronomy. "
        "If it is furniture or architecture, describe its typical role in this kind of scene.\n\n"
        "Format: one blurb per line, no numbering, no bullet characters, no markdown."
    )
    return prefix + body


def _is_connection_refused(exc: BaseException) -> bool:
    """True when Ollama (or any TCP target) refused the connection — common if the daemon is not running."""
    seen: set[int] = set()
    cur: BaseException | None = exc
    while cur is not None and id(cur) not in seen:
        seen.add(id(cur))
        if isinstance(cur, ConnectionRefusedError):
            return True
        if isinstance(cur, OSError):
            if cur.errno == errno.ECONNREFUSED:
                return True
            # Windows: WSAECONNREFUSED
            if getattr(cur, "winerror", None) == 10061:
                return True
        nxt: BaseException | None = None
        if isinstance(cur, urllib.error.URLError) and cur.reason is not None:
            nxt = cur.reason  # type: ignore[assignment]
        elif cur.__cause__ is not None:
            nxt = cur.__cause__
        elif cur.__context__ is not None and not cur.__suppress_context__:
            nxt = cur.__context__
        cur = nxt
    return False


def _ollama_unreachable_message(exc: BaseException) -> str:
    base = _ollama_base_url()
    if _is_connection_refused(exc):
        return (
            f"Cannot reach Ollama at {base} (connection refused). "
            "The API process could not open a TCP connection — usually Ollama is not running.\n\n"
            "Fix: start Ollama (open the Ollama app from the Start menu on Windows, or run `ollama serve` in a terminal), "
            "wait until it is listening, then use **Recheck** in the SceneForge header.\n\n"
            "If Ollama uses another address, set environment variable OLLAMA_API_URL "
            "(for example http://127.0.0.1:11434), restart the FastAPI server (uvicorn), and try again."
        )
    return f"Ollama request failed: {exc}"


def _http_error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        raw = exc.read().decode("utf-8", errors="replace")
    except Exception:
        return ""
    raw = raw.strip()
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict) and "error" in parsed:
            return str(parsed["error"])[:600]
    except json.JSONDecodeError:
        pass
    return raw[:600]


def _post_ollama_generate(url: str, payload: Dict[str, Any], timeout_s: float) -> Dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return json.loads(response.read().decode("utf-8"))


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

    Uses modest ``options`` (context / max tokens) to reduce HTTP 500 from large models
    on limited RAM/VRAM. On 500, retries once with a shorter prompt and tighter limits.
    """
    url = _ollama_generate_url()
    model = _resolve_ollama_model(_explain_model_name())
    installed = ", ".join(_list_installed_ollama_models()) or "(could not list models)"

    rag_context = ""
    try:
        from sceneforge.rag import rag_globally_disabled, retrieved_context_block

        if not rag_globally_disabled():
            rag_context = retrieved_context_block(
                f"{scene_prompt}\nObject to explain: {obj.label} ({obj.kind})."
            )
    except Exception:
        rag_context = ""

    def _payload(compact: bool, options: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        p: Dict[str, Any] = {
            "model": model,
            "prompt": _build_explain_prompt(
                scene_prompt, obj, compact=compact, rag_context=rag_context
            ),
            "stream": False,
        }
        if options:
            p["options"] = options
        return p

    primary_options = {
        "num_ctx": int(os.getenv("OLLAMA_EXPLAIN_NUM_CTX", "4096")),
        "num_predict": int(os.getenv("OLLAMA_EXPLAIN_NUM_PREDICT", "512")),
    }
    fallback_options = {"num_ctx": 2048, "num_predict": 320}

    body: Dict[str, Any]
    try:
        body = _post_ollama_generate(url, _payload(False, primary_options), timeout_s)
    except urllib.error.HTTPError as exc:
        detail = _http_error_detail(exc)
        if exc.code == 404:
            raise RuntimeError(
                f"Ollama HTTP 404 — model `{model}` is often missing. "
                f"Run: ollama pull {model}   Installed: {installed}"
            ) from exc
        if exc.code == 500:
            try:
                body = _post_ollama_generate(url, _payload(True, fallback_options), timeout_s)
            except urllib.error.HTTPError as exc2:
                detail2 = _http_error_detail(exc2)
                raise RuntimeError(
                    "Ollama HTTP 500 while generating the explanation. "
                    "That usually means the model runner crashed or ran out of memory.\n\n"
                    f"First error: {detail or '(no message from server)'}\n"
                    f"Retry error: {detail2 or '(no message)'}\n\n"
                    "Try: restart Ollama, close other GPU apps, use a smaller model "
                    "(`setx OLLAMA_EXPLAIN_MODEL mistral:latest` then reopen terminal), "
                    "or set `OLLAMA_EXPLAIN_NUM_CTX=2048`.\n"
                    f"Installed models: {installed}"
                ) from exc2
        raise RuntimeError(
            f"Ollama HTTP {exc.code}: {detail or exc.reason or str(exc)}"
        ) from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(_ollama_unreachable_message(exc)) from exc

    raw = (body.get("response") or "").strip()
    if not raw:
        raise RuntimeError("Ollama returned an empty explanation.")
    return split_explanation_text(raw)
