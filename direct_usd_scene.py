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


def build_scene_from_prompt(prompt: str, save_path: Optional[str] = None, mode: str = "ai") -> List[Dict]:
    stage = Usd.Stage.CreateInMemory()
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.y)
    stage.SetMetadata("metersPerUnit", 0.01)
    UsdGeom.Xform.Define(stage, "/World")
    stage.SetDefaultPrim(stage.GetPrimAtPath("/World"))

    scene_graph = generate_scene(prompt, mode=mode)

    name_counts: Dict[str, int] = {}
    resolved_assets: Dict[str, Optional[Dict]] = {}
    for item in scene_graph:
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

        if asset_spec and asset_spec.get("asset_path"):
            asset_path = str(asset_spec["asset_path"])
            prim_path_ref = str(asset_spec.get("prim_path", ""))
            prim.GetReferences().AddReference(
                assetPath=asset_path,
                primPath=Sdf.Path(prim_path_ref) if prim_path_ref else Sdf.Path.emptyPath,
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

        xformable = UsdGeom.Xformable(prim)
        xformable.AddTranslateOp().Set(Gf.Vec3d(x, y, z))
        xformable.AddRotateXYZOp().Set(Gf.Vec3f(*final_rotation))
        xformable.AddScaleOp().Set(Gf.Vec3d(sx, sy, sz))
        print(
            f"[INFO] Placed '{object_name}' pos={item['position']} rot={final_rotation} "
            f"scale={item['scale']} asset={asset_spec.get('source', 'local') if asset_spec else 'placeholder'} "
            f"quality={asset_spec.get('quality_score', 'n/a') if asset_spec else 'n/a'} -> {prim_path}"
        )

    if save_path:
        exported_path = export_stage_safely(stage, save_path)
        print(f"[INFO] Exported stage to file: {Path(exported_path).name}")

    return scene_graph


def main() -> int:
    import os
    import sys

    mode = "ai"
    filtered_args = []
    for arg in sys.argv[1:]:
        if arg.startswith("--mode="):
            mode = arg.split("=", 1)[1].strip() or "ai"
        else:
            filtered_args.append(arg)

    prompt = " ".join(filtered_args).strip() or "a medieval classroom with wooden desks"
    save_path = os.path.abspath("generated_scene.usda")
    build_scene_from_prompt(prompt=prompt, save_path=save_path, mode=mode)
    print("[INFO] Scene generation completed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
