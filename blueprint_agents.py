from __future__ import annotations

import math
from typing import Dict, List, Tuple


ROOM_MIN = -6.0
ROOM_MAX = 6.0
MIN_SPACING = 0.75
NEAR_DISTANCE = 2.25
MAX_REFINEMENT_STEP = 0.3
GRID_STEP = 0.1
SAFE_MAX_MOVE = 0.15
ANGLE_TOL = 30.0
DIST_TOL = 0.5


def evaluate_scene(objects: List[Dict]) -> Dict:
    violations: List[str] = []
    overlap_count = 0
    spacing_rewards = 0
    pair_count = 0

    for obj in objects:
        name = str(obj.get("name", "object"))
        x, _y, z = obj.get("position", [0.0, 0.0, 0.0])
        if x < ROOM_MIN or x > ROOM_MAX or z < ROOM_MIN or z > ROOM_MAX:
            violations.append(f"{name} is outside expected room bounds")

    for i in range(len(objects)):
        for j in range(i + 1, len(objects)):
            pair_count += 1
            a = objects[i]
            b = objects[j]
            distance = _distance(a, b)
            if distance < MIN_SPACING:
                overlap_count += 1
                violations.append(f"{a['name']} overlaps {b['name']}")
            elif 1.0 <= distance <= 3.0:
                spacing_rewards += 1

    placement_score = 1.0
    if pair_count:
        placement_score += 0.15 * (spacing_rewards / pair_count)
    placement_score -= 0.25 * overlap_count
    placement_score -= 0.05 * len([v for v in violations if "outside" in v])
    placement_score = max(0.0, min(1.0, round(placement_score, 3)))

    return {
        "placement_score": placement_score,
        "overlap_count": overlap_count,
        "violations": violations,
    }


def infer_relationships(objects: List[Dict]) -> List[Tuple]:
    relations: List[Tuple] = []
    desks = [obj for obj in objects if _is_desk(obj)]
    chairs = [obj for obj in objects if _is_chair(obj)]
    boards = [obj for obj in objects if _is_board(obj)]

    for chair in chairs:
        desk = _nearest_object(chair, desks)
        if desk and _distance(chair, desk) <= NEAR_DISTANCE:
            relations.append((chair["name"], "near", desk["name"]))

    if boards:
        board = min(boards, key=lambda obj: obj.get("position", [0.0, 0.0, 0.0])[2])
        for desk in desks:
            relations.append((desk["name"], "facing", board["name"]))

    return relations


def reflect_scene(objects: List[Dict], relations: List[Tuple]) -> Dict:
    detected_issues: List[str] = []
    relation_map = {(a, rel): b for a, rel, b in relations}
    lookup = {obj["name"]: obj for obj in objects if "name" in obj}

    for obj in objects:
        if not _is_chair(obj):
            continue
        target_name = relation_map.get((obj["name"], "near"))
        target = lookup.get(target_name) if target_name else None
        if not target:
            detected_issues.append(f"{obj['name']} is not associated with a desk")
            continue
        distance_delta = max(0.0, _distance(obj, target) - (1.0 + DIST_TOL))
        if distance_delta > DIST_TOL:
            detected_issues.append(f"{obj['name']} is too far from its desk")
            continue
        if not _faces_target(obj, target, tolerance_degrees=ANGLE_TOL):
            detected_issues.append(f"{obj['name']} is not facing its desk")

    for obj in objects:
        if not _is_desk(obj):
            continue
        target_name = relation_map.get((obj["name"], "facing"))
        target = lookup.get(target_name) if target_name else None
        if not target:
            detected_issues.append(f"{obj['name']} has no blackboard target")
            continue
        if not _faces_target(obj, target, tolerance_degrees=ANGLE_TOL):
            detected_issues.append(f"{obj['name']} is not oriented toward the blackboard")

    issues = detected_issues[:5]
    total_objects = max(1, len(objects))
    reasoning_score = max(0.0, min(1.0, round(1.0 - (len(issues) / total_objects), 3)))

    return {
        "reasoning_score": reasoning_score,
        "issues": issues,
    }


def compute_score(T, M, C, alpha=0.5, beta=0.3, gamma=0.2):
    return alpha * T + beta * M - gamma * C


def adaptive_controller(prev_score, curr_score, violations, iteration):
    base_threshold = 0.85

    if violations > 5:
        threshold = 0.75
    elif curr_score > 0.9:
        threshold = 0.9
    else:
        threshold = base_threshold

    improvement = curr_score - prev_score
    if improvement < 0.01:
        continue_flag = False
    elif iteration >= 4:
        continue_flag = False
    else:
        continue_flag = True

    if violations > 3:
        refinement_weight = 1.0
    else:
        refinement_weight = 0.5

    return {
        "threshold": float(threshold),
        "continue": bool(continue_flag),
        "refinement_weight": float(refinement_weight),
    }


def explain_scene(eval_result, reflect_result, relations, score):
    violations = list(eval_result.get("violations", []))
    issues = list(reflect_result.get("issues", []))
    placement_score = float(eval_result.get("placement_score", 0.0))
    reasoning_score = float(reflect_result.get("reasoning_score", 0.0))
    relation_count = len(relations)
    overlap_count = int(eval_result.get("overlap_count", 0))

    if score >= 0.85 and not violations and not issues:
        summary = (
            "Scene is logically consistent with refinements stabilized. "
            "Objects are well placed and relationships are satisfied."
        )
    elif score >= 0.6:
        summary = (
            "Scene is logically consistent with minor refinements applied. "
            "Most placements and relationships satisfy the blueprint intent."
        )
    else:
        summary = (
            "Scene remains partially consistent after refinement. "
            "Some placement or relationship constraints still need attention."
        )

    details: List[str] = []
    details.append(f"Placement quality score: {placement_score:.3f}")
    details.append(f"Reasoning quality score: {reasoning_score:.3f}")
    details.append(f"Inferred {relation_count} object relationships")

    if overlap_count == 0:
        details.append("No overlapping objects detected")
    else:
        details.append(f"Detected {overlap_count} overlapping object pairs")

    if violations:
        details.append(
            f"Detected {len(violations)} placement issue(s); refinements were applied to improve spacing and bounds"
        )
    else:
        details.append("No placement violations detected")

    chair_desk_relations = sum(1 for _src, rel, _dst in relations if rel == "near")
    facing_relations = sum(1 for _src, rel, _dst in relations if rel == "facing")
    if chair_desk_relations:
        details.append(f"Inferred {chair_desk_relations} chair-desk proximity relationships")
    if facing_relations:
        details.append(f"Inferred {facing_relations} orientation relationships toward the blackboard")

    if issues:
        details.append(f"Detected {len(issues)} reasoning issue(s) during reflection")
    else:
        details.append("Relationship checks passed without reasoning issues")

    return {
        "summary": summary,
        "details": details,
    }


def refine_scene(objects: List[Dict], weight: float = 0.5, eval_result: Dict | None = None) -> List[Dict]:
    current_eval = eval_result if eval_result is not None else evaluate_scene(objects)
    if current_eval["placement_score"] > 0.8 and len(current_eval["violations"]) == 0:
        print("[SKIP] refinement skipped (already optimal)")
        return objects

    refined = [_copy_object(obj) for obj in objects]
    desks = [obj for obj in refined if _is_desk(obj)]
    chairs = [obj for obj in refined if _is_chair(obj)]
    boards = [obj for obj in refined if _is_board(obj)]
    bounded_weight = max(0.0, min(0.5, float(weight)))
    max_step = round(min(MAX_REFINEMENT_STEP * bounded_weight, SAFE_MAX_MOVE), 4)

    for obj in refined:
        pos = obj.setdefault("position", [0.0, 0.0, 0.0])
        pos[0] = _snap_to_grid(pos[0])
        pos[2] = _snap_to_grid(pos[2])

    board = min(boards, key=lambda obj: obj.get("position", [0.0, 0.0, 0.0])[2]) if boards else None

    for chair in chairs:
        desk = _nearest_object(chair, desks)
        if not desk:
            continue
        chair_pos = chair.setdefault("position", [0.0, 0.0, 0.0])
        desk_pos = desk.setdefault("position", [0.0, 0.0, 0.0])
        delta_x = _clamp(desk_pos[0] - chair_pos[0], -SAFE_MAX_MOVE, SAFE_MAX_MOVE)
        delta_z = _clamp((desk_pos[2] + 1.0) - chair_pos[2], -SAFE_MAX_MOVE, SAFE_MAX_MOVE)
        chair_pos[0] = _move_toward(chair_pos[0], chair_pos[0] + delta_x, max_step)
        chair_pos[2] = _move_toward(chair_pos[2], chair_pos[2] + delta_z, max_step)
        rotation = chair.setdefault("rotation", [0.0, 0.0, 0.0])
        rotation[1] = _yaw_to_target(chair, desk)

    if board:
        for desk in desks:
            rotation = desk.setdefault("rotation", [0.0, 0.0, 0.0])
            rotation[1] = _yaw_to_target(desk, board)

    new_eval = evaluate_scene(refined)
    if new_eval["placement_score"] < current_eval["placement_score"]:
        print("[REJECT] refinement reduced quality, reverting")
        return objects

    return refined


def _copy_object(obj: Dict) -> Dict:
    copied = dict(obj)
    if "position" in copied:
        copied["position"] = list(copied["position"])
    if "rotation" in copied:
        copied["rotation"] = list(copied["rotation"])
    if "scale" in copied:
        copied["scale"] = list(copied["scale"])
    return copied


def _distance(obj1: Dict, obj2: Dict) -> float:
    x1, _y1, z1 = obj1.get("position", [0.0, 0.0, 0.0])
    x2, _y2, z2 = obj2.get("position", [0.0, 0.0, 0.0])
    return math.hypot(x1 - x2, z1 - z2)


def _nearest_object(source: Dict, candidates: List[Dict]):
    if not candidates:
        return None
    return min(candidates, key=lambda candidate: _distance(source, candidate))


def _is_chair(obj: Dict) -> bool:
    return "chair" in str(obj.get("name", "")).lower()


def _is_desk(obj: Dict) -> bool:
    lower = str(obj.get("name", "")).lower()
    return "desk" in lower or "table" in lower


def _is_board(obj: Dict) -> bool:
    lower = str(obj.get("name", "")).lower()
    return "board" in lower


def _snap_to_grid(value: float, step: float = GRID_STEP) -> float:
    return round(round(value / step) * step, 4)


def _move_toward(current: float, target: float, max_step: float) -> float:
    delta = target - current
    if abs(delta) <= max_step:
        return round(target, 4)
    return round(current + math.copysign(max_step, delta), 4)


def _clamp(value: float, lower: float, upper: float) -> float:
    return max(lower, min(upper, value))


def _yaw_to_target(source: Dict, target: Dict) -> float:
    sx, _sy, sz = source.get("position", [0.0, 0.0, 0.0])
    tx, _ty, tz = target.get("position", [0.0, 0.0, 0.0])
    angle = math.degrees(math.atan2(tx - sx, tz - sz))
    return round(angle, 3)


def _faces_target(source: Dict, target: Dict, tolerance_degrees: float = 35.0) -> bool:
    rotation = source.get("rotation", [0.0, 0.0, 0.0])
    current_yaw = float(rotation[1]) if len(rotation) > 1 else 0.0
    desired_yaw = _yaw_to_target(source, target)
    delta = (current_yaw - desired_yaw + 180.0) % 360.0 - 180.0
    return abs(delta) <= tolerance_degrees
