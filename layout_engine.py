"""
Structured classroom layout helpers for the scene-graph pipeline.

This module is intentionally graph-only: it updates node transforms and stores
layout metadata without depending on USD authoring. The USD layer can later use
the returned room dimensions to add a floor plane and enclosing walls.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple


DESK_KEYWORDS = ("desk", "table")
CHAIR_KEYWORDS = ("chair",)
BOARD_KEYWORDS = ("board", "blackboard")


def ensure_lookup(graph: Dict) -> Dict[str, Dict]:
    lookup = graph.get("lookup")
    if isinstance(lookup, dict) and lookup:
        return lookup

    lookup = {}
    for node in graph.get("nodes", []):
        name = node.get("name")
        if name:
            lookup[name] = node
    graph["lookup"] = lookup
    return lookup


def is_classroom_graph(graph: Dict, prompt: str = "") -> bool:
    text = prompt.lower()
    if any(token in text for token in ("classroom", "school", "lecture", "teacher", "student")):
        return True

    names = [str(node.get("name", "")).lower() for node in graph.get("nodes", [])]
    desk_count = sum(1 for name in names if _matches(name, DESK_KEYWORDS))
    chair_count = sum(1 for name in names if _matches(name, CHAIR_KEYWORDS))
    board_count = sum(1 for name in names if _matches(name, BOARD_KEYWORDS))
    return desk_count >= 2 and chair_count >= 1 and board_count >= 1


def arrange_classroom_layout(
    graph: Dict,
    rows: Optional[int] = None,
    cols: Optional[int] = None,
    desk_spacing_x: float = 3.0,
    desk_spacing_z: float = 3.2,
    chair_offset_z: float = 1.0,
    room_margin: float = 3.0,
) -> Dict:
    """
    Arrange desk-like objects into a classroom grid and place chairs near them.

    The graph is updated in place and also returned for pipeline convenience.
    Room footprint metadata is written to `graph["layout"]` so the USD stage can
    later add a floor plane and enclosing walls without re-deriving bounds.
    """
    ensure_lookup(graph)

    desks = _collect_nodes(graph, DESK_KEYWORDS)
    chairs = _collect_nodes(graph, CHAIR_KEYWORDS)
    boards = _collect_nodes(graph, BOARD_KEYWORDS)

    if not desks:
        _store_room_metadata(graph, room_margin=room_margin)
        return graph

    row_count, col_count = _resolve_grid_shape(len(desks), rows, cols)
    desk_slots = _grid_slots(
        count=len(desks),
        rows=row_count,
        cols=col_count,
        spacing_x=desk_spacing_x,
        spacing_z=desk_spacing_z,
        start_z=2.0,
    )

    ordered_desks = _sort_nodes_for_layout(desks)
    for desk, (x, z) in zip(ordered_desks, desk_slots):
        position = desk.setdefault("position", [0.0, 0.0, 0.0])
        rotation = desk.setdefault("rotation", [0.0, 0.0, 0.0])
        scale = desk.setdefault("scale", [1.0, 1.0, 1.0])
        position[0] = x
        position[1] = 0.0
        position[2] = z
        rotation[0] = rotation[0] if len(rotation) > 0 else 0.0
        rotation[1] = 0.0
        rotation[2] = rotation[2] if len(rotation) > 2 else 0.0
        scale[0] = scale[0] if len(scale) > 0 else 1.0
        scale[1] = scale[1] if len(scale) > 1 else 1.0
        scale[2] = scale[2] if len(scale) > 2 else 1.0

    _place_chairs_near_desks(chairs, ordered_desks, chair_offset_z=chair_offset_z)
    _place_boards(boards, ordered_desks, room_margin=room_margin)
    _store_room_metadata(graph, room_margin=room_margin)
    _tag_layout_edges(graph, ordered_desks, chairs)
    return graph


def classroom_room_dimensions(graph: Dict) -> Dict[str, float]:
    layout = graph.get("layout", {})
    room = layout.get("room", {})
    if room:
        return room

    _store_room_metadata(graph, room_margin=3.0)
    return graph.get("layout", {}).get("room", {})


def _matches(name: str, keywords: Iterable[str]) -> bool:
    return any(keyword in name for keyword in keywords)


def _collect_nodes(graph: Dict, keywords: Iterable[str]) -> List[Dict]:
    nodes = []
    for node in graph.get("nodes", []):
        name = str(node.get("name", "")).lower()
        if _matches(name, keywords):
            nodes.append(node)
    return nodes


def _resolve_grid_shape(count: int, rows: Optional[int], cols: Optional[int]) -> Tuple[int, int]:
    if count <= 0:
        return 0, 0

    if rows and cols:
        return max(1, rows), max(1, cols)
    if rows:
        rows = max(1, rows)
        return rows, math.ceil(count / rows)
    if cols:
        cols = max(1, cols)
        return math.ceil(count / cols), cols

    cols = math.ceil(math.sqrt(count))
    rows = math.ceil(count / cols)
    return rows, cols


def _grid_slots(
    count: int,
    rows: int,
    cols: int,
    spacing_x: float,
    spacing_z: float,
    start_z: float,
) -> List[Tuple[float, float]]:
    slots: List[Tuple[float, float]] = []
    total_width = (cols - 1) * spacing_x

    for index in range(count):
        row = index // cols
        col = index % cols
        x = (col * spacing_x) - (total_width / 2.0)
        z = start_z + (row * spacing_z)
        slots.append((x, z))

    return slots


def _sort_nodes_for_layout(nodes: List[Dict]) -> List[Dict]:
    return sorted(
        nodes,
        key=lambda node: (
            str(node.get("name", "")),
            tuple(node.get("position", [0.0, 0.0, 0.0])),
        ),
    )


def _place_chairs_near_desks(chairs: List[Dict], desks: List[Dict], chair_offset_z: float) -> None:
    if not chairs or not desks:
        return

    ordered_chairs = _sort_nodes_for_layout(chairs)
    for index, chair in enumerate(ordered_chairs):
        desk = desks[index % len(desks)]
        desk_position = desk.setdefault("position", [0.0, 0.0, 0.0])
        chair_position = chair.setdefault("position", [0.0, 0.0, 0.0])
        chair_rotation = chair.setdefault("rotation", [0.0, 0.0, 0.0])

        chair_position[0] = desk_position[0]
        chair_position[1] = 0.0
        chair_position[2] = desk_position[2] + chair_offset_z
        chair_rotation[0] = chair_rotation[0] if len(chair_rotation) > 0 else 0.0
        chair_rotation[1] = 180.0
        chair_rotation[2] = chair_rotation[2] if len(chair_rotation) > 2 else 0.0


def _place_boards(boards: List[Dict], desks: List[Dict], room_margin: float) -> None:
    if not boards:
        return

    min_x, max_x, min_z, _max_z = _layout_bounds(desks)
    center_x = (min_x + max_x) / 2.0
    board_z = min_z - room_margin

    for board in boards:
        position = board.setdefault("position", [0.0, 0.0, 0.0])
        rotation = board.setdefault("rotation", [0.0, 0.0, 0.0])
        position[0] = center_x
        position[1] = 0.0
        position[2] = board_z
        rotation[1] = 0.0


def _layout_bounds(nodes: List[Dict]) -> Tuple[float, float, float, float]:
    if not nodes:
        return (-2.0, 2.0, -2.0, 2.0)

    xs = [float(node.get("position", [0.0, 0.0, 0.0])[0]) for node in nodes]
    zs = [float(node.get("position", [0.0, 0.0, 0.0])[2]) for node in nodes]
    return min(xs), max(xs), min(zs), max(zs)


def _store_room_metadata(graph: Dict, room_margin: float) -> None:
    nodes = graph.get("nodes", [])
    if not nodes:
        graph["layout"] = {
            "type": "generic",
            "room": {"width": 8.0, "depth": 8.0, "height": 3.0},
        }
        return

    min_x, max_x, min_z, max_z = _layout_bounds(nodes)
    width = max(8.0, (max_x - min_x) + (room_margin * 2.0))
    depth = max(8.0, (max_z - min_z) + (room_margin * 2.0))

    graph["layout"] = {
        "type": "classroom",
        "bounds": {
            "min_x": min_x,
            "max_x": max_x,
            "min_z": min_z,
            "max_z": max_z,
        },
        "room": {
            "width": round(width, 3),
            "depth": round(depth, 3),
            "height": 3.0,
        },
    }


def _tag_layout_edges(graph: Dict, desks: List[Dict], chairs: List[Dict]) -> None:
    if not desks or not chairs:
        return

    edges = graph.setdefault("edges", [])
    existing = {
        (edge.get("from"), edge.get("relation"), edge.get("to"))
        for edge in edges
        if isinstance(edge, dict)
    }

    ordered_chairs = _sort_nodes_for_layout(chairs)
    for index, chair in enumerate(ordered_chairs):
        desk = desks[index % len(desks)]
        relation = (chair.get("name"), "near", desk.get("name"))
        if relation not in existing:
            edges.append({"from": relation[0], "relation": relation[1], "to": relation[2]})
            existing.add(relation)
