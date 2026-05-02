"""Scene generation orchestration that preserves legacy behavior."""

from __future__ import annotations

import json
import math
import re
from typing import Dict, List, Optional

from sceneforge.asset_registry import find_asset
from sceneforge.layout import apply_relation_constraints, ensure_lookup, prevent_overlaps
from sceneforge.logging_utils import get_logger, pipeline_span
from sceneforge.models import SceneClassification
from sceneforge.relations import infer_relations, legacy_relation_tuples, parse_relations, validate_relations
from sceneforge.scene_understanding import classify_scene


LOGGER = get_logger(__name__)
MAX_ABS_XZ = 12.0
MAX_Y = 1.5
MIN_DISTANCE = 1.6


def supported_assets() -> set[str]:
    """Backward-compatible supported asset names."""

    return {
        "wooden_desk",
        "table",
        "chair",
        "basketball",
        "basketball_hoop",
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
    """Normalize object names while avoiding unrelated substitutions."""

    import re

    key = re.sub(r"[^a-z0-9]+", "_", (name or "").lower()).strip("_")
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
        "water_feature": "fountain",
        "exit": "door",
        "doorway": "door",
        "egress": "door",
    }
    return synonyms.get(key, key)


def load_dataset(dataset_path=None) -> List[Dict]:
    """Load few-shot examples from the project dataset."""

    from sceneforge.config import get_config

    path = dataset_path or get_config().dataset_path
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, list) else []


def _tokenize(text: str) -> set[str]:
    import re

    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def select_examples(prompt: str, limit: int = 2) -> List[Dict]:
    """Pick relevant few-shot examples based on token overlap."""

    prompt_tokens = _tokenize(prompt)
    scored = []
    for item in load_dataset():
        item_prompt = str(item.get("prompt", ""))
        overlap = len(prompt_tokens & _tokenize(item_prompt))
        scored.append((overlap, item))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return [item for score, item in scored[:limit] if score > 0] or load_dataset()[:limit]


def build_few_shot_prompt(prompt: str) -> str:
    """Construct the scene-graph prompt used for Ollama generation."""

    examples = select_examples(prompt)
    blocks: List[str] = []
    for example in examples:
        blocks.append(
            "Prompt: "
            + str(example["prompt"])
            + "\nJSON:\n"
            + json.dumps(example["objects"], indent=2)
        )
    common_assets = ", ".join(sorted(supported_assets()))
    core = (
        "You generate 3D scene graphs. Return only a JSON array.\n"
        "Each item must be an object with exactly these keys: name, position, rotation, scale.\n"
        "position must be [x, y, z], rotation must be [rx, ry, rz], scale must be [sx, sy, sz].\n"
        "Keep Y near 0 for grounded scenes. Keep positions compact and non-overlapping.\n"
        "Use concise noun-like object names.\n"
        "If the prompt asks for something outside the common library, introduce new object names instead of forcing them into unrelated furniture.\n"
        f"Common reusable asset names already supported well: {common_assets}.\n\n"
        + "\n\n".join(blocks)
        + f"\n\nPrompt: {prompt}\nJSON:\n"
    )
    try:
        from sceneforge.rag import rag_globally_disabled, retrieved_context_block

        if not rag_globally_disabled():
            ctx = retrieved_context_block(prompt).strip()
            if ctx:
                return ctx + "\n\n" + core
    except Exception as exc:
        LOGGER.debug("RAG augment skipped for scene prompt: %s", exc)
    return core


def _scene_template_objects(scene_type: str) -> List[Dict]:
    """Return deterministic template objects for known scene families."""

    from ai_scene_graph import _scene_template_objects as legacy_templates

    return legacy_templates(scene_type)


def _normalize_entry(entry: Dict) -> Optional[Dict]:
    """Normalize an object dictionary into the legacy scene format."""

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
    """Clamp coordinates and enforce basic spacing."""

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

    graph = {"nodes": constrained}
    prevent_overlaps(graph, min_spacing=MIN_DISTANCE)
    return constrained


def score_layout(scene: List[Dict]) -> float:
    """Return a coarse quality score for spacing and grounding."""

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


def classify_scene_legacy(prompt: str) -> tuple[str, str]:
    """Compatibility bridge for direct_usd_scene."""

    result = classify_scene(prompt)
    return result.scene_type, result.mode_label


def is_valid_scene(scene: List[Dict]) -> bool:
    """Check the minimum contract used throughout the existing pipeline."""

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
    """Tiny safe fallback layout."""

    return _apply_scene_constraints(_scene_template_objects("studio"))


def _meaningful_prompt_tokens(prompt: str) -> List[str]:
    stop_words = {
        "a", "an", "the", "with", "and", "or", "in", "on", "under", "inside", "near",
        "beside", "aligned", "facing", "scene", "generate", "create", "make", "show",
        "for", "to", "of", "at", "by", "from", "into", "outdoor", "indoor",
    }
    raw_tokens = re.findall(r"[a-z][a-z0-9_-]+", (prompt or "").lower())
    tokens = [token for token in raw_tokens if token not in stop_words and len(token) > 2]
    return tokens


def _canonical_prompt_objects(prompt: str, limit: int = 8) -> List[str]:
    scene_words = {
        "classroom", "court", "room", "hall", "studio", "market", "forest", "camp",
        "garden", "courtyard", "tavern", "solar", "system",
    }
    ordered: List[str] = []
    phrase_matches = re.findall(r"(?:a|an|the)\s+([a-z][a-z0-9_-]*(?:\s+[a-z][a-z0-9_-]*){0,2})", (prompt or "").lower())
    for phrase in phrase_matches:
        canonical = canonicalize_object_name(phrase)
        if canonical and canonical not in ordered and canonical not in scene_words:
            ordered.append(canonical)
    for chunk in re.split(r",|\band\b|\bwith\b", (prompt or "").lower()):
        words = [word for word in re.findall(r"[a-z][a-z0-9_-]*", chunk) if word not in {"a", "an", "the"}]
        if 1 <= len(words) <= 3:
            canonical = canonicalize_object_name(" ".join(words))
            if canonical and canonical not in ordered and canonical not in scene_words:
                ordered.append(canonical)
    for token in _meaningful_prompt_tokens(prompt):
        canonical = canonicalize_object_name(token)
        if canonical and canonical not in ordered and canonical not in scene_words:
            ordered.append(canonical)
    return ordered[:limit]


def _layout_prompt_objects(object_names: List[str]) -> List[Dict]:
    if not object_names:
        return []
    nodes: List[Dict] = []
    radius = max(2.5, min(8.0, 1.2 * len(object_names)))
    for index, name in enumerate(object_names):
        angle = (math.tau * index) / max(1, len(object_names))
        nodes.append(
            {
                "name": name,
                "position": [round(math.cos(angle) * radius, 3), 0.0, round(math.sin(angle) * radius, 3)],
                "rotation": [0.0, round((math.degrees(angle) + 180.0) % 360.0, 3), 0.0],
                "scale": [1.0, 1.0, 1.0],
            }
        )
    return nodes


def generate_prompt_driven_scene(prompt: str) -> List[Dict]:
    """Create a generic placeholder-friendly layout from arbitrary prompt objects."""

    objects = _canonical_prompt_objects(prompt)
    if not objects:
        return []
    return _apply_scene_constraints(_layout_prompt_objects(objects))


def generate_solar_system_scene() -> tuple[List[Dict], List[tuple[str, str, str]]]:
    """Deterministic solar system scene plus orbit relations."""

    scene = _apply_scene_constraints(_scene_template_objects("solar_system"))
    relations = legacy_relation_tuples(infer_relations("solar system"))
    return scene, relations


def generate_rule_scene(prompt: str) -> List[Dict]:
    """Generate a deterministic scene from the detected family."""

    scene_type = classify_scene(prompt, prefer_llm=False).scene_type
    if scene_type == "studio":
        generic_scene = generate_prompt_driven_scene(prompt)
        if generic_scene:
            return generic_scene
    return _apply_scene_constraints(_scene_template_objects(scene_type))


def query_local_model(prompt: str, model: str | None = None, ollama_url: str | None = None) -> List[Dict]:
    """Backward-compatible LLM query wrapper."""

    from sceneforge.llm import query_scene_llm

    result = query_scene_llm(build_few_shot_prompt(prompt))
    return [item.model_dump() for item in result.objects]


def generate_scene(prompt: str, mode: str = "ai") -> List[Dict]:
    """Generate a structured scene graph with robust LLM fallback."""

    classification = classify_scene(prompt)
    if classification.scene_type == "solar_system":
        scene = generate_rule_scene(prompt)
        LOGGER.info("Scene graph mode: rule-solar-system")
        LOGGER.info("Layout score: %s", score_layout(scene))
        LOGGER.debug("Scene graph: %s", json.dumps(scene))
        return scene

    if mode == "rule":
        scene = generate_rule_scene(prompt)
        LOGGER.info("Scene graph mode: rule")
        LOGGER.info("Layout score: %s", score_layout(scene))
        LOGGER.debug("Scene graph: %s", json.dumps(scene))
        return scene

    try:
        raw_scene = query_local_model(prompt)
        scene = _apply_scene_constraints(raw_scene)
        if not scene:
            raise ValueError("AI scene graph was empty after normalization.")
        LOGGER.info("Scene graph mode: ai")
        LOGGER.info("Layout score: %s", score_layout(scene))
        LOGGER.debug("Scene graph: %s", json.dumps(scene))
        return scene
    except Exception as exc:
        LOGGER.warning("AI scene graph generation failed: %s", exc)
        scene = generate_rule_scene(prompt)
        LOGGER.info("Scene graph mode: rule-fallback")
        LOGGER.info("Layout score: %s", score_layout(scene))
        LOGGER.debug("Scene graph: %s", json.dumps(scene))
        return scene


def build_graph(scene_objects: List[Dict], relations: List[tuple[str, str, str]]) -> Dict:
    """Construct the legacy graph structure."""

    graph = {"nodes": [], "edges": []}
    name_to_obj = {}
    for obj in scene_objects:
        graph["nodes"].append(obj)
        name_to_obj[obj["name"]] = obj
    for obj1, rel, obj2 in relations:
        if obj1 in name_to_obj and obj2 in name_to_obj:
            graph["edges"].append({"from": obj1, "relation": rel, "to": obj2})
    graph["lookup"] = name_to_obj
    return graph


def enrich_graph_with_relations(graph: Dict, prompt: str, seed_relations: Optional[List[tuple[str, str, str]]] = None) -> Dict:
    """Parse, validate, and apply relation constraints to a graph."""

    object_names = [str(node.get("name", "")) for node in graph.get("nodes", [])]
    structured = list(parse_relations(prompt))
    if not structured:
        structured = list(infer_relations(prompt))
    if seed_relations:
        structured.extend(
            validate_relations(
                [
                    type("SeedRelation", (), {"source": src, "relation": rel, "target": dst})()  # type: ignore[misc]
                    for src, rel, dst in seed_relations
                ],
                object_names,
            )
        )
    structured = validate_relations(structured, object_names)
    for relation in structured:
        edge = {"from": relation.source, "relation": relation.relation, "to": relation.target}
        if edge not in graph.get("edges", []):
            graph.setdefault("edges", []).append(edge)
    apply_relation_constraints(graph, structured)
    prevent_overlaps(graph, min_spacing=1.0)
    ensure_lookup(graph)
    return graph


def training_stub() -> Dict[str, str]:
    """Placeholder for future training/fine-tuning work."""

    return {
        "status": "stub",
        "message": "Provide a local LoRA/fine-tune pipeline here if you later choose to train a small model on scene_dataset.json.",
    }
