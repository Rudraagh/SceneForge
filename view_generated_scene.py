"""
Simple local USDA previewer for the generated classroom scene.

This is not a full USD renderer. It is a lightweight viewer that opens the
generated scene and draws recognizable furniture proxies in a desktop window.
It is meant for quick inspection when you want the output to open
automatically after generation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from pxr import Usd, UsdGeom


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_STAGE = PROJECT_ROOT / "generated_scene.usda"


def get_transform_components(prim) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    translate = np.array([0.0, 0.0, 0.0], dtype=float)
    scale = np.array([1.0, 1.0, 1.0], dtype=float)
    rotate = np.array([0.0, 0.0, 0.0], dtype=float)

    xformable = UsdGeom.Xformable(prim)
    for op in xformable.GetOrderedXformOps():
        op_name = op.GetOpName()
        value = op.Get()
        if op_name == "xformOp:translate":
            translate = np.array(value, dtype=float)
        elif op_name == "xformOp:scale":
            scale = np.array(value, dtype=float)
        elif op_name == "xformOp:rotateXYZ":
            rotate = np.array(value, dtype=float)

    return translate, scale, rotate


def add_box(ax, center, size, color):
    sx, sy, sz = size
    x = center[0] - sx / 2
    y = center[1] - sy / 2
    z = center[2] - sz / 2
    ax.bar3d(x, z, y, sx, sz, sy, color=color, shade=True, alpha=0.95)


def add_sphere(ax, center, radius, color):
    u, v = np.mgrid[0 : 2 * np.pi : 20j, 0 : np.pi : 12j]
    x = center[0] + radius * np.cos(u) * np.sin(v)
    y = center[1] + radius * np.sin(u) * np.sin(v)
    z = center[2] + radius * np.cos(v)
    ax.plot_surface(x, y, z, color=color, linewidth=0, antialiased=True, shade=True)


def add_cylinder(ax, center, radius, height, color):
    theta = np.linspace(0, 2 * np.pi, 24)
    z = np.linspace(0, height, 2)
    theta_grid, z_grid = np.meshgrid(theta, z)
    x_grid = center[0] + radius * np.cos(theta_grid)
    y_grid = center[2] + radius * np.sin(theta_grid)
    z_grid = center[1] + z_grid
    ax.plot_surface(x_grid, y_grid, z_grid, color=color, linewidth=0, antialiased=True, shade=True)


def draw_desk(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.55 * scale[1], 0.0]), np.array([1.6, 0.12, 0.9]) * scale, "#7b4f28")
    for x in (-0.65, 0.65):
        for z in (-0.30, 0.30):
            add_box(ax, pos + np.array([x * scale[0], 0.0, z * scale[2]]), np.array([0.10, 0.55, 0.10]) * scale, "#4b2d14")


def draw_chair(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.35 * scale[1], 0.0]), np.array([0.7, 0.10, 0.7]) * scale, "#355fbf")
    add_box(ax, pos + np.array([0.0, 0.78 * scale[1], -0.30 * scale[2]]), np.array([0.7, 0.7, 0.10]) * scale, "#355fbf")
    for x in (-0.26, 0.26):
        for z in (-0.26, 0.26):
            add_box(ax, pos + np.array([x * scale[0], 0.0, z * scale[2]]), np.array([0.08, 0.35, 0.08]) * scale, "#222222")


def draw_blackboard(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.90 * scale[1], 0.0]), np.array([2.2, 1.4, 0.12]) * scale, "#6a421d")
    add_box(ax, pos + np.array([0.0, 0.90 * scale[1], 0.04 * scale[2]]), np.array([2.0, 1.2, 0.06]) * scale, "#163019")


def draw_lamp(ax, pos, scale):
    add_cylinder(ax, pos, 0.08 * scale[0], 1.60 * scale[1], "#666666")
    add_sphere(ax, pos + np.array([0.0, 1.70 * scale[1], 0.0]), 0.24 * scale[0], "#ffe08a")


def draw_bookshelf(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.95 * scale[1], 0.0]), np.array([1.2, 1.8, 0.4]) * scale, "#6f431d")
    for y in (0.45, 0.95, 1.45):
        add_box(ax, pos + np.array([0.0, y * scale[1], 0.02 * scale[2]]), np.array([1.1, 0.05, 0.35]) * scale, "#96602b")


def draw_table(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.58 * scale[1], 0.0]), np.array([1.7, 0.12, 1.1]) * scale, "#7d5128")
    add_box(ax, pos + np.array([0.0, 0.0, 0.0]), np.array([0.25, 0.55, 0.25]) * scale, "#503015")


def draw_throne(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.40 * scale[1], 0.0]), np.array([1.0, 0.18, 1.0]) * scale, "#8b1c1c")
    add_box(ax, pos + np.array([0.0, 1.20 * scale[1], -0.38 * scale[2]]), np.array([1.0, 1.3, 0.18]) * scale, "#d1b23d")
    add_box(ax, pos + np.array([0.0, 0.05 * scale[1], 0.0]), np.array([1.2, 0.22, 1.2]) * scale, "#593814")


def draw_banner(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.90 * scale[1], 0.0]), np.array([0.7, 1.6, 0.05]) * scale, "#ba1e26")
    add_box(ax, pos + np.array([0.0, 1.75 * scale[1], 0.0]), np.array([0.9, 0.06, 0.06]) * scale, "#c0a33a")


def draw_torch(ax, pos, scale):
    add_cylinder(ax, pos, 0.07 * scale[0], 1.20 * scale[1], "#6d4a2d")
    add_sphere(ax, pos + np.array([0.0, 1.32 * scale[1], 0.0]), 0.20 * scale[0], "#ff8c14")


def draw_barrel(ax, pos, scale):
    add_cylinder(ax, pos, 0.42 * scale[0], 0.95 * scale[1], "#7a4b24")


def draw_crate(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.30 * scale[1], 0.0]), np.array([0.6, 0.6, 0.6]) * scale, "#8c5a28")


def draw_campfire(ax, pos, scale):
    add_cylinder(ax, pos + np.array([0.0, 0.04 * scale[1], 0.0]), 0.09 * scale[0], 0.90 * scale[2], "#6a421e")
    add_sphere(ax, pos + np.array([0.0, 0.38 * scale[1], 0.0]), 0.28 * scale[0], "#ff7d0a")


def draw_tree(ax, pos, scale):
    add_cylinder(ax, pos, 0.14 * scale[0], 1.80 * scale[1], "#67401e")
    add_sphere(ax, pos + np.array([0.0, 2.20 * scale[1], 0.0]), 0.95 * scale[0], "#2f6f34")


def draw_bench(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.42 * scale[1], 0.0]), np.array([1.4, 0.12, 0.4]) * scale, "#7c5026")
    add_box(ax, pos + np.array([-0.55 * scale[0], 0.0, 0.0]), np.array([0.10, 0.42, 0.10]) * scale, "#573517")
    add_box(ax, pos + np.array([0.55 * scale[0], 0.0, 0.0]), np.array([0.10, 0.42, 0.10]) * scale, "#573517")


def draw_market_stall(ax, pos, scale):
    add_box(ax, pos + np.array([0.0, 0.48 * scale[1], 0.0]), np.array([1.5, 0.22, 0.9]) * scale, "#805327")
    add_box(ax, pos + np.array([0.0, 1.65 * scale[1], 0.0]), np.array([1.7, 0.10, 1.0]) * scale, "#c23d1d")
    add_box(ax, pos + np.array([-0.68 * scale[0], 0.80 * scale[1], -0.35 * scale[2]]), np.array([0.08, 1.6, 0.08]) * scale, "#5f3d18")
    add_box(ax, pos + np.array([0.68 * scale[0], 0.80 * scale[1], -0.35 * scale[2]]), np.array([0.08, 1.6, 0.08]) * scale, "#5f3d18")


def _rotation_matrix_xyz(degrees_xyz: np.ndarray) -> np.ndarray:
    rx, ry, rz = np.radians(degrees_xyz.astype(float))
    cx, sx = np.cos(rx), np.sin(rx)
    cy, sy = np.cos(ry), np.sin(ry)
    cz, sz = np.cos(rz), np.sin(rz)
    mx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    my = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    mz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return mz @ my @ mx


def _mesh_color(mesh_prim) -> tuple[float, float, float]:
    attr = mesh_prim.GetAttribute("primvars:displayColor")
    if attr and attr.HasValue():
        value = attr.Get()
        if value and len(value) > 0:
            color = value[0]
            return float(color[0]), float(color[1]), float(color[2])
    return 0.75, 0.75, 0.75


def _draw_mesh(ax, points: np.ndarray, triangles: list[list[int]], color: tuple[float, float, float]) -> None:
    if not triangles:
        return
    faces = [[points[idx] for idx in tri] for tri in triangles]
    collection = Poly3DCollection(
        faces,
        facecolors=[color],
        edgecolors="none",
        linewidths=0.0,
        alpha=1.0,
    )
    ax.add_collection3d(collection)


def _triangles_from_face_data(face_counts, face_indices, max_faces: int = 1800) -> list[list[int]]:
    triangles: list[list[int]] = []
    cursor = 0
    for count in face_counts:
        face = list(face_indices[cursor : cursor + count])
        cursor += count
        if count < 3:
            continue
        for i in range(1, count - 1):
            triangles.append([face[0], face[i], face[i + 1]])
    if len(triangles) > max_faces:
        step = max(1, len(triangles) // max_faces)
        triangles = triangles[::step]
    return triangles


def draw_referenced_meshes(ax, prim) -> bool:
    references = prim.GetMetadata("references")
    if not references or not getattr(references, "prependedItems", None):
        return False

    reference = references.prependedItems[0]
    asset_path = reference.assetPath
    if not asset_path:
        return False

    asset_stage = Usd.Stage.Open(asset_path)
    if asset_stage is None:
        return False

    translate, scale, rotate = get_transform_components(prim)
    rotation = _rotation_matrix_xyz(rotate)
    drew_any = False

    for mesh_prim in asset_stage.Traverse():
        if not mesh_prim.IsA(UsdGeom.Mesh):
            continue
        mesh = UsdGeom.Mesh(mesh_prim)
        points_attr = mesh.GetPointsAttr().Get()
        face_counts = mesh.GetFaceVertexCountsAttr().Get()
        face_indices = mesh.GetFaceVertexIndicesAttr().Get()
        if not points_attr or not face_counts or not face_indices:
            continue

        points = np.array([[float(p[0]), float(p[1]), float(p[2])] for p in points_attr], dtype=float)
        points = points * scale
        points = (rotation @ points.T).T
        points = points + translate
        triangles = _triangles_from_face_data(face_counts, face_indices)
        color = _mesh_color(mesh_prim)
        _draw_mesh(ax, points, triangles, color)
        drew_any = True

    return drew_any


def draw_object(ax, prim):
    name = prim.GetName().lower()
    pos, scale, _rotate = get_transform_components(prim)
    used_known_proxy = False

    if "desk" in name or "table" in name:
        if "desk" in name:
            draw_desk(ax, pos, scale)
        else:
            draw_table(ax, pos, scale)
        used_known_proxy = True
    elif "chair" in name:
        draw_chair(ax, pos, scale)
        used_known_proxy = True
    elif "blackboard" in name or "board" in name:
        draw_blackboard(ax, pos, scale)
        used_known_proxy = True
    elif "lamp" in name:
        draw_lamp(ax, pos, scale)
        used_known_proxy = True
    elif "bookshelf" in name or "shelf" in name:
        draw_bookshelf(ax, pos, scale)
        used_known_proxy = True
    elif "throne" in name:
        draw_throne(ax, pos, scale)
        used_known_proxy = True
    elif "banner" in name:
        draw_banner(ax, pos, scale)
        used_known_proxy = True
    elif "torch" in name:
        draw_torch(ax, pos, scale)
        used_known_proxy = True
    elif "barrel" in name:
        draw_barrel(ax, pos, scale)
        used_known_proxy = True
    elif "crate" in name:
        draw_crate(ax, pos, scale)
        used_known_proxy = True
    elif "campfire" in name:
        draw_campfire(ax, pos, scale)
        used_known_proxy = True
    elif "pine_tree" in name or "tree" in name:
        draw_tree(ax, pos, scale)
        used_known_proxy = True
    elif "bench" in name:
        draw_bench(ax, pos, scale)
        used_known_proxy = True
    elif "market_stall" in name or "stall" in name:
        draw_market_stall(ax, pos, scale)
        used_known_proxy = True

    if used_known_proxy:
        return

    if draw_referenced_meshes(ax, prim):
        return
    else:
        add_box(ax, pos, np.array([1.0, 1.0, 1.0]) * scale, "#bbbbbb")


def main() -> int:
    stage_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_STAGE
    if not stage_path.exists():
        print(f"[ERROR] Stage file not found: {stage_path}")
        return 1

    stage = Usd.Stage.Open(str(stage_path))
    if stage is None:
        print(f"[ERROR] Failed to open stage: {stage_path}")
        return 1

    world = stage.GetPrimAtPath("/World")
    if not world:
        print("[ERROR] /World prim not found.")
        return 1

    fig = plt.figure("USDA Scene Preview", figsize=(10, 7))
    ax = fig.add_subplot(111, projection="3d")

    for child in world.GetChildren():
        draw_object(ax, child)

    ax.set_title(f"Preview: {stage_path.name}")
    ax.set_xlabel("X")
    ax.set_ylabel("Z")
    ax.set_zlabel("Y")
    ax.view_init(elev=22, azim=-58)
    ax.set_box_aspect((1.4, 1.4, 0.8))
    ax.grid(True, alpha=0.3)

    bounds = []
    for child in world.GetChildren():
        pos, scale, _rotate = get_transform_components(child)
        bounds.append(pos - np.maximum(scale, 1.0) * 2.5)
        bounds.append(pos + np.maximum(scale, 1.0) * 2.5)
    if bounds:
        stacked = np.vstack(bounds)
        mins = stacked.min(axis=0)
        maxs = stacked.max(axis=0)
        pad = np.array([2.0, 2.0, 2.0])
        ax.set_xlim(mins[0] - pad[0], maxs[0] + pad[0])
        ax.set_ylim(mins[2] - pad[2], maxs[2] + pad[2])
        ax.set_zlim(min(0.0, mins[1] - 0.5), maxs[1] + pad[1])
    else:
        ax.set_xlim(-6, 8)
        ax.set_ylim(-8, 6)
        ax.set_zlim(0, 5)

    plt.tight_layout()
    if os.getenv("PREVIEW_SAVE_ONLY", "0") == "1":
        preview_path = stage_path.with_suffix(".preview.png")
        plt.savefig(preview_path, dpi=160)
        print(f"[INFO] Saved preview image to: {preview_path.name}")
    else:
        plt.show()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
