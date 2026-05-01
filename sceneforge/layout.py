"""Constraint-oriented layout helpers and relation application."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Tuple

from sceneforge.logging_utils import get_logger
from sceneforge.relations import ParsedRelation


LOGGER = get_logger(__name__)
DEFAULT_MIN_SPACING = 1.2
OBJECT_FOOTPRINTS = {
    "chair": 0.75,
    "wooden_desk": 1.2,
    "table": 1.2,
    "blackboard": 1.0,
    "bookshelf": 1.0,
    "bench": 1.1,
    "barrel": 0.7,
    "crate": 0.8,
}


def ensure_lookup(graph: Dict) -> Dict[str, Dict]:
    """Ensure a name -> node lookup exists on the graph."""

    lookup = graph.get("lookup")
    if isinstance(lookup, dict) and lookup:
        return lookup
    lookup = {}
    for node in graph.get("nodes", []):
        name = str(node.get("name", "")).strip()
        if name:
            lookup[name] = node
    graph["lookup"] = lookup
    return lookup


def _footprint(node: Dict) -> float:
    name = str(node.get("name", "")).lower()
    for key, radius in OBJECT_FOOTPRINTS.items():
        if key in name:
            return radius
    scale = node.get("scale", [1.0, 1.0, 1.0])
    return max(0.6, float(scale[0]) * 0.5, float(scale[2]) * 0.5)


def _position(node: Dict) -> List[float]:
    return node.setdefault("position", [0.0, 0.0, 0.0])


def _rotation(node: Dict) -> List[float]:
    return node.setdefault("rotation", [0.0, 0.0, 0.0])


def _direction_vector(direction: str, distance: float) -> Tuple[float, float]:
    mapping = {
        "left": (-distance, 0.0),
        "right": (distance, 0.0),
        "front": (0.0, -distance),
        "back": (0.0, distance),
    }
    return mapping[direction]


def apply_relation_constraints(graph: Dict, relations: Iterable[ParsedRelation]) -> Dict:
    """Apply structured relation constraints in-place."""

    lookup = ensure_lookup(graph)
    for relation in relations:
        source = lookup.get(relation.source)
        target = lookup.get(relation.target)
        if not source or not target:
            continue

        source_pos = _position(source)
        target_pos = _position(target)
        source_rot = _rotation(source)
        target_rot = _rotation(target)
        spacing = _footprint(source) + _footprint(target) + 0.2

        if relation.relation == "on":
            source_pos[0] = target_pos[0]
            source_pos[2] = target_pos[2]
            source_pos[1] = max(source_pos[1], target_pos[1] + 1.0)
        elif relation.relation == "under":
            source_pos[0] = target_pos[0]
            source_pos[2] = target_pos[2]
            source_pos[1] = min(source_pos[1], target_pos[1] - 0.8)
        elif relation.relation == "inside":
            source_pos[0] = target_pos[0]
            source_pos[2] = target_pos[2]
            source_pos[1] = target_pos[1]
        elif relation.relation == "near":
            if math.hypot(source_pos[0] - target_pos[0], source_pos[2] - target_pos[2]) > spacing:
                source_pos[0] = target_pos[0]
                source_pos[2] = target_pos[2] + spacing
        elif relation.relation == "beside":
            source_pos[0] = target_pos[0] + spacing
            source_pos[2] = target_pos[2]
        elif relation.relation == "facing":
            dx = target_pos[0] - source_pos[0]
            dz = target_pos[2] - source_pos[2]
            source_rot[1] = math.degrees(math.atan2(dx, dz))
        elif relation.relation == "aligned_with":
            source_pos[2] = target_pos[2]
            source_rot[1] = target_rot[1]
        elif relation.relation == "orbits":
            continue
    return graph


def prevent_overlaps(graph: Dict, min_spacing: float = DEFAULT_MIN_SPACING, max_passes: int = 8) -> Dict:
    """Push objects apart while preserving a minimum spacing."""

    nodes = graph.get("nodes", [])
    for _pass in range(max_passes):
        moved = False
        for index, node in enumerate(nodes):
            pos_a = _position(node)
            for other in nodes[index + 1 :]:
                pos_b = _position(other)
                dx = pos_a[0] - pos_b[0]
                dz = pos_a[2] - pos_b[2]
                distance = math.hypot(dx, dz)
                target = max(min_spacing, _footprint(node) + _footprint(other))
                if distance == 0.0:
                    pos_a[0] += target / 2.0
                    pos_b[0] -= target / 2.0
                    moved = True
                    continue
                if distance < target:
                    push = (target - distance) / 2.0
                    nx = dx / distance
                    nz = dz / distance
                    pos_a[0] += nx * push
                    pos_a[2] += nz * push
                    pos_b[0] -= nx * push
                    pos_b[2] -= nz * push
                    moved = True
        if not moved:
            break
    return graph

