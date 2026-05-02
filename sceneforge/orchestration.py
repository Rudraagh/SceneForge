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
FAMILY_MINIMUM_COUNTS: Dict[str, Dict[str, int]] = {
    "classroom": {"desk": 2, "chair": 2, "board": 1},
    "throne_room": {"throne": 1, "banner": 2, "torch": 2, "bench": 2},
    "market": {"market_stall": 2, "crate": 2, "barrel": 2},
    "tavern": {"table": 2, "chair": 2},
    "basketball_court": {"basketball_hoop": 2, "bench": 2},
}
SCALE_HINT_WORDS = {
    "tiny": 0.55,
    "small": 0.75,
    "short": 0.8,
    "modest": 0.9,
    "medium": 1.0,
    "large": 1.2,
    "big": 1.25,
    "tall": 1.25,
    "huge": 1.45,
    "massive": 1.6,
    "giant": 1.75,
    "oversized": 1.5,
}


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
    if key.endswith("ies") and len(key) > 4:
        key = key[:-3] + "y"
    elif key.endswith(("ches", "shes", "xes", "zes", "ses", "oes")) and len(key) > 4:
        key = key[:-2]
    elif key.endswith("s") and len(key) > 3 and not key.endswith(("ss", "us")):
        key = key[:-1]
    synonyms = {
        "desk": "wooden_desk",
        "school_desk": "wooden_desk",
        "teacher_desk": "wooden_desk",
        "seat": "chair",
        "student_seat": "chair",
        "stool": "chair",
        "bench": "bench",
        "benche": "bench",
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
    prompt_text = (prompt or "").lower()
    if any(token in prompt_text for token in ("classroom", "school", "lecture", "teacher", "student")):
        layout_hint = (
            "For classrooms: choose a front teaching wall, arrange desks in rows, and place chairs aligned with desks.\n"
        )
    elif any(token in prompt_text for token in ("throne room", "royal", "throne", "castle", "king", "queen")):
        layout_hint = (
            "For throne rooms: center the throne on the far side, place banners and torches symmetrically around it, and place benches along the sides/front.\n"
        )
    elif any(token in prompt_text for token in ("solar system", "planetary system", "sun and planets", "orbiting planets", "planets orbiting")):
        layout_hint = (
            "For solar systems: center the sun, place planets on increasing orbit radii around it, keep those radii clearly separated, and avoid polygonal clutter near the center.\n"
        )
    else:
        layout_hint = (
            "For all other scenes: choose one focal object, place wall-supporting objects near the perimeter, keep seating or paired objects aligned with the focal area, and avoid random diagonal scatter.\n"
        )
    core = (
        "You generate 3D scene graphs. Return only a JSON array.\n"
        + "Think through the spatial arrangement internally before writing coordinates, then output only the final JSON.\n"
        + "Each item must be an object with exactly these keys: name, position, rotation, scale.\n"
        + "position must be [x, y, z], rotation must be [rx, ry, rz], scale must be [sx, sy, sz].\n"
        + "Keep Y near 0 for grounded scenes. Keep positions compact and non-overlapping.\n"
        + "Prefer coherent room structure: identify a front wall, center focal objects, keep pairs symmetric, and avoid random diagonal scatter.\n"
        + layout_hint
        + "Use concise noun-like object names.\n"
        + "Do not use container names like classroom, room, scene, environment, or world as objects.\n"
        + "If the prompt asks for something outside the common library, introduce new object names instead of forcing them into unrelated furniture.\n"
        + f"Common reusable asset names already supported well: {common_assets}.\n\n"
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


def _resolve_scale_hint_targets(raw_target: str) -> set[str]:
    cleaned = re.split(r"\b(?:and|with|near|beside|inside|on|under)\b|,", str(raw_target or ""), maxsplit=1)[0].strip()
    canonical = canonicalize_object_name(cleaned)
    targets = {canonical} if canonical else set()
    normalized = cleaned.lower().strip()
    singular = normalized[:-1] if normalized.endswith("s") else normalized
    for candidate in filter(None, {normalized, singular}):
        targets.add(canonicalize_object_name(candidate))
    return {target for target in targets if target}


def _prompt_scale_hints(prompt: str) -> Dict[str, float]:
    text = (prompt or "").lower()
    hints: Dict[str, float] = {}
    target_phrase = r"[a-z][a-z0-9_-]*(?:\s+(?!and\b|with\b|near\b|beside\b|inside\b|on\b|under\b)[a-z][a-z0-9_-]*){0,2}"
    adjective_pattern = re.compile(
        r"\b("
        + "|".join(sorted(SCALE_HINT_WORDS, key=len, reverse=True))
        + r")\s+("
        + target_phrase
        + r")"
    )
    predicate_pattern = re.compile(
        r"\b("
        + target_phrase
        + r")\s+(?:is|are)\s+("
        + "|".join(sorted(SCALE_HINT_WORDS, key=len, reverse=True))
        + r")\b"
    )
    for match in adjective_pattern.finditer(text):
        scale_word = match.group(1)
        for target in _resolve_scale_hint_targets(match.group(2)):
            hints[target] = SCALE_HINT_WORDS[scale_word]
    for match in predicate_pattern.finditer(text):
        scale_word = match.group(2)
        for target in _resolve_scale_hint_targets(match.group(1)):
            hints[target] = SCALE_HINT_WORDS[scale_word]
    return hints


def _apply_prompt_scale_hints(scene: List[Dict], prompt: str) -> List[Dict]:
    hints = _prompt_scale_hints(prompt)
    if not hints:
        return scene

    scaled_scene: List[Dict] = []
    for item in scene:
        updated = dict(item)
        name = canonicalize_object_name(str(updated.get("name", "")))
        factor = hints.get(name)
        if factor is not None:
            scale = list(updated.get("scale", [1.0, 1.0, 1.0]))
            updated["scale"] = [
                round(max(0.1, float(scale[0]) * factor), 4),
                round(max(0.1, float(scale[1]) * factor), 4),
                round(max(0.1, float(scale[2]) * factor), 4),
            ]
        scaled_scene.append(updated)
    return scaled_scene


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


def _prompt_object_specs(prompt: str, limit: int = 8) -> List[Dict[str, int | str]]:
    stop_words = {
        "a", "an", "the", "with", "and", "or", "in", "on", "under", "inside", "near",
        "beside", "aligned", "facing", "scene", "generate", "create", "make", "show",
        "for", "to", "of", "at", "by", "from", "into", "outdoor", "indoor", "central",
        "eastern", "western", "northern", "southern", "edge", "along",
    }
    specs: List[Dict[str, int | str]] = []
    seen_names: set[str] = set()

    def _add_spec(raw_phrase: str) -> None:
        words = [word for word in re.findall(r"[a-z][a-z0-9_-]*", raw_phrase.lower()) if word not in stop_words]
        if not words:
            return
        count = 2 if words[-1].endswith("s") and len(words[-1]) > 3 else 1
        candidates = []
        for size in (3, 2, 1):
            candidate_words = words[-size:]
            if candidate_words:
                candidates.append(" ".join(candidate_words))
        normalized_candidates = []
        blocked = {"room", "scene", "environment", "world", "courtyard", "garden", "market", "forest", "camp", "studio", "hall"}
        asset_names = supported_assets()
        for candidate in candidates:
            normalized = canonicalize_object_name(candidate)
            if normalized and normalized not in blocked:
                normalized_candidates.append((candidate, normalized))
        canonical = ""
        for _candidate, normalized in reversed(normalized_candidates):
            if normalized in asset_names:
                canonical = normalized
                break
        if not canonical and normalized_candidates:
            canonical = normalized_candidates[0][1]
        if not canonical or canonical in seen_names:
            return
        specs.append({"name": canonical, "count": min(2, count)})
        seen_names.add(canonical)

    phrase_matches = re.findall(
        r"(?:a|an|the)\s+([a-z][a-z0-9_-]*(?:\s+[a-z][a-z0-9_-]*){0,5})",
        (prompt or "").lower(),
    )
    for phrase in phrase_matches:
        _add_spec(re.split(r"\b(?:with|and|near|beside|inside|on|under|along)\b", phrase, maxsplit=1)[0])
    for chunk in re.split(r",|\band\b|\bwith\b", (prompt or "").lower()):
        _add_spec(chunk)
    return specs[:limit]


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

    specs = _prompt_object_specs(prompt)
    objects: List[str] = []
    for spec in specs:
        objects.extend([str(spec["name"])] * int(spec["count"]))
    if not objects:
        objects = _canonical_prompt_objects(prompt)
    if not objects:
        return []
    return _apply_scene_constraints(_apply_prompt_scale_hints(_layout_prompt_objects(objects), prompt))


def generate_solar_system_scene() -> tuple[List[Dict], List[tuple[str, str, str]]]:
    """Deterministic solar system scene plus orbit relations."""

    scene = _apply_scene_constraints(_scene_template_objects("solar_system"))
    relations = legacy_relation_tuples(infer_relations("solar system"))
    return scene, relations


def generate_rule_scene(prompt: str) -> List[Dict]:
    """Generate a deterministic scene from the detected family."""

    scene_type = classify_scene(prompt, prefer_llm=False).scene_type
    if scene_type == "solar_system":
        scene = _scene_template_objects(scene_type)
        scene = _apply_prompt_scale_hints(scene, prompt)
        return _apply_scene_constraints(scene)
    if scene_type not in FAMILY_MINIMUM_COUNTS:
        generic_scene = generate_prompt_driven_scene(prompt)
        if generic_scene:
            return generic_scene
    scene = _scene_template_objects(scene_type)
    scene = _apply_prompt_scale_hints(scene, prompt)
    return _apply_scene_constraints(scene)


def _count_named(scene: List[Dict], token: str) -> int:
    return sum(1 for item in scene if token in _base_object_name(str(item.get("name", ""))))


def _base_object_name(name: str) -> str:
    return re.sub(r"_\d+$", "", str(name or "").lower())


def _scene_meets_family_expectations(scene: List[Dict], scene_type: str) -> bool:
    minimums = FAMILY_MINIMUM_COUNTS.get(scene_type)
    if minimums:
        return all(_count_named(scene, token) >= minimum for token, minimum in minimums.items())
    return bool(scene)


def _scene_meets_prompt_expectations(scene: List[Dict], prompt: str) -> bool:
    specs = _prompt_object_specs(prompt)
    if not specs:
        return bool(scene)
    return all(_count_named(scene, str(spec["name"])) >= int(spec["count"]) for spec in specs)


def _augment_scene_for_family(scene: List[Dict], prompt: str, scene_type: str) -> List[Dict]:
    minimums = FAMILY_MINIMUM_COUNTS.get(scene_type)
    if not minimums:
        return scene

    enriched = [dict(item) for item in scene]
    template = generate_rule_scene(prompt)
    if _scene_meets_family_expectations(enriched, scene_type):
        return enriched

    existing_names = [_base_object_name(str(item.get("name", ""))) for item in enriched]
    outstanding = {
        token: max(0, minimum - _count_named(enriched, token))
        for token, minimum in minimums.items()
    }

    for candidate in template:
        name = _base_object_name(str(candidate.get("name", "")).lower())
        matched_requirement = False
        for token, remaining in outstanding.items():
            if remaining and token in name:
                enriched.append(dict(candidate))
                outstanding[token] -= 1
                matched_requirement = True
                break
        if matched_requirement:
            continue
        if len(enriched) < 5 and name not in existing_names:
            enriched.append(dict(candidate))
            existing_names.append(name)

    min_scene_size = max(5, sum(minimums.values()))
    if len(enriched) < min_scene_size:
        for candidate in template:
            if len(enriched) >= min_scene_size:
                break
            enriched.append(dict(candidate))

    return _apply_scene_constraints(enriched)


def _augment_scene_for_prompt(scene: List[Dict], prompt: str) -> List[Dict]:
    specs = _prompt_object_specs(prompt)
    if not specs:
        return scene

    enriched = [dict(item) for item in scene]
    template = generate_prompt_driven_scene(prompt)
    if _scene_meets_prompt_expectations(enriched, prompt):
        return enriched

    outstanding = {
        str(spec["name"]): max(0, int(spec["count"]) - _count_named(enriched, str(spec["name"])))
        for spec in specs
    }

    for candidate in template:
        name = _base_object_name(str(candidate.get("name", "")))
        if outstanding.get(name, 0) > 0:
            enriched.append(dict(candidate))
            outstanding[name] -= 1

    if len(enriched) < max(3, len(specs)):
        for candidate in template:
            if len(enriched) >= max(3, len(specs)):
                break
            enriched.append(dict(candidate))

    return _apply_scene_constraints(enriched)


def query_local_model(prompt: str, model: str | None = None, ollama_url: str | None = None) -> List[Dict]:
    """Backward-compatible LLM query wrapper."""

    from sceneforge.llm import query_scene_llm

    result = query_scene_llm(build_few_shot_prompt(prompt))
    return [item.model_dump() for item in result.objects]


def generate_scene(prompt: str, mode: str = "ai") -> List[Dict]:
    """Generate a structured scene graph with robust LLM fallback."""

    classification = classify_scene(prompt)
    fallback_family = classify_scene(prompt, prefer_llm=False).scene_type
    target_family = classification.scene_type if classification.scene_type in FAMILY_MINIMUM_COUNTS else fallback_family
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
        scene = _augment_scene_for_family(scene, prompt, target_family)
        scene = _augment_scene_for_prompt(scene, prompt)
        if not _scene_meets_family_expectations(scene, target_family):
            raise ValueError(f"AI scene graph incomplete for {target_family}.")
        if not _scene_meets_prompt_expectations(scene, prompt):
            raise ValueError("AI scene graph incomplete for requested prompt objects.")
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
    counts: Dict[str, int] = {}
    name_map: Dict[str, List[str]] = {}
    for obj in scene_objects:
        copied = dict(obj)
        copied["position"] = list(copied.get("position", [0.0, 0.0, 0.0]))
        copied["rotation"] = list(copied.get("rotation", [0.0, 0.0, 0.0]))
        copied["scale"] = list(copied.get("scale", [1.0, 1.0, 1.0]))
        base_name = str(copied.get("name", "")).strip()
        counts[base_name] = counts.get(base_name, 0) + 1
        unique_name = base_name if counts[base_name] == 1 and sum(1 for item in scene_objects if str(item.get("name", "")).strip() == base_name) == 1 else f"{base_name}_{counts[base_name]}"
        copied["name"] = unique_name
        copied["base_name"] = base_name
        graph["nodes"].append(copied)
        name_to_obj[unique_name] = copied
        name_map.setdefault(base_name, []).append(unique_name)
    for obj1, rel, obj2 in relations:
        source_candidates = name_map.get(obj1, [obj1])
        target_candidates = name_map.get(obj2, [obj2])
        if source_candidates and target_candidates:
            graph["edges"].append({"from": source_candidates[0], "relation": rel, "to": target_candidates[0]})
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
