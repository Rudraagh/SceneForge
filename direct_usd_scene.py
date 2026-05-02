"""
Direct USD scene builder that does not depend on Omniverse Kit runtime.

This is used as a robust local fallback when Kit-based scene editing/export is
unreliable on the current machine or path.
"""

from __future__ import annotations

import argparse
import copy
import os
import re
import math
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from pxr import Gf, Sdf, Usd, UsdGeom

from ai_scene_graph import (
    classify_scene,
    detect_scene_type,
    enrich_graph_with_relations,
    generate_minimal_scene,
    generate_rule_scene,
    generate_scene,
    generate_solar_system_scene,
    is_valid_scene,
    score_layout,
)
from sceneforge.asset_registry import find_asset
from sceneforge.config import get_config
from sceneforge.logging_utils import configure_logging


PROJECT_ROOT = get_config().project_root
DEFAULT_REFERENCE_SCALE = 0.3
GROUND_EPSILON = 0.02
STRICT_BLUEPRINT_MODE = True
OBJECT_SCALE_MAP = {
    "chair": 0.4,
    "table": 1.0,
    "wooden_desk": 1.0,
    "blackboard": 2.0,
    "bookshelf": 1.0,
    "lamp": 1.0,
    "door": 0.35,
    "clock": 1.0,
    "throne": 0.75,
    "banner": 0.7,
    "torch": 0.9,
    "bench": 0.55,
    "pine_tree": 0.35,
    "barrel": 0.45,
}
OBJECT_TARGET_SIZE_MAP = {
    "chair": [0.9, 1.0, 0.9],
    "table": [1.4, 0.8, 0.8],
    "wooden_desk": [1.4, 0.8, 0.8],
    "blackboard": [2.2, 1.2, 0.12],
    "bookshelf": [1.2, 1.8, 0.45],
    "lamp": [0.45, 1.2, 0.45],
    "door": [1.0, 2.05, 0.12],
    "clock": [1.2, 1.2, 0.2],
    "throne": [1.7, 2.2, 1.45],
    "banner": [0.95, 2.6, 0.18],
    "torch": [0.4, 1.6, 0.4],
    "bench": [2.25, 0.72, 0.78],
    "pine_tree": [1.2, 3.5, 1.2],
    "barrel": [0.65, 0.95, 0.65],
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


def _base_object_name(name: str) -> str:
    return re.sub(r"_\d+$", "", str(name or "").lower())


def _normalized_scale_override(object_name: str, asset_spec: Optional[Dict], authored_scale: List[float]) -> List[float]:
    base_name = _base_object_name(object_name)
    if base_name in OBJECT_SCALE_MAP:
        base_scale = OBJECT_SCALE_MAP[base_name]
    elif asset_spec and asset_spec.get("asset_path"):
        base_scale = 1.0
    else:
        base_scale = DEFAULT_REFERENCE_SCALE

    return [
        round(max(1e-6, float(authored_scale[0]) * base_scale), 8),
        round(max(1e-6, float(authored_scale[1]) * base_scale), 8),
        round(max(1e-6, float(authored_scale[2]) * base_scale), 8),
    ]


def _bbox_fit_scale(prim, object_name: str) -> float:
    target_size = OBJECT_TARGET_SIZE_MAP.get(_base_object_name(object_name))
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


def _count_spacing_violations(nodes: List[Dict], min_distance: float = 0.5) -> int:
    violations = 0
    for index, node in enumerate(nodes):
        ax, _ay, az = [float(value) for value in node.get("position", [0.0, 0.0, 0.0])]
        for other in nodes[index + 1 :]:
            bx, _by, bz = [float(value) for value in other.get("position", [0.0, 0.0, 0.0])]
            if math.hypot(ax - bx, az - bz) < min_distance:
                violations += 1
    return violations


def _print_run_summary(graph: Dict, score: float, violations: int, iterations: int, selected_mode: str) -> None:
    nodes = graph.get("nodes", [])
    print(
        f"[RESULT] score={score:.3f} | objects={len(nodes)} | "
        f"violations={violations} | iterations={iterations}"
    )
    print(f"[EXPLAIN] Generated {len(nodes)} objects using {selected_mode} mode.")
    print(f"[DETAIL] Layout score: {score:.3f}")
    print(f"[DETAIL] Spacing violations: {violations}")


def _refresh_graph_lookup(graph: Dict) -> None:
    graph["lookup"] = {
        str(node.get("name", "")): node
        for node in graph.get("nodes", [])
        if str(node.get("name", "")).strip()
    }


def _complexity_penalty(eval_result: Dict, node_count: int) -> float:
    base = int(eval_result.get("overlap_count", 0)) + len(eval_result.get("violations", []))
    denom = max(1, int(node_count))
    return round(min(1.0, base / denom), 3)


def _run_multi_agent_refinement(graph: Dict, prompt: str, scene_type: str = "") -> tuple[Dict, float, int]:
    from agents import domain_agent, evaluator_agent, evaluator_agent_diagnostics, reflection_agent
    from blueprint_agents import (
        adaptive_controller,
        compute_score,
        evaluate_scene as evaluate_blueprint_scene,
        explain_scene,
        infer_relationships,
        reflect_scene,
        refine_scene,
    )
    import layout_engine

    if scene_type == "classroom" or layout_engine.is_classroom_graph(graph, prompt):
        graph = layout_engine.arrange_classroom_layout(graph)
        print("[LAYOUT] Applied classroom layout engine.")
    elif scene_type == "throne_room" or layout_engine.is_throne_room_graph(graph, prompt):
        graph = layout_engine.arrange_throne_room_layout(graph)
        print("[LAYOUT] Applied throne room layout engine.")
    elif scene_type == "solar_system" or layout_engine.is_solar_system_graph(graph, prompt):
        graph = layout_engine.arrange_solar_system_layout(graph)
        print("[LAYOUT] Applied solar system layout engine.")
    elif layout_engine.has_blueprint_positions(graph):
        graph = layout_engine.arrange_blueprint_layout(graph)
        print("[LAYOUT] Applied blueprint-anchored layout.")
    else:
        graph = layout_engine.arrange_semantic_layout(graph, prompt=prompt, scene_type=scene_type)
        print("[LAYOUT] Applied semantic layout engine.")

    _refresh_graph_lookup(graph)

    best_graph = copy.deepcopy(graph)
    best_score = evaluator_agent(graph)
    prev_score = best_score
    iterations = 0

    for iteration in range(1, 6):
        graph = domain_agent(graph)
        _refresh_graph_lookup(graph)

        diagnostics = evaluator_agent_diagnostics(graph)
        layout_score = diagnostics["score"]
        reflection = reflection_agent(graph)

        relations = infer_relationships(graph.get("nodes", []))
        eval_result = evaluate_blueprint_scene(graph.get("nodes", []))
        reflect_result = reflect_scene(graph.get("nodes", []), relations)
        penalty = _complexity_penalty(eval_result, len(graph.get("nodes", [])))
        adaptive_score = compute_score(
            float(eval_result.get("placement_score", 0.0)),
            float(reflect_result.get("reasoning_score", 0.0)),
            penalty,
        )
        summary = explain_scene(eval_result, reflect_result, relations, adaptive_score)
        control = adaptive_controller(prev_score, layout_score, len(eval_result.get("violations", [])), iteration)

        iterations = iteration
        print(
            "[AGENT] "
            f"iter={iteration} layout_score={layout_score:.3f} "
            f"spacing={diagnostics['spacing_score']:.3f} "
            f"bounds={diagnostics['bounds_score']:.3f} "
            f"relation={diagnostics['relation_score']:.3f} "
            f"placement={eval_result.get('placement_score', 0.0):.3f} "
            f"reasoning={reflect_result.get('reasoning_score', 0.0):.3f} "
            f"penalty={penalty:.3f}"
        )
        print(f"[REFLECT] {reflection}")
        print(f"[REFLECT] {summary['summary']}")
        if summary.get("details"):
            print(f"[DETAIL] {summary['details'][0]}")

        if layout_score >= best_score:
            best_score = layout_score
            best_graph = copy.deepcopy(graph)

        if layout_score >= control["threshold"]:
            print(f"[CONTROL] Stop: score {layout_score:.3f} reached threshold {control['threshold']:.3f}.")
            break

        if not control["continue"]:
            print("[CONTROL] Stop: improvement plateau or iteration limit reached.")
            break

        graph["nodes"] = refine_scene(
            graph.get("nodes", []),
            weight=control["refinement_weight"],
            eval_result=eval_result,
        )
        _refresh_graph_lookup(graph)
        prev_score = layout_score

    return best_graph, best_score, iterations


def _should_run_layout_and_agents(selected_mode: str, scene_type: str, blueprint_mode: bool, blueprint_data: List[Dict]) -> bool:
    if selected_mode != "deterministic":
        return True
    if blueprint_mode and blueprint_data:
        return True
    return False


def _should_add_room_shell(scene_type: str, selected_mode: str, graph: Dict) -> bool:
    if scene_type == "solar_system":
        return False
    if selected_mode != "deterministic":
        return True
    return bool(graph.get("layout")) or scene_type == "classroom"


def create_placeholder_geometry(stage: Usd.Stage, prim_path: str, object_name: str) -> None:
    placeholder_path = Sdf.Path(f"{prim_path}/Placeholder")
    cube = UsdGeom.Cube.Define(stage, placeholder_path)
    cube.CreateSizeAttr(100.0)

    color_attr = cube.GetPrim().CreateAttribute("primvars:displayColor", Sdf.ValueTypeNames.Color3fArray)
    lower = object_name.lower()
    if any(key in lower for key in ("desk", "table", "bench", "crate", "barrel")):
        color = Gf.Vec3f(0.45, 0.28, 0.12)
    elif "door" in lower:
        color = Gf.Vec3f(0.22, 0.22, 0.28)
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
    bounds = layout.get("bounds", {})
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
    if bounds:
        center_x = float(bounds.get("center_x", 0.0))
        center_z = float(bounds.get("center_z", 0.0))
    else:
        center_x = 0.0
        center_z = 0.0

    room_root = UsdGeom.Xform.Define(stage, "/World/Room").GetPrim()

    shell_specs = {
        "Ground": {
            "translate": Gf.Vec3d(center_x, -0.05, center_z),
            "scale": Gf.Vec3d(width, 0.1, depth),
            "color": Gf.Vec3f(0.55, 0.55, 0.55),
        },
        "WallNorth": {
            "translate": Gf.Vec3d(center_x, height / 2.0, center_z - (depth / 2.0)),
            "scale": Gf.Vec3d(width, height, wall_thickness),
            "color": Gf.Vec3f(0.88, 0.88, 0.9),
        },
        "WallSouth": {
            "translate": Gf.Vec3d(center_x, height / 2.0, center_z + (depth / 2.0)),
            "scale": Gf.Vec3d(width, height, wall_thickness),
            "color": Gf.Vec3f(0.88, 0.88, 0.9),
        },
        "WallWest": {
            "translate": Gf.Vec3d(center_x - (width / 2.0), height / 2.0, center_z),
            "scale": Gf.Vec3d(wall_thickness, height, depth),
            "color": Gf.Vec3f(0.9, 0.9, 0.92),
        },
        "WallEast": {
            "translate": Gf.Vec3d(center_x + (width / 2.0), height / 2.0, center_z),
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


def add_solar_system_guides(stage: Usd.Stage, graph: Dict) -> None:
    nodes = graph.get("nodes", [])
    lookup = {str(node.get("name", "")): node for node in nodes}
    sun = lookup.get("sun")
    if not sun:
        return

    sun_x, sun_y, sun_z = [float(value) for value in sun.get("position", [0.0, 0.0, 0.0])]
    guide_root = UsdGeom.Xform.Define(stage, "/World/SolarSystemGuides").GetPrim()

    for node in nodes:
        name = str(node.get("name", ""))
        if name == "sun":
            continue
        x, _y, z = [float(value) for value in node.get("position", [0.0, 0.0, 0.0])]
        radius = max(0.1, math.hypot(x - sun_x, z - sun_z))
        points = []
        segments = 128
        for index in range(segments + 1):
            angle = (index / segments) * math.tau
            points.append(Gf.Vec3f(float(sun_x + math.cos(angle) * radius), float(sun_y - 0.04), float(sun_z + math.sin(angle) * radius)))
        curve = UsdGeom.BasisCurves.Define(stage, f"{guide_root.GetPath()}/{sanitize_name(name)}_Orbit")
        curve.CreateTypeAttr().Set(UsdGeom.Tokens.linear)
        curve.CreateCurveVertexCountsAttr([len(points)])
        curve.CreatePointsAttr(points)
        curve.CreateWidthsAttr([0.035])
        color_attr = curve.GetPrim().CreateAttribute("primvars:displayColor", Sdf.ValueTypeNames.Color3fArray)
        color_attr.Set([Gf.Vec3f(0.38, 0.48, 0.70)])

    star_root = UsdGeom.Xform.Define(stage, f"{guide_root.GetPath()}/Stars").GetPrim()
    for index in range(48):
        angle = index * 2.399963
        radius = 22.0 + (index % 9) * 1.7
        height = -3.0 + (index % 7) * 1.15
        star = UsdGeom.Sphere.Define(stage, f"{star_root.GetPath()}/Star_{index + 1}")
        star.CreateRadiusAttr(0.035 + (index % 3) * 0.015)
        star.GetPrim().CreateAttribute("primvars:displayColor", Sdf.ValueTypeNames.Color3fArray).Set([Gf.Vec3f(0.9, 0.92, 1.0)])
        UsdGeom.Xformable(star.GetPrim()).AddTranslateOp().Set(
            Gf.Vec3d(float(math.cos(angle) * radius), float(height), float(math.sin(angle) * radius))
        )


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
    blueprint_path: str = "blueprint.png",
) -> List[Dict]:
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    stage.SetMetadata("metersPerUnit", 0.01)
    UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(stage.GetPrimAtPath("/World"))

    scene_type, selected_mode = classify_scene(prompt)
    if mode == "rule":
        selected_mode = "deterministic"
    print(f"[CLASSIFIER] scene_type={scene_type} mode={selected_mode}")
    print(f"[CLASSIFIER] {scene_type} | {selected_mode}")
    print("[PIPELINE] robust fallback enabled")

    solar_relations = []
    blueprint_data = []
    skip_agents = False

    actual_generation_mode = selected_mode

    if selected_mode == "deterministic":
        print("[MODE] Deterministic mode selected")
        skip_agents = True
        if scene_type == "solar_system":
            print("[INFO] Using deterministic solar system generator")
            scene, solar_relations = generate_solar_system_scene()
            actual_generation_mode = "deterministic-solar-system"
            print(f"[SOLAR] planets placed: {len(scene)}")
            print("[SOLAR] deterministic layout used")
        else:
            scene = generate_rule_scene(prompt)
            actual_generation_mode = "deterministic"
            if not is_valid_scene(scene):
                print("[FALLBACK] Rule failed -> using minimal scene")
                scene = generate_minimal_scene()
                actual_generation_mode = "minimal-fallback"
    else:
        print("[MODE] Generative AI mode selected")
        scene = generate_scene(prompt, mode="ai")
        actual_generation_mode = "ai"
        if not is_valid_scene(scene):
            print("[FALLBACK] AI failed -> using rule-based scene")
            scene = generate_rule_scene(prompt)
            actual_generation_mode = "rule-fallback"
        if not is_valid_scene(scene):
            print("[FALLBACK] Rule failed -> using minimal scene")
            scene = generate_minimal_scene()
            actual_generation_mode = "minimal-fallback"

    if blueprint_mode and scene_type != "solar_system":
        from blueprint_mapper import map_blueprint_to_scene, merge_blueprint_positions
        from blueprint_parser import parse_blueprint_or_empty

        blueprint_file = Path(blueprint_path)
        print(f"[BLUEPRINT] Checking file: {blueprint_file.resolve()}")
        print(f"[BLUEPRINT] File exists: {blueprint_file.exists()}")
        blueprint_data = parse_blueprint_or_empty(str(blueprint_file), prompt)
        print(f"[BLUEPRINT] Parsed data: {blueprint_data}")
        if STRICT_BLUEPRINT_MODE and blueprint_data:
            blueprint_scene = map_blueprint_to_scene(blueprint_data)
            scene = blueprint_scene
            print("[BLUEPRINT] Strict blueprint mode enabled. Using blueprint objects only.")
            print(f"[BLUEPRINT FINAL] placing {len(scene)} objects")
        elif blueprint_data:
            blueprint_scene = map_blueprint_to_scene(blueprint_data)
            scene = merge_blueprint_positions(scene, blueprint_scene)
            print(f"[BLUEPRINT] Applied blueprint positions: {blueprint_scene}")
            print(f"[BLUEPRINT FINAL] placing {len(scene)} objects")
        else:
            print("[BLUEPRINT] No blueprint data found. Using template layout only.")
    elif blueprint_mode and scene_type == "solar_system":
        print("[BLUEPRINT] Blueprint not merged for deterministic solar_system scene.")

    if not is_valid_scene(scene):
        print("[FALLBACK] Final validation failed -> using minimal scene")
        scene = generate_minimal_scene()
    print(f"[OBJECTS] count={len(scene)}")

    from ai_scene_graph import build_graph

    graph = build_graph(scene, list(solar_relations))
    graph = enrich_graph_with_relations(graph, prompt, list(solar_relations))
    final_score = score_layout(graph.get("nodes", []))
    iterations = 0

    run_agents = _should_run_layout_and_agents(selected_mode, scene_type, blueprint_mode, blueprint_data)

    if run_agents:
        if selected_mode == "deterministic" and blueprint_mode and blueprint_data and scene_type == "classroom":
            print("[MODE] Deterministic classroom blueprint: running layout engine and refinement agents.")
        graph, final_score, iterations = _run_multi_agent_refinement(graph, prompt, scene_type=scene_type)
    else:
        if selected_mode == "deterministic":
            if blueprint_mode and scene_type != "solar_system" and blueprint_data:
                print("[MODE] Deterministic: blueprint placement applied; layout engine and agents skipped.")
            else:
                print("[MODE] Deterministic: layout engine and agents skipped.")
        elif blueprint_mode and STRICT_BLUEPRINT_MODE and blueprint_data:
            print("[BLUEPRINT] Skipping layout engine and agents in strict blueprint mode.")

    if graph.get("nodes"):
        from agents import evaluator_agent_diagnostics

        final_score = evaluator_agent_diagnostics(graph)["score"]

    violations = _count_spacing_violations(graph.get("nodes", []))
    _print_run_summary(graph, final_score, violations, iterations, actual_generation_mode)

    if scene_type == "solar_system":
        add_solar_system_guides(stage, graph)
    elif _should_add_room_shell(scene_type, selected_mode, graph):
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
        print(f"[INFO] Exported stage path: {exported_path}")

    return graph

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a USD scene from a prompt with optional blueprint and asset-source controls.",
    )
    parser.add_argument("-help", action="help", help=argparse.SUPPRESS)
    parser.add_argument("prompt", nargs="*", help="Scene prompt, for example: a classroom with desks and chairs")
    parser.add_argument("--mode", choices=["ai", "rule"], default="ai", help="Scene graph generation mode.")
    parser.add_argument("-b", "--blueprint", action="store_true", help="Use a blueprint image for placement.")
    parser.add_argument("--blueprint-path", default="blueprint.png", help="Blueprint image path used with --blueprint.")
    parser.add_argument("-o", "--output", default="generated_scene.usda", help="Output USDA path.")
    parser.add_argument(
        "--asset-source-order",
        help="Comma-separated source order using cache,objaverse,free,local,procedural.",
    )
    parser.add_argument("--prefer-local-assets", action="store_true", help="Prefer local assets before external sources.")
    parser.add_argument("--disable-cache", action="store_true", help="Do not reuse normalized asset cache entries.")
    parser.add_argument("--disable-objaverse", action="store_true", help="Skip Objaverse search/download.")
    parser.add_argument("--disable-free", action="store_true", help="Skip curated free-source downloads.")
    parser.add_argument("--disable-procedural", action="store_true", help="Skip procedural fallback assets.")
    parser.add_argument("--objaverse-candidate-limit", type=int, help="Objaverse candidates to inspect per category.")
    parser.add_argument("--objaverse-min-score", type=float, help="Minimum Objaverse quality score.")
    return parser.parse_args()


def apply_asset_env(args: argparse.Namespace) -> None:
    if args.prefer_local_assets and not args.asset_source_order:
        os.environ["SCENE_ASSET_SOURCE_ORDER"] = "local,free,cache,objaverse,procedural"
    elif args.asset_source_order:
        os.environ["SCENE_ASSET_SOURCE_ORDER"] = args.asset_source_order

    for flag_name, env_name in (
        ("disable_cache", "SCENE_DISABLE_CACHE"),
        ("disable_objaverse", "SCENE_DISABLE_OBJAVERSE"),
        ("disable_free", "SCENE_DISABLE_FREE"),
        ("disable_procedural", "SCENE_DISABLE_PROCEDURAL"),
    ):
        if getattr(args, flag_name):
            os.environ[env_name] = "1"

    if args.objaverse_candidate_limit is not None:
        os.environ["OBJAVERSE_CANDIDATE_LIMIT"] = str(max(1, args.objaverse_candidate_limit))
    if args.objaverse_min_score is not None:
        os.environ["OBJAVERSE_MIN_SCORE"] = str(args.objaverse_min_score)


def main() -> int:
    configure_logging()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    args = parse_args()
    apply_asset_env(args)

    prompt = " ".join(args.prompt).strip() or "a medieval classroom with wooden desks"
    print(f"[INFO] Blueprint mode: {args.blueprint}")
    print(f"[INFO] Asset source order: {os.getenv('SCENE_ASSET_SOURCE_ORDER', 'per-object defaults')}")
    save_path = os.path.abspath(args.output)
    build_scene_from_prompt(
        prompt=prompt,
        save_path=save_path,
        mode=args.mode,
        blueprint_mode=args.blueprint,
        blueprint_path=args.blueprint_path,
    )
    print("[INFO] Scene generation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
