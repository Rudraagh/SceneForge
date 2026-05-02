"""Robust LLM scene generation utilities with validation and repair."""

from __future__ import annotations

import json
import ast
import re
import urllib.error
import urllib.request
from typing import Dict, List

from sceneforge.config import get_config, resolve_ollama_model
from sceneforge.logging_utils import get_logger
from sceneforge.models import LLMSceneResult, SceneObjectModel, ValidationError


LOGGER = get_logger(__name__)


def _extract_scene_request(prompt: str) -> str:
    matches = re.findall(r"Prompt:\s*(.*?)\s*JSON:", prompt or "", flags=re.DOTALL | re.IGNORECASE)
    if matches:
        return matches[-1].strip()
    return str(prompt or "").strip()


def _family_count_hint(scene_prompt: str) -> str:
    text = (scene_prompt or "").lower()
    if any(token in text for token in ("classroom", "school", "lecture", "teacher", "student")):
        return "Include at least 2 wooden_desk, 2 chair, and 1 blackboard objects."
    if any(token in text for token in ("throne room", "royal", "throne", "castle", "king", "queen")):
        return "Include at least 1 throne, 2 banner, 2 torch, and 2 bench objects."
    if any(token in text for token in ("solar system", "planetary system", "sun and planets", "orbiting planets", "planets orbiting")):
        return "Include 1 sun and multiple planets. Put the sun near the center and place planets on clearly separated orbit radii around it."
    if any(token in text for token in ("market", "bazaar", "vendor", "stall")):
        return "Include at least 2 market_stall objects plus supporting crate or barrel objects."
    if any(token in text for token in ("basketball", "court", "hoop")):
        return "Include 2 basketball_hoop objects and supporting bench or lamp objects."
    if any(token in text for token in ("forest", "camp", "campfire", "woods")):
        return "Include a central campfire and surrounding pine_tree objects."
    return "Include 5 to 8 grounded objects when the prompt suggests a room or environment."


def _layout_reasoning_hint(scene_prompt: str) -> str:
    text = (scene_prompt or "").lower()
    if any(token in text for token in ("classroom", "school", "lecture", "teacher", "student")):
        return (
            "Reason about the layout before coordinates: put the teaching surface on a front wall, "
            "arrange desks in rows, and place chairs aligned with nearby desks."
        )
    if any(token in text for token in ("throne room", "royal", "throne", "castle", "king", "queen")):
        return (
            "Reason about the layout before coordinates: use a centered focal throne, keep ceremonial pairs symmetric, "
            "and place secondary seating along the sides or front."
        )
    if any(token in text for token in ("solar system", "planetary system", "sun and planets", "orbiting planets", "planets orbiting")):
        return (
            "Reason about the layout before coordinates: keep the sun at the center and distribute planets on increasing "
            "orbital radii with clear separation."
        )
    return (
        "Reason about the layout before coordinates: choose one focal object, place wall-supporting objects near the perimeter, "
        "keep seating or paired objects aligned with that focal area, and avoid random diagonal scatter."
    )


def _compact_retry_prompt(prompt: str) -> str:
    scene_prompt = _extract_scene_request(prompt)
    return (
        "Return only valid JSON with no markdown, no explanation, and no trailing text.\n"
        "Output a JSON array. Each item must be exactly: "
        '{"name":"object","position":[x,y,z],"rotation":[rx,ry,rz],"scale":[sx,sy,sz]}.\n'
        "Use numeric arrays with 3 numbers each. Keep y near 0. Keep objects non-overlapping.\n"
        "Plan the layout internally first, then emit only the final JSON array.\n"
        f"{_layout_reasoning_hint(scene_prompt)}\n"
        "Do not output container labels like classroom, room, scene, environment, or world as object names.\n"
        f"{_family_count_hint(scene_prompt)}\n"
        f"Scene prompt: {scene_prompt}\n"
        "JSON:"
    )


def extract_json_payload(text: str) -> str:
    """Extract the most likely JSON payload from noisy model output."""

    array_start = text.find("[")
    object_start = text.find("{")
    if array_start == -1 and object_start == -1:
        raise ValueError("No JSON payload found in model response.")
    if array_start != -1:
        end = text.rfind("]")
        if end != -1 and end > array_start:
            return text[array_start : end + 1]
    if object_start != -1:
        end = text.rfind("}")
        if end != -1 and end > object_start:
            return text[object_start : end + 1]
    raise ValueError("Incomplete JSON payload in model response.")


def repair_json_payload(text: str) -> str:
    """Best-effort repair for common invalid JSON patterns."""

    repaired = text.strip()
    repaired = repaired.replace("\r", "")
    repaired = re.sub(r",\s*([}\]])", r"\1", repaired)
    repaired = re.sub(r"([{,]\s*)([A-Za-z_][A-Za-z0-9_]*)(\s*:)", r'\1"\2"\3', repaired)
    repaired = re.sub(r'(\]|\}|"|[0-9])(\\?\s*\n\s*)(")', r"\1,\2\3", repaired)
    repaired = re.sub(r'(\]|\}|"|[0-9])(\s+)(")', r"\1,\2\3", repaired)
    repaired = re.sub(r"(\}|\])(\s*)(\{|\[)", r"\1,\2\3", repaired)
    repaired = re.sub(r'("scale"\s*:\s*\[[^\]]+\])(\s*)(\})', r"\1\2\3", repaired)
    return repaired


def parse_scene_payload(payload_text: str) -> tuple[object, bool]:
    """Parse model JSON with progressively more forgiving repair steps."""

    try:
        return json.loads(payload_text), False
    except json.JSONDecodeError:
        pass

    repaired_text = repair_json_payload(payload_text)
    try:
        return json.loads(repaired_text), True
    except json.JSONDecodeError:
        pass

    pythonish = repaired_text
    pythonish = re.sub(r"\btrue\b", "True", pythonish, flags=re.IGNORECASE)
    pythonish = re.sub(r"\bfalse\b", "False", pythonish, flags=re.IGNORECASE)
    pythonish = re.sub(r"\bnull\b", "None", pythonish, flags=re.IGNORECASE)
    try:
        return ast.literal_eval(pythonish), True
    except (ValueError, SyntaxError):
        pass

    salvage_matches = re.findall(
        r'\{\s*"name"\s*:\s*"[^"]+"\s*,\s*"position"\s*:\s*\[[^\]]+\]\s*,\s*"rotation"\s*:\s*\[[^\]]+\]\s*,\s*"scale"\s*:\s*\[[^\]]+\]\s*\}',
        repaired_text,
        flags=re.DOTALL,
    )
    if salvage_matches:
        return [json.loads(match) for match in salvage_matches], True

    raise json.JSONDecodeError("Unable to repair JSON payload.", payload_text, 0)


def validate_scene_payload(payload: object) -> List[Dict]:
    """Validate scene objects against a strict schema."""

    if isinstance(payload, dict) and "objects" in payload:
        payload = payload["objects"]
    elif isinstance(payload, dict) and {"name", "position", "rotation", "scale"}.issubset(payload.keys()):
        payload = [payload]
    if not isinstance(payload, list):
        raise ValueError("Scene graph response must be a JSON array.")
    validated: List[Dict] = []
    for item in payload:
        validated.append(SceneObjectModel.model_validate(item).model_dump())
    return validated


def _scene_request_profiles(prompt: str) -> List[dict]:
    config = get_config()
    resolved_model = resolve_ollama_model(
        config.scene_graph_model,
        config.ollama_base_url,
        timeout_s=min(config.llm_timeout_seconds, 8.0),
    )
    lightweight_model = resolve_ollama_model(
        "llama3.2:1b",
        config.ollama_base_url,
        timeout_s=min(config.llm_timeout_seconds, 8.0),
    )
    compact_prompt = _compact_retry_prompt(prompt)
    profiles: List[dict] = [
        {
            "model": resolved_model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.2,
                "num_predict": config.llm_max_predict,
                "num_ctx": config.llm_num_ctx,
            },
        },
        {
            "model": resolved_model,
            "prompt": compact_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "num_predict": min(config.llm_max_predict, 144),
                "num_ctx": min(config.llm_num_ctx, 1280),
            },
        },
        {
            "model": resolved_model,
            "prompt": compact_prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.0,
                "num_predict": min(config.llm_max_predict, 96),
                "num_ctx": min(config.llm_num_ctx, 896),
            },
        },
    ]
    if lightweight_model != resolved_model:
        profiles.append(
            {
                "model": lightweight_model,
                "prompt": compact_prompt,
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.1,
                    "num_predict": min(config.llm_max_predict, 96),
                    "num_ctx": min(config.llm_num_ctx, 768),
                },
            }
        )
    return profiles


def _ollama_request(payload: dict) -> str:
    config = get_config()
    request = urllib.request.Request(
        config.ollama_generate_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=config.llm_timeout_seconds) as response:
        body = json.loads(response.read().decode("utf-8"))
    raw_response = str(body.get("response", "")).strip()
    if not raw_response:
        raise ValueError("Ollama returned an empty response.")
    return raw_response


def query_scene_llm(prompt: str, retries: int | None = None) -> LLMSceneResult:
    """Query Ollama with validation, JSON repair, and confidence scoring."""

    config = get_config()
    if retries is None:
        retries = max(0, config.llm_retries)
    profiles = _scene_request_profiles(prompt)
    raw_response = ""
    errors: List[str] = []
    repaired = False

    for attempt in range(retries + 1):
        profile = profiles[min(attempt, len(profiles) - 1)]
        try:
            raw_response = _ollama_request(profile)
            payload_text = extract_json_payload(raw_response)
            payload, payload_repaired = parse_scene_payload(payload_text)
            repaired = repaired or payload_repaired
            objects = validate_scene_payload(payload)
            confidence = max(0.2, 0.95 - (0.2 * attempt) - (0.1 if repaired else 0.0))
            return LLMSceneResult(
                objects=[SceneObjectModel.model_validate(item) for item in objects],
                confidence=round(confidence, 3),
                repaired=repaired,
                raw_response=raw_response,
                errors=errors,
            )
        except (
            urllib.error.URLError,
            TimeoutError,
            OSError,
            ValueError,
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            model = str(profile.get("model", config.scene_graph_model))
            options = profile.get("options", {})
            raw_preview = raw_response[:160].replace("\n", "\\n") if raw_response else ""
            LOGGER.warning(
                "LLM scene generation attempt %s failed for model=%s num_ctx=%s num_predict=%s: %s%s",
                attempt + 1,
                model,
                options.get("num_ctx"),
                options.get("num_predict"),
                exc,
                f" | raw_preview={raw_preview}" if raw_preview else "",
            )
            errors.append(
                f"model={model} num_ctx={options.get('num_ctx')} num_predict={options.get('num_predict')}: {exc}"
            )
            repaired = repaired or "JSON" in str(exc)
    raise ValueError(errors[-1] if errors else "LLM scene generation failed.")
