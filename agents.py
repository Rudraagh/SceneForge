from __future__ import annotations
import math


def _ensure_lookup(graph):
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


def _distance(node1, node2):
    x1, _, z1 = node1.get("position", [0.0, 0.0, 0.0])
    x2, _, z2 = node2.get("position", [0.0, 0.0, 0.0])
    return math.hypot(x1 - x2, z1 - z2)


def _is_chair_table_pair(obj1, obj2):
    name1 = str(obj1.get("name", "")).lower()
    name2 = str(obj2.get("name", "")).lower()
    return "chair" in name1 and ("desk" in name2 or "table" in name2)


def domain_agent(graph):
    lookup = _ensure_lookup(graph)

    for edge in graph.get("edges", []):
        obj1 = lookup.get(edge.get("from"))
        obj2 = lookup.get(edge.get("to"))
        relation = edge.get("relation")

        if not obj1 or not obj2:
            continue

        pos1 = obj1.setdefault("position", [0.0, 0.0, 0.0])
        pos2 = obj2.setdefault("position", [0.0, 0.0, 0.0])

        if relation == "beside":
            dx = pos2[0] - pos1[0]
            dz = pos2[2] - pos1[2]
            distance = math.hypot(dx, dz)
            target = 1.0 if _is_chair_table_pair(obj1, obj2) else 1.5

            if distance > target and distance > 0:
                move = min(0.5, (distance - target) / 2.0)
                pos1[0] += (dx / distance) * move
                pos1[2] += (dz / distance) * move

            if _is_chair_table_pair(obj1, obj2):
                pos1[0] = pos2[0]
                pos1[2] = pos2[2] + target
                rotation = obj1.setdefault("rotation", [0.0, 0.0, 0.0])
                rotation[1] = 180.0

        elif relation == "on":
            pos1[1] = pos2[1] + 1.0
            pos1[0] = pos2[0]
            pos1[2] = pos2[2]

        elif relation == "under":
            pos1[0] = pos2[0]
            pos1[2] = pos2[2]
            pos1[1] = pos2[1] - 0.8

        elif relation == "inside":
            pos1[0] = pos2[0]
            pos1[1] = pos2[1]
            pos1[2] = pos2[2]

        elif relation == "near":
            dx = pos2[0] - pos1[0]
            dz = pos2[2] - pos1[2]
            distance = math.hypot(dx, dz)
            target = 1.0 if _is_chair_table_pair(obj1, obj2) else 2.0

            if distance > target and distance > 0:
                move = min(0.4, (distance - target) / 2.0)
                pos1[0] += (dx / distance) * move
                pos1[2] += (dz / distance) * move

            if _is_chair_table_pair(obj1, obj2):
                pos1[0] = pos2[0]
                pos1[2] = pos2[2] + target
                rotation = obj1.setdefault("rotation", [0.0, 0.0, 0.0])
                rotation[1] = 180.0

        elif relation == "facing":
            dx = pos2[0] - pos1[0]
            dz = pos2[2] - pos1[2]
            rotation = obj1.setdefault("rotation", [0.0, 0.0, 0.0])
            rotation[1] = math.degrees(math.atan2(dx, dz))

        elif relation == "aligned_with":
            pos1[2] = pos2[2]
            rotation = obj1.setdefault("rotation", [0.0, 0.0, 0.0])
            rotation2 = obj2.setdefault("rotation", [0.0, 0.0, 0.0])
            rotation[1] = rotation2[1]

    return graph


def evaluator_agent(graph):
    nodes = graph.get("nodes", [])
    if len(nodes) < 2:
        return 1.0

    score = 1.0
    pair_count = 0

    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            pair_count += 1
            distance = _distance(nodes[i], nodes[j])

            if distance < 0.5:
                score -= 0.35
            elif distance < 1.0:
                score -= 0.15
            elif 1.0 <= distance <= 3.0:
                score += 0.05

    if pair_count:
        score = score / (1.0 + 0.02 * pair_count)

    return max(0.0, min(1.0, round(score, 3)))


def reflection_agent(graph):
    score = evaluator_agent(graph)

    if score < 0.4:
        return "Objects are too crowded. Spread them out."
    if score < 0.7:
        return "Layout is okay but spacing can improve."
    return "Layout looks good."
