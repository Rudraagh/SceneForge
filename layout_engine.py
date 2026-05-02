"""
Structured classroom layout helpers for the scene-graph pipeline.

This module is intentionally graph-only: it updates node transforms and stores
layout metadata without depending on USD authoring. The USD layer can later use
the returned room dimensions to add a floor plane and enclosing walls.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Tuple

from sceneforge.layout import prevent_overlaps


DESK_KEYWORDS = ("desk", "table")
CHAIR_KEYWORDS = ("chair",)
BOARD_KEYWORDS = ("board", "blackboard")
THRONE_KEYWORDS = ("throne",)
BANNER_KEYWORDS = ("banner",)
TORCH_KEYWORDS = ("torch",)
BENCH_KEYWORDS = ("bench",)
WALL_DECOR_KEYWORDS = ("banner", "torch", "blackboard", "bookshelf", "lamp")
SURFACE_KEYWORDS = ("table", "desk", "stall", "throne", "campfire", "fountain")
STORAGE_KEYWORDS = ("crate", "barrel")
NATURE_KEYWORDS = ("tree", "pine")
SOLAR_SEQUENCE = ("sun", "mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune")
PLANET_RADII = {
    "mercury": 2.4,
    "venus": 4.0,
    "earth": 5.6,
    "mars": 7.2,
    "jupiter": 10.2,
    "saturn": 13.2,
    "uranus": 16.2,
    "neptune": 19.2,
}
PLANET_ANGLES = {
    "mercury": 12.0,
    "venus": 62.0,
    "earth": 118.0,
    "mars": 188.0,
    "jupiter": 248.0,
    "saturn": 302.0,
    "uranus": 352.0,
    "neptune": 32.0,
}


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


def is_throne_room_graph(graph: Dict, prompt: str = "") -> bool:
    text = prompt.lower()
    if any(token in text for token in ("throne room", "royal", "throne", "castle", "king", "queen")):
        return True

    names = [str(node.get("name", "")).lower() for node in graph.get("nodes", [])]
    throne_count = sum(1 for name in names if _matches(name, THRONE_KEYWORDS))
    banner_count = sum(1 for name in names if _matches(name, BANNER_KEYWORDS))
    torch_count = sum(1 for name in names if _matches(name, TORCH_KEYWORDS))
    return throne_count >= 1 and (banner_count >= 1 or torch_count >= 1)


def is_solar_system_graph(graph: Dict, prompt: str = "") -> bool:
    text = prompt.lower()
    if any(token in text for token in ("solar system", "planetary system", "sun and planets", "planets orbiting")):
        return True

    names = [str(node.get("name", "")).lower() for node in graph.get("nodes", [])]
    has_sun = any("sun" in name for name in names)
    planet_count = sum(1 for name in names if any(planet in name for planet in SOLAR_SEQUENCE[1:]))
    return has_sun and planet_count >= 3


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
        start_z=-2.0,
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
    prevent_overlaps(graph, min_spacing=0.95)
    return graph


def arrange_throne_room_layout(graph: Dict, room_margin: float = 3.5) -> Dict:
    """
    Arrange ceremonial objects around a throne-focused front wall composition.
    """
    ensure_lookup(graph)

    thrones = _collect_nodes(graph, THRONE_KEYWORDS)
    banners = _collect_nodes(graph, BANNER_KEYWORDS)
    torches = _collect_nodes(graph, TORCH_KEYWORDS)
    benches = _collect_nodes(graph, BENCH_KEYWORDS)

    if not thrones:
        _store_room_metadata(graph, room_margin=room_margin, layout_type="throne_room")
        return graph

    throne = _sort_nodes_for_layout(thrones)[0]
    throne_position = throne.setdefault("position", [0.0, 0.0, 0.0])
    throne_rotation = throne.setdefault("rotation", [0.0, 0.0, 0.0])
    throne_position[0] = 0.0
    throne_position[1] = 0.0
    throne_position[2] = -4.4
    throne_rotation[1] = 0.0

    for index, banner in enumerate(_sort_nodes_for_layout(banners)):
        side = -1.0 if index % 2 == 0 else 1.0
        slot = index // 2
        position = banner.setdefault("position", [0.0, 0.0, 0.0])
        rotation = banner.setdefault("rotation", [0.0, 0.0, 0.0])
        position[0] = round(side * (4.6 + (slot * 1.1)), 3)
        position[1] = 0.0
        position[2] = -4.95
        rotation[1] = 0.0

    for index, torch in enumerate(_sort_nodes_for_layout(torches)):
        side = -1.0 if index % 2 == 0 else 1.0
        slot = index // 2
        position = torch.setdefault("position", [0.0, 0.0, 0.0])
        rotation = torch.setdefault("rotation", [0.0, 0.0, 0.0])
        position[0] = round(side * (3.1 + (slot * 1.15)), 3)
        position[1] = 0.0
        position[2] = round(-2.35 - (slot * 0.35), 3)
        rotation[1] = 0.0

    for index, bench in enumerate(_sort_nodes_for_layout(benches)):
        side = -1.0 if index % 2 == 0 else 1.0
        row = index // 2
        position = bench.setdefault("position", [0.0, 0.0, 0.0])
        rotation = bench.setdefault("rotation", [0.0, 0.0, 0.0])
        position[0] = round(side * (3.4 + (row * 0.15)), 3)
        position[1] = 0.0
        position[2] = round(0.9 + (row * 1.55), 3)
        rotation[1] = 90.0

    _store_room_metadata(graph, room_margin=room_margin, layout_type="throne_room")
    prevent_overlaps(graph, min_spacing=1.1)
    return graph


def arrange_solar_system_layout(graph: Dict, room_margin: float = 4.0) -> Dict:
    """
    Arrange solar-system objects into concentric orbits around the sun.
    """
    ensure_lookup(graph)
    nodes = graph.get("nodes", [])
    if not nodes:
        _store_room_metadata(graph, room_margin=room_margin, layout_type="solar_system")
        return graph

    lookup = {_base_object_name(str(node.get("name", ""))): node for node in nodes}
    sun = lookup.get("sun")
    if sun:
        _set_node_transform(sun, x=0.0, z=0.0, yaw=0.0)

    for planet in SOLAR_SEQUENCE[1:]:
        node = lookup.get(planet)
        if not node:
            continue
        radius = PLANET_RADII[planet]
        angle_deg = PLANET_ANGLES[planet]
        angle = math.radians(angle_deg)
        x = math.cos(angle) * radius
        z = math.sin(angle) * radius
        _set_node_transform(node, x=x, z=z, yaw=0.0)

    _store_room_metadata(graph, room_margin=room_margin, layout_type="solar_system")
    prevent_overlaps(graph, min_spacing=1.6)
    return graph


def arrange_semantic_layout(graph: Dict, prompt: str = "", scene_type: str = "", room_margin: float = 3.25) -> Dict:
    """
    Generic semantic layout for AI-generated scenes that do not have a stricter
    family-specific arrangement. It chooses a focal object, then distributes
    supporting objects into front, side, wall, and perimeter zones.
    """
    ensure_lookup(graph)
    nodes = list(graph.get("nodes", []))
    if not nodes:
        _store_room_metadata(graph, room_margin=room_margin, layout_type=scene_type or "generic")
        return graph

    groups = _group_nodes_by_base_name(nodes)
    focal = _pick_focal_node(nodes, prompt=prompt, scene_type=scene_type)
    if focal:
        focal_position = _semantic_focal_position(focal, scene_type=scene_type, prompt=prompt)
        _set_node_transform(focal, x=focal_position[0], z=focal_position[1], yaw=0.0)

    wall_groups: List[Tuple[str, List[Dict]]] = []
    seat_groups: List[Tuple[str, List[Dict]]] = []
    storage_groups: List[Tuple[str, List[Dict]]] = []
    nature_groups: List[Tuple[str, List[Dict]]] = []
    misc_groups: List[Tuple[str, List[Dict]]] = []

    for base_name, members in groups:
        if focal and any(node is focal for node in members):
            remaining = [node for node in members if node is not focal]
            if not remaining:
                continue
            members = remaining
        lowered = base_name.lower()
        if _matches(lowered, WALL_DECOR_KEYWORDS):
            wall_groups.append((base_name, members))
        elif _matches(lowered, BENCH_KEYWORDS) or _matches(lowered, CHAIR_KEYWORDS):
            seat_groups.append((base_name, members))
        elif _matches(lowered, STORAGE_KEYWORDS):
            storage_groups.append((base_name, members))
        elif _matches(lowered, NATURE_KEYWORDS):
            nature_groups.append((base_name, members))
        else:
            misc_groups.append((base_name, members))

    _place_groups_on_wall(wall_groups, back_z=-4.9)
    _place_seating_groups(seat_groups, front_start_z=0.9)
    _place_storage_groups(storage_groups, z_band=(-1.2, 2.1))
    _place_nature_groups(nature_groups)
    _place_misc_groups(misc_groups)

    _store_room_metadata(graph, room_margin=room_margin, layout_type=scene_type or "generic")
    prevent_overlaps(graph, min_spacing=1.0)
    return graph


def has_blueprint_positions(graph: Dict) -> bool:
    return any("blueprint_position" in node for node in graph.get("nodes", []))


def arrange_blueprint_layout(graph: Dict, room_margin: float = 3.0) -> Dict:
    """
    Re-apply explicit blueprint positions so generic blueprint scenes preserve
    the authored 2D structure while still receiving room metadata.
    """
    ensure_lookup(graph)

    for node in graph.get("nodes", []):
        blueprint_position = node.get("blueprint_position")
        if not blueprint_position:
            continue
        position = node.setdefault("position", [0.0, 0.0, 0.0])
        position[0] = float(blueprint_position[0])
        position[1] = 0.0
        position[2] = float(blueprint_position[2])

    _store_room_metadata(graph, room_margin=room_margin)
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
        z = start_z - (row * spacing_z)
        slots.append((x, z))

    return slots


def _sort_nodes_for_layout(nodes: List[Dict]) -> List[Dict]:
    return sorted(
        nodes,
        key=lambda node: (
            -float(node.get("position", [0.0, 0.0, 0.0])[2]),
            float(node.get("position", [0.0, 0.0, 0.0])[0]),
            str(node.get("name", "")),
        ),
    )


def _group_nodes_by_base_name(nodes: List[Dict]) -> List[Tuple[str, List[Dict]]]:
    grouped: Dict[str, List[Dict]] = {}
    for node in nodes:
        raw_name = str(node.get("name", ""))
        base_name = raw_name.rsplit("_", 1)[0] if raw_name.rsplit("_", 1)[-1].isdigit() else raw_name
        grouped.setdefault(base_name, []).append(node)
    return sorted(grouped.items(), key=lambda item: (len(item[1]) * -1, item[0]))


def _base_object_name(name: str) -> str:
    return str(name or "").rsplit("_", 1)[0] if str(name or "").rsplit("_", 1)[-1].isdigit() else str(name or "")


def _semantic_focal_position(node: Dict, scene_type: str, prompt: str) -> Tuple[float, float]:
    lowered = str(node.get("name", "")).lower()
    prompt_text = (prompt or "").lower()
    if "throne" in lowered or scene_type == "throne_room":
        return (0.0, -4.4)
    if "blackboard" in lowered or "board" in lowered:
        return (0.0, -5.2)
    if "campfire" in lowered or "fountain" in lowered:
        return (0.0, 0.0)
    if "stall" in lowered or scene_type == "market":
        return (0.0, -1.0)
    if "basketball" in lowered and "hoop" not in lowered:
        return (0.0, 0.0)
    if any(token in prompt_text for token in ("center", "central", "middle")):
        return (0.0, 0.0)
    return (0.0, -0.4)


def _pick_focal_node(nodes: List[Dict], prompt: str = "", scene_type: str = "") -> Optional[Dict]:
    priority_tokens = (
        "throne",
        "blackboard",
        "campfire",
        "fountain",
        "market_stall",
        "table",
        "desk",
        "basketball",
        "sun",
    )
    lowered_prompt = (prompt or "").lower()
    if scene_type == "studio" and "table" in lowered_prompt:
        priority_tokens = ("table", "desk") + priority_tokens
    for token in priority_tokens:
        for node in nodes:
            if token in str(node.get("name", "")).lower():
                return node
    return _sort_nodes_for_layout(nodes)[0] if nodes else None


def _set_node_transform(node: Dict, x: float, z: float, yaw: float) -> None:
    position = node.setdefault("position", [0.0, 0.0, 0.0])
    rotation = node.setdefault("rotation", [0.0, 0.0, 0.0])
    position[0] = round(float(x), 3)
    position[1] = 0.0
    position[2] = round(float(z), 3)
    rotation[1] = round(float(yaw), 3)


def _place_groups_on_wall(groups: List[Tuple[str, List[Dict]]], back_z: float) -> None:
    lane = 0
    for _base_name, members in groups:
        ordered = _sort_nodes_for_layout(members)
        if len(ordered) == 1:
            _set_node_transform(ordered[0], x=4.8 - (lane * 1.0), z=back_z + (lane * 0.15), yaw=0.0)
        else:
            for index, node in enumerate(ordered):
                side = -1.0 if index % 2 == 0 else 1.0
                row = index // 2
                _set_node_transform(
                    node,
                    x=side * (4.6 + row * 1.1),
                    z=back_z + (lane * 0.15),
                    yaw=0.0,
                )
        lane += 1


def _place_seating_groups(groups: List[Tuple[str, List[Dict]]], front_start_z: float) -> None:
    lane = 0
    for base_name, members in groups:
        ordered = _sort_nodes_for_layout(members)
        yaw = 90.0 if "bench" in base_name.lower() else 0.0
        if len(ordered) == 1:
            _set_node_transform(ordered[0], x=0.0, z=front_start_z + lane * 1.5, yaw=yaw)
        else:
            for index, node in enumerate(ordered):
                side = -1.0 if index % 2 == 0 else 1.0
                row = index // 2
                _set_node_transform(
                    node,
                    x=side * (3.2 + row * 0.85),
                    z=front_start_z + (lane * 1.55) + (row * 1.2),
                    yaw=90.0 if "bench" in base_name.lower() else 0.0,
                )
        lane += 1


def _place_storage_groups(groups: List[Tuple[str, List[Dict]]], z_band: Tuple[float, float]) -> None:
    lane = 0
    for _base_name, members in groups:
        ordered = _sort_nodes_for_layout(members)
        center_z = z_band[0] + min(lane, 4) * 0.85
        if len(ordered) == 1:
            _set_node_transform(ordered[0], x=2.6, z=center_z, yaw=0.0)
        else:
            for index, node in enumerate(ordered):
                side = -1.0 if index % 2 == 0 else 1.0
                row = index // 2
                _set_node_transform(
                    node,
                    x=side * (2.6 + row * 0.8),
                    z=min(z_band[1], center_z + row * 0.75),
                    yaw=0.0,
                )
        lane += 1


def _place_nature_groups(groups: List[Tuple[str, List[Dict]]]) -> None:
    ring_slots = [(-5.2, -3.8), (5.2, -3.8), (-5.6, 3.8), (5.6, 3.8), (0.0, 5.0), (-6.0, 0.0), (6.0, 0.0)]
    slot_index = 0
    for _base_name, members in groups:
        for node in _sort_nodes_for_layout(members):
            x, z = ring_slots[slot_index % len(ring_slots)]
            _set_node_transform(node, x=x, z=z, yaw=0.0)
            slot_index += 1


def _place_misc_groups(groups: List[Tuple[str, List[Dict]]]) -> None:
    slot_index = 0
    for _base_name, members in groups:
        for node in _sort_nodes_for_layout(members):
            ring = 2.6 + (slot_index // 6) * 1.0
            angle = (slot_index % 6) * (math.tau / 6.0)
            _set_node_transform(node, x=math.cos(angle) * ring, z=math.sin(angle) * ring, yaw=0.0)
            slot_index += 1


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
        chair_position[2] = desk_position[2] - chair_offset_z
        chair_rotation[0] = chair_rotation[0] if len(chair_rotation) > 0 else 0.0
        chair_rotation[1] = 0.0
        chair_rotation[2] = chair_rotation[2] if len(chair_rotation) > 2 else 0.0


def _place_boards(boards: List[Dict], desks: List[Dict], room_margin: float) -> None:
    if not boards:
        return

    min_x, max_x, _min_z, max_z = _layout_bounds(desks)
    center_x = (min_x + max_x) / 2.0
    board_z = max_z + room_margin

    for board in boards:
        position = board.setdefault("position", [0.0, 0.0, 0.0])
        rotation = board.setdefault("rotation", [0.0, 0.0, 0.0])
        position[0] = center_x
        position[1] = 0.0
        position[2] = board_z
        rotation[1] = 180.0


def _layout_bounds(nodes: List[Dict]) -> Tuple[float, float, float, float]:
    if not nodes:
        return (-2.0, 2.0, -2.0, 2.0)

    xs = [float(node.get("position", [0.0, 0.0, 0.0])[0]) for node in nodes]
    zs = [float(node.get("position", [0.0, 0.0, 0.0])[2]) for node in nodes]
    return min(xs), max(xs), min(zs), max(zs)


def _store_room_metadata(graph: Dict, room_margin: float, layout_type: str = "classroom") -> None:
    nodes = graph.get("nodes", [])
    if not nodes:
        graph["layout"] = {
            "type": layout_type if layout_type else "generic",
            "room": {"width": 8.0, "depth": 8.0, "height": 3.0},
        }
        return

    min_x, max_x, min_z, max_z = _layout_bounds(nodes)
    width = max(8.0, (max_x - min_x) + (room_margin * 2.0))
    depth = max(8.0, (max_z - min_z) + (room_margin * 2.0))
    center_x = (min_x + max_x) / 2.0
    center_z = (min_z + max_z) / 2.0

    graph["layout"] = {
        "type": layout_type,
        "bounds": {
            "min_x": min_x,
            "max_x": max_x,
            "min_z": min_z,
            "max_z": max_z,
            "center_x": round(center_x, 3),
            "center_z": round(center_z, 3),
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
