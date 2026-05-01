"""
AI-assisted scene graph generation with deterministic safety constraints.

This module prefers a local Ollama model for structured JSON generation and
falls back to a deterministic rule layout if the model output is unusable.
"""

from __future__ import annotations

import json
import math
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Optional


PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_PATH = PROJECT_ROOT / "scene_dataset.json"
DEFAULT_MODEL = os.getenv("SCENE_GRAPH_OLLAMA_MODEL", "llama3.2:1b")
DEFAULT_OLLAMA_URL = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
MAX_ABS_XZ = 12.0
MAX_Y = 1.5
MIN_DISTANCE = 1.6


def supported_assets() -> set[str]:
    return {
        "wooden_desk",
        "table",
        "chair",
        "blackboard",
        "lamp",
        "bookshelf",
        "throne",
        "banner",
        "torch",
        "barrel",
        "crate",
        "campfire",
        "pine_tree",
        "bench",
        "market_stall",
        "sun",
        "mercury",
        "venus",
        "earth",
        "mars",
        "jupiter",
        "saturn",
        "uranus",
        "neptune",
    }


def canonicalize_object_name(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    synonyms = {
        "desk": "wooden_desk",
        "school_desk": "wooden_desk",
        "teacher_desk": "wooden_desk",
        "seat": "chair",
        "student_seat": "chair",
        "stool": "chair",
        "board": "blackboard",
        "chalkboard": "blackboard",
        "sign_board": "blackboard",
        "shelf": "bookshelf",
        "bookcase": "bookshelf",
        "fire": "campfire",
        "camp_fire": "campfire",
        "tree": "pine_tree",
        "pine": "pine_tree",
        "stall": "market_stall",
        "vendor_stall": "market_stall",
        "crate_stack": "crate",
        "torchlight": "torch",
        "king_chair": "throne",
        "sol": "sun",
    }
    return synonyms.get(key, key)


def detect_scene_type(prompt: str) -> str:
    text = prompt.lower()
    if any(word in text for word in ("classroom", "school", "lecture", "teacher", "desk")):
        return "classroom"
    if any(word in text for word in ("throne", "castle", "royal", "king", "queen", "hall")):
        return "throne_room"
    if any(word in text for word in ("forest", "camp", "campfire", "woods", "clearing")):
        return "forest_camp"
    if any(word in text for word in ("market", "bazaar", "vendor", "stall")):
        return "market"
    if any(word in text for word in ("tavern", "inn", "pub")):
        return "tavern"
    if any(
        phrase in text
        for phrase in (
            "solar system",
            "planetary system",
            "planets orbiting",
            "planets around the sun",
            "sun and planets",
        )
    ):
        return "solar_system"
    return "studio"


def load_dataset(dataset_path: Path = DATASET_PATH) -> List[Dict]:
    if not dataset_path.exists():
        return []
    with dataset_path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def select_examples(prompt: str, limit: int = 2) -> List[Dict]:
    prompt_tokens = _tokenize(prompt)
    scored = []
    for item in load_dataset():
        item_prompt = str(item.get("prompt", ""))
        overlap = len(prompt_tokens & _tokenize(item_prompt))
        scored.append((overlap, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for score, item in scored[:limit] if score > 0] or load_dataset()[:limit]


def build_few_shot_prompt(prompt: str) -> str:
    examples = select_examples(prompt)
    blocks: List[str] = []
    for example in examples:
        blocks.append(
            "Prompt: "
            + example["prompt"]
            + "\nJSON:\n"
            + json.dumps(example["objects"], indent=2)
        )
    examples_text = "\n\n".join(blocks)
    common_assets = ", ".join(sorted(supported_assets()))
    return (
        "You generate 3D scene graphs. Return only a JSON array.\n"
        "Each item must be an object with exactly these keys: "
        'name, position, rotation, scale.\n'
        "position must be [x, y, z], rotation must be [rx, ry, rz], scale must be [sx, sy, sz].\n"
        "Keep Y near 0 for grounded scenes. Keep positions compact and non-overlapping.\n"
        "Use concise noun-like object names.\n"
        f"If the prompt asks for something outside the common library, introduce new object names instead of forcing them into unrelated furniture.\n"
        f"Common reusable asset names already supported well: {common_assets}.\n\n"
        f"{examples_text}\n\n"
        f"Prompt: {prompt}\nJSON:\n"
    )


def _extract_json_payload(text: str) -> str:
    array_start = text.find("[")
    object_start = text.find("{")
    if array_start == -1 and object_start == -1:
        raise ValueError("No JSON payload found in model response.")
    if array_start == -1 or (object_start != -1 and object_start < array_start):
        start = object_start
        end = text.rfind("}")
    else:
        start = array_start
        end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("Incomplete JSON payload in model response.")
    return text[start : end + 1]


def query_local_model(prompt: str, model: str = DEFAULT_MODEL, ollama_url: str = DEFAULT_OLLAMA_URL) -> List[Dict]:
    payload = {
        "model": model,
        "prompt": build_few_shot_prompt(prompt),
        "stream": False,
        "format": "json",
    }
    request = urllib.request.Request(
        ollama_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=90) as response:
        body = json.loads(response.read().decode("utf-8"))
    raw_response = body.get("response", "").strip()
    if not raw_response:
        raise ValueError("Ollama returned an empty response.")
    parsed = json.loads(_extract_json_payload(raw_response))
    if not isinstance(parsed, list):
        raise ValueError("Scene graph response must be a JSON array.")
    return parsed


def _scene_template_objects(scene_type: str) -> List[Dict]:
    templates = {
        "classroom": [
            {"name": "wooden_desk", "position": [-2.0, 0.0, 1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "wooden_desk", "position": [2.0, 0.0, 1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "chair", "position": [-2.0, 0.0, 2.7], "rotation": [0.0, 180.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "chair", "position": [2.0, 0.0, 2.7], "rotation": [0.0, 180.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "blackboard", "position": [0.0, 0.0, -5.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "bookshelf", "position": [-5.5, 0.0, -1.0], "rotation": [0.0, 90.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "lamp", "position": [5.0, 0.0, -1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ],
        "throne_room": [
            {"name": "throne", "position": [0.0, 0.0, -4.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "banner", "position": [-4.0, 0.0, -5.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "banner", "position": [4.0, 0.0, -5.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "torch", "position": [-5.5, 0.0, -2.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "torch", "position": [5.5, 0.0, -2.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "bench", "position": [-2.5, 0.0, 2.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "bench", "position": [2.5, 0.0, 2.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ],
        "forest_camp": [
            {"name": "campfire", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "pine_tree", "position": [-5.5, 0.0, -4.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "pine_tree", "position": [5.5, 0.0, -4.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "pine_tree", "position": [-6.0, 0.0, 4.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "barrel", "position": [-2.5, 0.0, 2.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "crate", "position": [3.5, 0.0, -1.5], "rotation": [0.0, 18.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "bench", "position": [-2.8, 0.0, 0.0], "rotation": [0.0, 90.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ],
        "market": [
            {"name": "market_stall", "position": [-3.5, 0.0, -1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "market_stall", "position": [3.5, 0.0, -1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "crate", "position": [-2.0, 0.0, 2.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "crate", "position": [2.0, 0.0, 2.5], "rotation": [0.0, 10.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "barrel", "position": [-4.5, 0.0, 2.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "barrel", "position": [4.5, 0.0, 2.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "lamp", "position": [0.0, 0.0, 4.8], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ],
        "tavern": [
            {"name": "table", "position": [-2.5, 0.0, 0.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "table", "position": [2.5, 0.0, 0.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "chair", "position": [-2.5, 0.0, 2.3], "rotation": [0.0, 180.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "chair", "position": [2.5, 0.0, 2.3], "rotation": [0.0, 180.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "barrel", "position": [-5.0, 0.0, -3.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "barrel", "position": [5.0, 0.0, -3.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "torch", "position": [0.0, 0.0, 4.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ],
        "solar_system": [
            {"name": "sun", "position": [-10.8, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "mercury", "position": [-8.4, 0.0, 0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "venus", "position": [-6.4, 0.0, -0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "earth", "position": [-4.2, 0.0, 0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "mars", "position": [-2.0, 0.0, -0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "jupiter", "position": [1.2, 0.0, 0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "saturn", "position": [4.7, 0.0, -0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "uranus", "position": [8.1, 0.0, 0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "neptune", "position": [11.1, 0.0, -0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ],
        "studio": [
            {"name": "table", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "chair", "position": [1.6, 0.0, 1.5], "rotation": [0.0, 180.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "lamp", "position": [-2.0, 0.0, 1.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "bookshelf", "position": [-3.5, 0.0, -2.0], "rotation": [0.0, 90.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ],
    }
    return [dict(item) for item in templates.get(scene_type, templates["studio"])]


def _normalize_entry(entry: Dict) -> Optional[Dict]:
    name = canonicalize_object_name(str(entry.get("name", "")))
    if not name:
        return None
    position = entry.get("position", [0.0, 0.0, 0.0])
    rotation = entry.get("rotation", [0.0, 0.0, 0.0])
    scale = entry.get("scale", [1.0, 1.0, 1.0])
    try:
        pos = [float(position[0]), float(position[1]), float(position[2])]
        rot = [float(rotation[0]), float(rotation[1]), float(rotation[2])]
        scl = [max(0.1, float(scale[0])), max(0.1, float(scale[1])), max(0.1, float(scale[2]))]
    except (TypeError, ValueError, IndexError):
        return None
    return {"name": name, "position": pos, "rotation": rot, "scale": scl}


def _apply_scene_constraints(scene: List[Dict]) -> List[Dict]:
    constrained: List[Dict] = []
    for item in scene:
        normalized = _normalize_entry(item)
        if not normalized:
            continue
        x, y, z = normalized["position"]
        x = max(-MAX_ABS_XZ, min(MAX_ABS_XZ, x))
        z = max(-MAX_ABS_XZ, min(MAX_ABS_XZ, z))
        y = max(-0.25, min(MAX_Y, y))
        normalized["position"] = [x, y, z]
        constrained.append(normalized)

    for i in range(len(constrained)):
        for j in range(i):
            ax, _, az = constrained[i]["position"]
            bx, _, bz = constrained[j]["position"]
            dx = ax - bx
            dz = az - bz
            distance = math.hypot(dx, dz)
            if 0.0 < distance < MIN_DISTANCE:
                push = (MIN_DISTANCE - distance) / 2.0
                nx = dx / distance
                nz = dz / distance
                constrained[i]["position"][0] += nx * push
                constrained[i]["position"][2] += nz * push
                constrained[j]["position"][0] -= nx * push
                constrained[j]["position"][2] -= nz * push
            elif distance == 0.0:
                constrained[i]["position"][0] += 0.8
                constrained[i]["position"][2] += 0.8

    for item in constrained:
        item["position"][0] = max(-MAX_ABS_XZ, min(MAX_ABS_XZ, item["position"][0]))
        item["position"][2] = max(-MAX_ABS_XZ, min(MAX_ABS_XZ, item["position"][2]))
        item["position"][1] = max(-0.25, min(MAX_Y, item["position"][1]))
    return constrained


def score_layout(scene: List[Dict]) -> float:
    if not scene:
        return 0.0
    score = 1.0
    for item in scene:
        _, y, _ = item["position"]
        score -= abs(y) * 0.05
    for i in range(len(scene)):
        for j in range(i):
            ax, _, az = scene[i]["position"]
            bx, _, bz = scene[j]["position"]
            if math.hypot(ax - bx, az - bz) < MIN_DISTANCE * 0.75:
                score -= 0.15
    return max(0.0, round(score, 3))


def classify_scene(prompt: str) -> tuple[str, str]:
    """
    Scene type plus a coarse pipeline label consumed by direct_usd_scene.py.

    ``direct_usd_scene`` forces ``deterministic`` when ``--mode rule``; otherwise
    it expects a non-deterministic label (here: ``generative``) for the AI path.
    """
    scene_type = detect_scene_type(prompt or "")
    return scene_type, "generative"


def is_valid_scene(scene: List[Dict]) -> bool:
    if not scene or not isinstance(scene, list):
        return False
    for item in scene:
        if not isinstance(item, dict):
            return False
        if "name" not in item or "position" not in item:
            return False
        pos = item["position"]
        if not isinstance(pos, (list, tuple)) or len(pos) < 3:
            return False
    return True


def generate_minimal_scene() -> List[Dict]:
    """Tiny safe layout when rule/AI outputs are unusable."""
    return _apply_scene_constraints(_scene_template_objects("studio"))


def generate_solar_system_scene() -> tuple[List[Dict], List[tuple[str, str, str]]]:
    """
    Deterministic solar system template plus simple ``orbits`` edges for the graph.
    """
    scene = _apply_scene_constraints(_scene_template_objects("solar_system"))
    relations: List[tuple[str, str, str]] = []
    sun_name = canonicalize_object_name("sun")
    for item in scene:
        name = str(item.get("name", "")).strip()
        if not name or canonicalize_object_name(name) == sun_name:
            continue
        relations.append((canonicalize_object_name(name), "orbits", sun_name))
    return scene, relations


def generate_rule_scene(prompt: str) -> List[Dict]:
    scene_type = detect_scene_type(prompt)
    return _apply_scene_constraints(_scene_template_objects(scene_type))


def generate_scene(prompt: str, mode: str = "ai") -> List[Dict]:
    """
    Generate a structured scene graph.

    `mode="ai"` prefers Ollama JSON generation with deterministic constraints.
    `mode="rule"` skips the model and uses the deterministic template directly.
    """
    scene_type = detect_scene_type(prompt)

    # Solar-system prompts need deterministic ordering and planet-specific assets,
    # so we bypass the generic indoor-scene LLM prompt path entirely here.
    if scene_type == "solar_system":
        scene = generate_rule_scene(prompt)
        print(f"[INFO] Scene graph mode: rule-solar-system")
        print(f"[INFO] Layout score: {score_layout(scene)}")
        print(f"[DEBUG] Scene graph: {json.dumps(scene)}")
        return scene

    if mode == "rule":
        scene = generate_rule_scene(prompt)
        print(f"[INFO] Scene graph mode: rule")
        print(f"[INFO] Layout score: {score_layout(scene)}")
        print(f"[DEBUG] Scene graph: {json.dumps(scene)}")
        return scene

    try:
        raw_scene = query_local_model(prompt)
        scene = _apply_scene_constraints(raw_scene)
        if not scene:
            raise ValueError("AI scene graph was empty after normalization.")
        print(f"[INFO] Scene graph mode: ai")
        print(f"[INFO] Layout score: {score_layout(scene)}")
        print(f"[DEBUG] Scene graph: {json.dumps(scene)}")
        return scene
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"[WARN] AI scene graph generation failed: {exc}")
        scene = generate_rule_scene(prompt)
        print(f"[INFO] Scene graph mode: rule-fallback")
        print(f"[INFO] Layout score: {score_layout(scene)}")
        print(f"[DEBUG] Scene graph: {json.dumps(scene)}")
        return scene

def build_graph(scene_objects, relations):
    graph = {
        "nodes": [],
        "edges": []
    }

    name_to_obj = {}

    # Add nodes
    for obj in scene_objects:
        graph["nodes"].append(obj)
        name_to_obj[obj["name"]] = obj

    # Add edges
    for (obj1, rel, obj2) in relations:
        if obj1 in name_to_obj and obj2 in name_to_obj:
            graph["edges"].append({
                "from": obj1,
                "relation": rel,
                "to": obj2
            })

    graph["lookup"] = name_to_obj

    return graph

def training_stub() -> Dict[str, str]:
    """
    Placeholder for optional fine-tuning.

    The project remains locally runnable without training. This stub documents
    the intended hook for a small local model fine-tune or adapter workflow.
    """
    return {
        "status": "stub",
        "message": "Provide a local LoRA/fine-tune pipeline here if you later choose to train a small model on scene_dataset.json.",
    }
