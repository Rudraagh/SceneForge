"""
AI-assisted scene graph generation with deterministic safety constraints.

This public module is preserved for backwards compatibility. The production
implementation now lives under ``sceneforge`` while this file retains the
legacy function names and signatures used by the CLI, FastAPI, Streamlit, and
direct USD export pipeline.
"""

from __future__ import annotations

from typing import Dict, List, Optional

from sceneforge.orchestration import (
    _apply_scene_constraints,
    _normalize_entry,
    build_few_shot_prompt,
    build_graph,
    canonicalize_object_name,
    enrich_graph_with_relations,
    generate_minimal_scene,
    generate_rule_scene,
    generate_scene,
    generate_solar_system_scene,
    is_valid_scene,
    load_dataset,
    query_local_model,
    score_layout,
    select_examples,
    supported_assets,
    training_stub,
)
from sceneforge.scene_understanding import (
    classify_scene as _classify_scene_model,
    classify_scene_legacy,
    detect_scene_type,
)


def _scene_template_objects(scene_type: str) -> List[Dict]:
    """Return deterministic templates for supported scene families."""

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
        "basketball_court": [
            {"name": "basketball_hoop", "position": [-8.0, 0.0, 0.0], "rotation": [0.0, 90.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "basketball_hoop", "position": [8.0, 0.0, 0.0], "rotation": [0.0, -90.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "basketball", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "bench", "position": [0.0, 0.0, -5.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.2, 1.0, 1.0]},
            {"name": "bench", "position": [0.0, 0.0, 5.5], "rotation": [0.0, 180.0, 0.0], "scale": [1.2, 1.0, 1.0]},
            {"name": "lamp", "position": [-6.5, 0.0, -7.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "lamp", "position": [6.5, 0.0, 7.5], "rotation": [0.0, 180.0, 0.0], "scale": [1.0, 1.0, 1.0]},
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
        "courtyard": [
            {"name": "bench", "position": [-4.0, 0.0, 0.0], "rotation": [0.0, 90.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "bench", "position": [4.0, 0.0, 0.0], "rotation": [0.0, 90.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "pine_tree", "position": [6.5, 0.0, -2.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "pine_tree", "position": [7.0, 0.0, 2.0], "rotation": [0.0, 22.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "barrel", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ],
    }
    return [dict(item) for item in templates.get(scene_type, templates["studio"])]


def classify_scene(prompt: str) -> tuple[str, str]:
    """Legacy tuple return shape for the direct USD pipeline."""

    return classify_scene_legacy(prompt)
