"""
Omniverse USD scene builder.

This keeps the existing Omniverse Kit and USD stage-building path intact while
delegating scene graph generation to either:
- `ai_scene_graph.generate_scene(..., mode="ai")`, or
- a deterministic rule layout fallback via `mode="rule"`.
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Dict, List, Optional

from ai_scene_graph import generate_scene
from objaverse_loader import find_asset


PROJECT_ROOT = Path(__file__).resolve().parent


def export_stage_safely(stage, save_path: str) -> str:
    """
    Export via an ASCII-safe temp location first, then copy into the requested
    path. This avoids silent USD export failures on some Unicode Windows paths.
    """
    target_path = Path(save_path).resolve()
    target_path.parent.mkdir(parents=True, exist_ok=True)

    safe_dir = Path(tempfile.gettempdir()) / "omniverse_scene_exports"
    safe_dir.mkdir(parents=True, exist_ok=True)
    safe_path = safe_dir / target_path.name

    exported = stage.GetRootLayer().Export(str(safe_path))
    if not exported or not safe_path.exists():
        raise RuntimeError(f"Failed to export USD stage to temporary path: {safe_path}")

    shutil.copyfile(safe_path, target_path)
    return str(target_path)


def sanitize_name(name: str) -> str:
    import re

    token = re.sub(r"[^a-zA-Z0-9_]", "_", name.strip())
    if not token:
        token = "Object"
    if token[0].isdigit():
        token = f"_{token}"
    return token


def ensure_world(stage):
    from pxr import Sdf, UsdGeom

    world = stage.GetPrimAtPath("/World")
    if not world or not world.IsValid():
        world = UsdGeom.Xform.Define(stage, Sdf.Path("/World")).GetPrim()
    stage.SetDefaultPrim(world)
    return world


def create_xform_if_needed(stage, prim_path: str):
    import omni.kit.commands

    prim = stage.GetPrimAtPath(prim_path)
    if prim and prim.IsValid():
        return prim

    omni.kit.commands.execute(
        "CreatePrim",
        prim_type="Xform",
        prim_path=prim_path,
        select_new_prim=False,
    )
    return stage.GetPrimAtPath(prim_path)


def set_translate(stage, prim_path: str, x: float, y: float, z: float) -> None:
    from pxr import Gf, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    xformable = UsdGeom.Xformable(prim)
    op = None
    for candidate in xformable.GetOrderedXformOps():
        if candidate.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            op = candidate
            break
    if op is None:
        op = xformable.AddTranslateOp()
    op.Set(Gf.Vec3d(x, y, z))


def set_rotate(stage, prim_path: str, rx: float, ry: float, rz: float) -> None:
    from pxr import Gf, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    xformable = UsdGeom.Xformable(prim)
    op = None
    for candidate in xformable.GetOrderedXformOps():
        if candidate.GetOpType() == UsdGeom.XformOp.TypeRotateXYZ:
            op = candidate
            break
    if op is None:
        op = xformable.AddRotateXYZOp()
    op.Set(Gf.Vec3f(rx, ry, rz))


def set_scale(stage, prim_path: str, sx: float, sy: float, sz: float) -> None:
    from pxr import Gf, UsdGeom

    prim = stage.GetPrimAtPath(prim_path)
    xformable = UsdGeom.Xformable(prim)
    op = None
    for candidate in xformable.GetOrderedXformOps():
        if candidate.GetOpType() == UsdGeom.XformOp.TypeScale:
            op = candidate
            break
    if op is None:
        op = xformable.AddScaleOp()
    op.Set(Gf.Vec3d(sx, sy, sz))


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


def asset_exists(asset_path: str) -> bool:
    import omni.client

    local_path = Path(asset_path)
    if local_path.exists():
        return True

    try:
        result, _entry = omni.client.stat(asset_path)
        return result == omni.client.Result.OK
    except Exception:
        return False


def create_placeholder_geometry(stage, prim_path: str, object_name: str) -> None:
    from pxr import Gf, Sdf, UsdGeom

    placeholder_path = Sdf.Path(f"{prim_path}/Placeholder")
    cube = UsdGeom.Cube.Define(stage, placeholder_path)
    cube.CreateSizeAttr(100.0)

    color_attr = cube.GetPrim().CreateAttribute("primvars:displayColor", Sdf.ValueTypeNames.Color3fArray)
    lower = object_name.lower()
    if any(key in lower for key in ("desk", "table", "bench", "crate", "barrel")):
        color = Gf.Vec3f(0.45, 0.28, 0.12)
    elif any(key in lower for key in ("chair", "banner")):
        color = Gf.Vec3f(0.2, 0.35, 0.75)
    elif any(key in lower for key in ("tree", "campfire", "board")):
        color = Gf.Vec3f(0.10, 0.35, 0.10)
    else:
        color = Gf.Vec3f(0.7, 0.7, 0.7)
    color_attr.Set([color])


def build_scene_from_prompt(prompt: str, save_path: Optional[str] = None, mode: str = "ai") -> List[Dict]:
    import omni.kit.commands
    import omni.usd
    from pxr import Sdf

    usd_context = omni.usd.get_context()
    if not usd_context.new_stage():
        raise RuntimeError("Failed to create a new USD stage.")

    stage = usd_context.get_stage()
    if stage is None:
        raise RuntimeError("Omniverse returned no active stage.")

    ensure_world(stage)
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

        create_xform_if_needed(stage, prim_path)

        if asset_spec and asset_exists(str(asset_spec["asset_path"])):
            omni.kit.commands.execute(
                "AddReference",
                stage=stage,
                prim_path=Sdf.Path(prim_path),
                reference=Sdf.Reference(
                    assetPath=str(asset_spec["asset_path"]),
                    primPath=Sdf.Path(str(asset_spec["prim_path"])) if asset_spec.get("prim_path") else Sdf.Path.emptyPath,
                ),
            )
        else:
            print(f"[WARN] Asset unavailable for '{object_name}', creating placeholder geometry.")
            create_placeholder_geometry(stage, prim_path, object_name)

        rotation_offset = asset_spec.get("rotation_offset", [0.0, 0.0, 0.0]) if asset_spec else [0.0, 0.0, 0.0]
        final_rotation = normalize_rotation_degrees([
            rx + float(rotation_offset[0]),
            ry + float(rotation_offset[1]),
            rz + float(rotation_offset[2]),
        ])
        set_translate(stage, prim_path, x, y, z)
        set_rotate(stage, prim_path, final_rotation[0], final_rotation[1], final_rotation[2])
        set_scale(stage, prim_path, sx, sy, sz)
        print(
            f"[INFO] Placed '{object_name}' pos={item['position']} rot={final_rotation} "
            f"scale={item['scale']} asset={asset_spec.get('source', 'local') if asset_spec else 'placeholder'} "
            f"quality={asset_spec.get('quality_score', 'n/a') if asset_spec else 'n/a'} -> {prim_path}"
        )

    if save_path:
        exported_path = export_stage_safely(stage, save_path)
        print(f"[INFO] Exported stage to: {exported_path}")

    return scene_graph
