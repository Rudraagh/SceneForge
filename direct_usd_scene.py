"""
Direct USD scene builder that does not depend on Omniverse Kit runtime.

This is used as a robust local fallback when Kit-based scene editing/export is
unreliable on the current machine or path.
"""

from __future__ import annotations

import re
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from pxr import Gf, Sdf, Usd, UsdGeom

from ai_scene_graph import generate_scene
from objaverse_loader import find_asset


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_REFERENCE_SCALE = 0.3
GROUND_EPSILON = 0.02
STRICT_BLUEPRINT_MODE = True
OBJECT_SCALE_MAP = {
    "chair": 0.4,
    "table": 1.0,
    "wooden_desk": 1.0,
    "blackboard": 1.0,
    "bookshelf": 1.0,
    "lamp": 1.0,
}
OBJECT_TARGET_SIZE_MAP = {
    "chair": [0.9, 1.0, 0.9],
    "table": [1.4, 0.8, 0.8],
    "wooden_desk": [1.4, 0.8, 0.8],
    "blackboard": [2.2, 1.2, 0.12],
    "bookshelf": [1.2, 1.8, 0.45],
    "lamp": [0.45, 1.2, 0.45],
}


def sanitize_name(name: str) -> str:
    token = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
    if not token:
        token = "Object"
    if token[0].isdigit():
        token = f"_{token}"
    return token


def normalize_rotation_degrees(values: List[float]) -> List[float]:
    normalized = []
    for value in values:
        angle = float(value) % 360.0
        if angle > 180.0:
            angle -= 360.0
        if abs(angle) < 1e-4:
            angle = 0.0
        normalized.append(angle)
    return normalized


def _normalized_scale_override(object_name: str, asset_spec: Optional[Dict], authored_scale: List[float]) -> List[float]:
    base_scale = OBJECT_SCALE_MAP.get(object_name.lower(), DEFAULT_REFERENCE_SCALE)

    return [
        round(max(1e-6, float(authored_scale[0]) * base_scale), 8),
        round(max(1e-6, float(authored_scale[1]) * base_scale), 8),
        round(max(1e-6, float(authored_scale[2]) * base_scale), 8),
    ]


def _bbox_fit_scale(prim, object_name: str) -> float:
    target_size = OBJECT_TARGET_SIZE_MAP.get(object_name.lower())
    if not target_size:
        return 1.0

    try:
        bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_]).ComputeWorldBound(prim)
        box = bbox.ComputeAlignedBox()
        size = box.GetSize()
        current_size = [float(size[0]), float(size[1]), float(size[2])]
    except Exception:
        return 1.0

    ratios = []
    for current, target in zip(current_size, target_size):
        if current > 1e-6:
            ratios.append(float(target) / float(current))

    return min(ratios) if ratios else 1.0


def create_placeholder_geometry(stage: Usd.Stage, prim_path: str, object_name: str) -> None:
    placeholder_path = Sdf.Path(f"{prim_path}/Placeholder")
    cube = UsdGeom.Cube.Define(stage, placeholder_path)
    cube.CreateSizeAttr(100.0)

    color_attr = cube.GetPrim().CreateAttribute("primvars:displayColor", Sdf.ValueTypeNames.Color3fArray)
    lower = object_name.lower()
    if any(key in lower for key in ("desk", "table", "bench", "crate", "barrel")):
        color = Gf.Vec3f(0.45, 0.28, 0.12)
    elif any(key in lower for key in ("chair", "banner")):
        color = Gf.Vec3f(0.2, 0.35, 0.75)
    elif any(key in lower for key in ("tree", "campfire", "board", "planet", "sun", "earth", "mars", "venus", "mercury", "jupiter", "saturn", "uranus", "neptune")):
        color = Gf.Vec3f(0.10, 0.35, 0.10)
    else:
        color = Gf.Vec3f(0.7, 0.7, 0.7)
    color_attr.Set([color])


def add_room_shell(stage: Usd.Stage, graph: Dict) -> None:
    layout = graph.get("layout", {})
    room = layout.get("room", {})
    if room:
        width = float(room.get("width", 12.0))
        depth = float(room.get("depth", 12.0))
    else:
        nodes = graph.get("nodes", [])
        if nodes:
            xs = [float(node.get("position", [0.0, 0.0, 0.0])[0]) for node in nodes]
            zs = [float(node.get("position", [0.0, 0.0, 0.0])[2]) for node in nodes]
            width = max(12.0, (max(xs) - min(xs)) + 8.0)
            depth = max(12.0, (max(zs) - min(zs)) + 8.0)
        else:
            width = 12.0
            depth = 12.0
    height = float(room.get("height", 3.0))
    wall_thickness = 0.1

    room_root = UsdGeom.Xform.Define(stage, "/World/Room").GetPrim()

    shell_specs = {
        "Ground": {
            "translate": Gf.Vec3d(0.0, -0.05, 0.0),
            "scale": Gf.Vec3d(width, 0.1, depth),
            "color": Gf.Vec3f(0.55, 0.55, 0.55),
        },
        "WallNorth": {
            "translate": Gf.Vec3d(0.0, height / 2.0, -depth / 2.0),
            "scale": Gf.Vec3d(width, height, wall_thickness),
            "color": Gf.Vec3f(0.88, 0.88, 0.9),
        },
        "WallSouth": {
            "translate": Gf.Vec3d(0.0, height / 2.0, depth / 2.0),
            "scale": Gf.Vec3d(width, height, wall_thickness),
            "color": Gf.Vec3f(0.88, 0.88, 0.9),
        },
        "WallWest": {
            "translate": Gf.Vec3d(-width / 2.0, height / 2.0, 0.0),
            "scale": Gf.Vec3d(wall_thickness, height, depth),
            "color": Gf.Vec3f(0.9, 0.9, 0.92),
        },
        "WallEast": {
            "translate": Gf.Vec3d(width / 2.0, height / 2.0, 0.0),
            "scale": Gf.Vec3d(wall_thickness, height, depth),
            "color": Gf.Vec3f(0.9, 0.9, 0.92),
        },
    }

    for name, spec in shell_specs.items():
        prim_path = f"{room_root.GetPath()}/{name}"
        cube = UsdGeom.Cube.Define(stage, prim_path)
        cube.CreateSizeAttr(1.0)
        color_attr = cube.GetPrim().CreateAttribute("primvars:displayColor", Sdf.ValueTypeNames.Color3fArray)
        color_attr.Set([spec["color"]])

        xformable = UsdGeom.Xformable(cube.GetPrim())
        xformable.AddTranslateOp().Set(spec["translate"])
        xformable.AddScaleOp().Set(spec["scale"])


def export_stage_safely(stage: Usd.Stage, save_path: str) -> str:
    target_path = Path(save_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    safe_dir = Path(tempfile.gettempdir()) / "omniverse_scene_exports"
    safe_dir.mkdir(parents=True, exist_ok=True)
    safe_path = safe_dir / target_path.name

    ok = stage.GetRootLayer().Export(str(safe_path))
    if not ok or not safe_path.exists():
        raise RuntimeError(f"Failed to export USD stage to temporary path: {safe_path}")
    shutil.copyfile(safe_path, target_path)
    return str(target_path)


def build_scene_from_prompt(
    prompt: str,
    save_path: Optional[str] = None,
    mode: str = "ai",
    blueprint_mode: bool = False,
) -> List[Dict]:
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    stage.SetMetadata("metersPerUnit", 0.01)
    UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(stage.GetPrimAtPath("/World"))

    from blueprint_mapper import map_blueprint_to_scene, merge_blueprint_positions
    from blueprint_parser import parse_blueprint_or_empty

    blueprint_path = Path("blueprint.png")
    print(f"[BLUEPRINT] Checking file: {blueprint_path.resolve()}")
    print(f"[BLUEPRINT] File exists: {blueprint_path.exists()}")
    blueprint_data = parse_blueprint_or_empty("blueprint.png", prompt)
    print(f"[BLUEPRINT] Parsed data: {blueprint_data}")
    if blueprint_mode and STRICT_BLUEPRINT_MODE and blueprint_data:
        print("[INFO] deterministic_mode=True")
        from blueprint_agents import (
            adaptive_controller,
            compute_score,
            evaluate_scene,
            explain_scene,
            infer_relationships,
            reflect_scene,
            refine_scene,
        )

        def _compute_total_movement(old_objects: List[Dict], new_objects: List[Dict]) -> float:
            total = 0.0
            for old_obj, new_obj in zip(old_objects, new_objects):
                ox, _oy, oz = old_obj.get("position", [0.0, 0.0, 0.0])
                nx, _ny, nz = new_obj.get("position", [0.0, 0.0, 0.0])
                dx = ox - nx
                dz = oz - nz
                total += (dx ** 2 + dz ** 2) ** 0.5
            return total

        MOVEMENT_EPSILON = 0.01

        scene = map_blueprint_to_scene(blueprint_data)
        initial_count = len(scene)
        prev_score = 0.0
        score_history = []
        movement_history = []
        refinement_flag = False
        eval_result = {"placement_score": 0.0, "violations": []}
        relations = []
        reflect_result = {"reasoning_score": 0.0, "issues": []}
        score = 0.0

        i = 0
        while True:
            if len(scene) != initial_count:
                raise RuntimeError("Object count changed during refinement!")

            eval_result = evaluate_scene(scene)
            relations = infer_relationships(scene)
            reflect_result = reflect_scene(scene, relations)
            score = compute_score(
                T=eval_result["placement_score"],
                M=reflect_result["reasoning_score"],
                C=len(eval_result["violations"]),
            )
            score_history.append(round(score, 3))

            violation_count = len(eval_result["violations"])
            print(f"[ITER {i}] score={score:.2f} violations={violation_count}")

            controller = adaptive_controller(prev_score, score, violation_count, i)
            print(
                f"[CONTROL] threshold={controller['threshold']:.2f} "
                f"refine={controller['refinement_weight']}"
            )

            if score >= controller["threshold"]:
                print("[STOP] adaptive threshold reached")
                break

            if not controller["continue"]:
                print("[STOP] controller halted iteration")
                break

            previous_scene = scene
            refined_scene = refine_scene(
                scene,
                weight=controller["refinement_weight"],
                eval_result=eval_result,
            )
            if len(refined_scene) != initial_count:
                raise RuntimeError("Object count changed during refinement!")

            movement = _compute_total_movement(previous_scene, refined_scene)
            movement_history.append(round(movement, 4))
            print(f"[MOVEMENT] iter={i} total={movement:.4f}")
            if movement > 0:
                refinement_flag = True

            if i > 1 and abs(prev_score - score) < 0.005 and movement > 0.1:
                print("[WARN] possible oscillation detected")

            if movement < MOVEMENT_EPSILON:
                scene = refined_scene
                print("[STOP] movement converged")
                break

            prev_score = score
            scene = refined_scene
            i += 1

        print(f"[BLUEPRINT] Strict blueprint mode enabled. Using blueprint objects only.")
        print(f"[BLUEPRINT FINAL] placing {len(scene)} objects")
        print(f"[AGENT EVAL] objects={len(scene)} violations={len(eval_result['violations'])}")
        print(f"[AGENT REL] inferred_relations={len(relations)}")
        print(f"[AGENT REFLECT] issues={len(reflect_result['issues'])}")
        print(f"[AGENT SCORE] {round(score, 3)}")
        print(f"[FINAL] score={score:.3f} iterations={i + 1}")
        print(f"[TREND] {score_history}")
        if len(score_history) > 1:
            delta = score_history[-1] - score_history[0]
            print(f"[IMPROVEMENT] delta={delta:.3f}")
        print(f"[MOVEMENT_TREND] {movement_history}")
        if refinement_flag:
            print("[INFO] refinement_applied=True")
        else:
            print("[INFO] refinement_applied=False")
        print(
            f"[RESULT] score={score:.3f} | objects={len(scene)} | "
            f"violations={len(eval_result['violations'])} | iterations={i + 1}"
        )
        explanation = explain_scene(eval_result, reflect_result, relations, score)
        print("[EXPLAIN] " + explanation["summary"])
        for line in explanation["details"]:
            print("[DETAIL] " + line)
    else:
        scene = generate_scene(prompt)
        if blueprint_data:
            blueprint_scene = map_blueprint_to_scene(blueprint_data)
            scene = merge_blueprint_positions(scene, blueprint_scene)
            print(f"[BLUEPRINT] Applied blueprint positions: {blueprint_scene}")
            print(f"[BLUEPRINT FINAL] placing {len(scene)} objects")
        else:
            print("[BLUEPRINT] No blueprint data found. Using existing layout flow.")

    from relations import extract_relations
    from relation_infer import infer_relations
    from ai_scene_graph import build_graph

    relations = extract_relations(prompt)

    if not relations:
        relations = infer_relations(prompt)

    graph = build_graph(scene, relations)

    if blueprint_mode and STRICT_BLUEPRINT_MODE and blueprint_data:
        print("[BLUEPRINT] Skipping layout engine and agents in strict blueprint mode.")
    else:
        from agents import domain_agent, evaluator_agent

        graph = __import__("layout_engine").arrange_classroom_layout(graph)

        # 🔁 Multi-agent loop (SAFE)
        for _ in range(5):
            graph = domain_agent(graph)
            score = evaluator_agent(graph)

            print(f"[AGENT] score = {score}")

            if score > 0.7:
                break

    add_room_shell(stage, graph)

    name_counts: Dict[str, int] = {}
    resolved_assets: Dict[str, Optional[Dict]] = {}
    for item in graph["nodes"]:
        object_name = item["name"]
        x, y, z = item["position"]
        rx, ry, rz = item["rotation"]
        sx, sy, sz = item["scale"]

        if object_name not in resolved_assets:
            resolved_assets[object_name] = find_asset(object_name)
        asset_spec = resolved_assets[object_name]

        base_name = sanitize_name(object_name)
        name_counts[base_name] = name_counts.get(base_name, 0) + 1
        prim_name = f"{base_name}_{name_counts[base_name]}"
        prim_path = f"/World/{prim_name}"

        xform = UsdGeom.Xform.Define(stage, prim_path)
        prim = xform.GetPrim()
        asset_prim_path = f"{prim_path}/Asset"
        asset_prim = UsdGeom.Xform.Define(stage, asset_prim_path).GetPrim()

        if asset_spec and asset_spec.get("asset_path"):
            asset_path = str(asset_spec["asset_path"])
            prim_path_ref = str(asset_spec.get("prim_path", ""))
            asset_prim.GetReferences().AddReference(
                asset_path,
                Sdf.Path(prim_path_ref) if prim_path_ref else Sdf.Path.emptyPath,
            )
        else:
            create_placeholder_geometry(stage, prim_path, object_name)

        rotation_offset = asset_spec.get("rotation_offset", [0.0, 0.0, 0.0]) if asset_spec else [0.0, 0.0, 0.0]
        final_rotation = normalize_rotation_degrees(
            [
                rx + float(rotation_offset[0]),
                ry + float(rotation_offset[1]),
                rz + float(rotation_offset[2]),
            ]
        )
        if "chair" in object_name.lower():
            final_rotation = normalize_rotation_degrees(
                [final_rotation[0], final_rotation[1] + 180.0, final_rotation[2]]
            )
        final_scale = _normalized_scale_override(object_name, asset_spec, [sx, sy, sz])
        final_position = [x, y + GROUND_EPSILON, z]

        xformable = UsdGeom.Xformable(prim)
        xformable.AddTranslateOp().Set(Gf.Vec3d(*final_position))
        xformable.AddRotateXYZOp().Set(Gf.Vec3f(*final_rotation))
        if asset_spec and asset_spec.get("asset_path"):
            xformable.AddScaleOp().Set(Gf.Vec3d(1.0, 1.0, 1.0))
            asset_xformable = UsdGeom.Xformable(asset_prim)
            bbox_fit = _bbox_fit_scale(asset_prim, object_name)
            asset_scale = [
                round(final_scale[0] * bbox_fit, 8),
                round(final_scale[1] * bbox_fit, 8),
                round(final_scale[2] * bbox_fit, 8),
            ]
            asset_xformable.AddScaleOp().Set(Gf.Vec3d(*asset_scale))
        else:
            xformable.AddScaleOp().Set(Gf.Vec3d(*final_scale))
            asset_scale = final_scale
        print(
            f"[INFO] Placed '{object_name}' final_pos={final_position} rot={final_rotation} "
            f"final_scale={asset_scale} asset={asset_spec.get('source', 'local') if asset_spec else 'placeholder'} "
            f"quality={asset_spec.get('quality_score', 'n/a') if asset_spec else 'n/a'} -> {prim_path}"
        )

    if save_path:
        exported_path = export_stage_safely(stage, save_path)
        print(f"[INFO] Exported stage to file: {Path(exported_path).name}")

    return graph

def main() -> int:
    import os
    import sys

    mode = "ai"
    blueprint_mode = False
    filtered_args = []
    for arg in sys.argv[1:]:
        if arg == "-b":
            blueprint_mode = True
            continue
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1].strip() or "ai"
        else:
            filtered_args.append(arg)

    prompt = " ".join(filtered_args).strip() or "a medieval classroom with wooden desks"
    print(f"[INFO] Blueprint mode: {blueprint_mode}")
    save_path = os.path.abspath("generated_scene.usda")
    build_scene_from_prompt(prompt=prompt, save_path=save_path, mode=mode, blueprint_mode=blueprint_mode)
    print("[INFO] Scene generation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
