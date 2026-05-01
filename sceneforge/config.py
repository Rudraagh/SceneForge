"""Centralized configuration for SceneForge."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SceneForgeConfig:
    """Resolved runtime configuration with OS-independent paths."""

    project_root: Path
    assets_dir: Path
    dataset_path: Path
    external_cache_dir: Path
    safe_generated_cache_dir: Path
    ollama_base_url: str
    ollama_generate_url: str
    scene_graph_model: str
    explain_model: str
    default_prompt: str
    asset_cache_ttl_hours: int
    objaverse_candidate_limit: int
    objaverse_min_score: float
    enable_procedural_fallback: bool
    llm_timeout_seconds: float
    llm_retries: int
    llm_max_predict: int


def _normalize_ollama_base_url(raw: str) -> str:
    value = (raw or "http://localhost:11434").rstrip("/")
    if value.endswith("/api/generate"):
        value = value[: -len("/api/generate")].rstrip("/")
    return value


def get_config(project_root: Path | None = None) -> SceneForgeConfig:
    """Build a runtime config from environment variables."""

    root = (project_root or Path(__file__).resolve().parent.parent).resolve()
    base_url = _normalize_ollama_base_url(os.getenv("OLLAMA_API_URL", "http://localhost:11434"))
    scene_graph_model = os.getenv("SCENE_GRAPH_OLLAMA_MODEL", "llama3.2:1b")
    return SceneForgeConfig(
        project_root=root,
        assets_dir=root / "assets",
        dataset_path=root / "scene_dataset.json",
        external_cache_dir=Path(
            os.getenv("SCENE_ASSET_CACHE_DIR", str(root / "external_asset_cache"))
        ),
        safe_generated_cache_dir=Path(
            os.getenv(
                "SCENE_SAFE_GENERATED_CACHE_DIR",
                str(Path(tempfile.gettempdir()) / "scene_asset_cache"),
            )
        ),
        ollama_base_url=base_url,
        ollama_generate_url=f"{base_url}/api/generate",
        scene_graph_model=scene_graph_model,
        explain_model=os.getenv("OLLAMA_EXPLAIN_MODEL", scene_graph_model),
        default_prompt=os.getenv(
            "SCENEFORGE_DEFAULT_PROMPT",
            "a medieval classroom with wooden desks",
        ),
        asset_cache_ttl_hours=int(os.getenv("SCENE_ASSET_CACHE_TTL_HOURS", "168")),
        objaverse_candidate_limit=int(os.getenv("OBJAVERSE_CANDIDATE_LIMIT", "5")),
        objaverse_min_score=float(os.getenv("OBJAVERSE_MIN_SCORE", "0.45")),
        enable_procedural_fallback=os.getenv("SCENE_ENABLE_PROCEDURAL_FALLBACK", "1") != "0",
        llm_timeout_seconds=float(os.getenv("SCENEFORGE_OLLAMA_TIMEOUT_S", "25")),
        llm_retries=int(os.getenv("SCENEFORGE_LLM_RETRIES", "1")),
        llm_max_predict=int(os.getenv("SCENEFORGE_OLLAMA_MAX_PREDICT", "300")),
    )
