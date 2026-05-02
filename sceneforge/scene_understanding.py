"""Hybrid scene understanding with deterministic fallback."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Dict, List

from sceneforge.config import get_config, resolve_ollama_model
from sceneforge.logging_utils import get_logger
from sceneforge.models import SceneClassification


LOGGER = get_logger(__name__)
SCENE_TYPES = (
    "courtyard",
    "classroom",
    "basketball_court",
    "throne_room",
    "forest_camp",
    "market",
    "tavern",
    "solar_system",
    "studio",
)


KEYWORD_SCENE_RULES: Dict[str, tuple[str, ...]] = {
    "courtyard": ("courtyard", "patio", "plaza", "atrium", "quad", "garden", "park"),
    "classroom": ("classroom", "school", "lecture", "teacher", "desk", "student"),
    "basketball_court": ("basketball", "basketball court", "court", "hoop", "backboard", "half court"),
    "throne_room": ("throne", "castle", "royal", "king", "queen", "hall"),
    "forest_camp": ("forest", "camp", "campfire", "woods", "clearing"),
    "market": ("market", "bazaar", "vendor", "stall"),
    "tavern": ("tavern", "inn", "pub"),
    "solar_system": (
        "solar system",
        "planetary system",
        "planets orbiting",
        "planets around the sun",
        "sun and planets",
    ),
    "studio": ("studio", "indoor studio", "library", "reading room", "book room"),
}


def detect_scene_type(prompt: str) -> str:
    """Backward-compatible deterministic scene type detection."""

    return classify_scene(prompt).scene_type


def _keyword_classification(prompt: str) -> SceneClassification:
    text = (prompt or "").lower()
    for scene_type, phrases in KEYWORD_SCENE_RULES.items():
        if any(phrase in text for phrase in phrases):
            return SceneClassification(
                scene_type=scene_type,
                confidence=0.72,
                source="rules",
                reasoning=f"Matched keywords for {scene_type}.",
            )
    return SceneClassification(
        scene_type="studio",
        confidence=0.35,
        source="rules",
        reasoning="No stronger scene-family keywords matched.",
    )


def _extract_json_object(raw: str) -> dict:
    start = raw.find("{")
    end = raw.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in classifier response.")
    return json.loads(raw[start : end + 1])


def _llm_classification(prompt: str) -> SceneClassification | None:
    config = get_config()
    resolved_model = resolve_ollama_model(
        config.scene_graph_model,
        config.ollama_base_url,
        timeout_s=min(config.llm_timeout_seconds, 8.0),
    )
    prompt_text = (
        "Classify the scene prompt into exactly one scene type from this list: "
        + ", ".join(SCENE_TYPES)
        + '. Return JSON with keys: scene_type, confidence, reasoning.\nPrompt: '
        + prompt
    )
    profiles = [
        {
            "model": resolved_model,
            "stream": False,
            "format": "json",
            "prompt": prompt_text,
            "options": {
                "temperature": 0.1,
                "num_predict": min(config.llm_max_predict, 96),
                "num_ctx": min(config.llm_num_ctx, 1024),
            },
        },
        {
            "model": resolved_model,
            "stream": False,
            "format": "json",
            "prompt": prompt_text,
            "options": {
                "temperature": 0.0,
                "num_predict": min(config.llm_max_predict, 64),
                "num_ctx": min(config.llm_num_ctx, 768),
            },
        },
    ]
    for profile in profiles:
        request = urllib.request.Request(
            config.ollama_generate_url,
            data=json.dumps(profile).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=config.llm_timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
            parsed = _extract_json_object(str(body.get("response", "")).strip())
            scene_type = str(parsed.get("scene_type", "")).strip().lower()
            if scene_type not in SCENE_TYPES:
                continue
            confidence = float(parsed.get("confidence", 0.0))
            return SceneClassification(
                scene_type=scene_type,
                confidence=max(0.0, min(1.0, confidence)),
                source="llm",
                reasoning=str(parsed.get("reasoning", "")).strip() or None,
            )
        except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as exc:
            LOGGER.warning(
                "Scene classification fallback attempt failed for model=%s num_ctx=%s num_predict=%s: %s",
                profile.get("model"),
                profile["options"].get("num_ctx"),
                profile["options"].get("num_predict"),
                exc,
            )
    return None


def classify_scene(prompt: str, prefer_llm: bool = True) -> SceneClassification:
    """Hybrid classification with a safe rules fallback."""

    rule_result = _keyword_classification(prompt)
    if not prefer_llm or rule_result.confidence >= 0.7:
        return rule_result

    llm_result = _llm_classification(prompt)
    if llm_result and llm_result.confidence >= 0.45:
        return llm_result
    return rule_result


def classify_scene_legacy(prompt: str) -> tuple[str, str]:
    """Compatibility helper for legacy callers."""

    result = classify_scene(prompt)
    return result.scene_type, result.mode_label
