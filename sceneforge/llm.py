"""Robust LLM scene generation utilities with validation and repair."""

from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Dict, List

from sceneforge.config import get_config
from sceneforge.logging_utils import get_logger
from sceneforge.models import LLMSceneResult, SceneObjectModel, ValidationError


LOGGER = get_logger(__name__)


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
    return repaired


def validate_scene_payload(payload: object) -> List[Dict]:
    """Validate scene objects against a strict schema."""

    if isinstance(payload, dict) and "objects" in payload:
        payload = payload["objects"]
    if not isinstance(payload, list):
        raise ValueError("Scene graph response must be a JSON array.")
    validated: List[Dict] = []
    for item in payload:
        validated.append(SceneObjectModel.model_validate(item).model_dump())
    return validated


def _ollama_request(prompt: str) -> str:
    config = get_config()
    payload = {
        "model": config.scene_graph_model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.2,
            "num_predict": config.llm_max_predict,
        },
    }
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
    raw_response = ""
    errors: List[str] = []
    repaired = False

    for attempt in range(retries + 1):
        try:
            raw_response = _ollama_request(prompt)
            payload_text = extract_json_payload(raw_response)
            try:
                payload = json.loads(payload_text)
            except json.JSONDecodeError:
                repaired = True
                payload = json.loads(repair_json_payload(payload_text))
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
            LOGGER.warning("LLM scene generation attempt %s failed: %s", attempt + 1, exc)
            errors.append(str(exc))
            repaired = repaired or "JSON" in str(exc)
    raise ValueError(errors[-1] if errors else "LLM scene generation failed.")
