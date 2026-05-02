"""
Map blueprint PNG centroids to USD scene positions.

Blueprint parser uses image coordinates with origin at the top-left (``y`` grows
downward). We map ``y`` to world ``Z`` with **image top toward +Z** so north /
``+Z`` matches common top-of-map reading. Stage up-axis remains ``Y``; lamps get
a small **Y** offset so strict blueprint mode reads as overhead fixtures in 3D
previews, not as floor markers.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from ai_scene_graph import canonicalize_object_name


DEFAULT_WORLD_WIDTH = 12.0
DEFAULT_WORLD_DEPTH = 12.0
# World Y (up) for lamp prims when placed from a 2D floor/ceiling plan blob.
LAMP_BLUEPRINT_Y_OFFSET = 2.75


def normalized_to_world(
    normalized_x: float,
    normalized_y: float,
    world_width: float = DEFAULT_WORLD_WIDTH,
    world_depth: float = DEFAULT_WORLD_DEPTH,
) -> Tuple[float, float]:
    clamped_x = max(0.0, min(1.0, float(normalized_x)))
    clamped_y = max(0.0, min(1.0, float(normalized_y)))
    world_x = (clamped_x - 0.5) * world_width
    # Image top (small normalized y) -> +Z (depth / "north" on typical map orientation).
    world_z = (0.5 - clamped_y) * world_depth
    return world_x, world_z


def pixel_to_world(
    pixel_x: float,
    pixel_y: float,
    image_width: int,
    image_height: int,
    world_width: float = DEFAULT_WORLD_WIDTH,
    world_depth: float = DEFAULT_WORLD_DEPTH,
) -> Tuple[float, float]:
    width = max(1, int(image_width))
    height = max(1, int(image_height))
    normalized_x = float(pixel_x) / max(1.0, width - 1.0)
    normalized_y = float(pixel_y) / max(1.0, height - 1.0)
    return normalized_to_world(normalized_x, normalized_y, world_width=world_width, world_depth=world_depth)


def map_blueprint_to_scene(
    blueprint_data: List[Dict],
    world_width: float = DEFAULT_WORLD_WIDTH,
    world_depth: float = DEFAULT_WORLD_DEPTH,
) -> List[Dict]:
    scene_objects: List[Dict] = []

    for item in blueprint_data or []:
        name = canonicalize_object_name(str(item.get("name", "")))
        if not name:
            continue

        world_x, world_z = normalized_to_world(
            item.get("x", 0.5),
            item.get("y", 0.5),
            world_width=world_width,
            world_depth=world_depth,
        )
        base = name.lower()
        world_y = float(LAMP_BLUEPRINT_Y_OFFSET) if base.startswith("lamp") else 0.0
        scene_objects.append(
            {
                "name": name,
                "position": [round(world_x, 3), round(world_y, 3), round(world_z, 3)],
                "rotation": [0.0, 0.0, 0.0],
                "scale": [1.0, 1.0, 1.0],
            }
        )

    return scene_objects


def merge_blueprint_positions(base_scene: List[Dict], blueprint_scene: List[Dict]) -> List[Dict]:
    if not blueprint_scene:
        return base_scene

    available_by_name: Dict[str, List[Dict]] = {}
    for item in blueprint_scene:
        available_by_name.setdefault(item["name"], []).append(item)

    merged: List[Dict] = []
    for obj in base_scene:
        name = canonicalize_object_name(str(obj.get("name", "")))
        candidates = available_by_name.get(name, [])
        if candidates:
            mapped = candidates.pop(0)
            updated = dict(obj)
            updated["position"] = list(mapped.get("position", obj.get("position", [0.0, 0.0, 0.0])))
            merged.append(updated)
        else:
            merged.append(obj)

    return merged
