"""
High-quality asset retrieval and normalization for scene generation.

Resolution order:
1. Reuse a fresh cached normalized asset
2. Try Objaverse candidates and keep the best-scoring match
3. Try curated free-source assets
4. Fall back to the local USDA asset library

External meshes are converted into normalized USDA files so scene placement
stays stable:
- centered on X/Z
- grounded on Y=0
- uniformly scaled to a category target size

Cached assets are cleaned up automatically when they go stale.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
import urllib.request
import hashlib
from difflib import get_close_matches
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import trimesh
from PIL import Image, ImageDraw
from pxr import Gf, Sdf, Usd, UsdGeom, UsdShade


PROJECT_ROOT = Path(__file__).resolve().parent
LOCAL_ASSET_ROOT = PROJECT_ROOT / "assets"
EXTERNAL_CACHE_DIR = Path(os.getenv("SCENE_ASSET_CACHE_DIR", str(PROJECT_ROOT / "external_asset_cache")))
SAFE_GENERATED_CACHE_DIR = Path(os.getenv("SCENE_SAFE_GENERATED_CACHE_DIR", str(Path(tempfile.gettempdir()) / "scene_asset_cache")))
CACHE_INDEX_PATH = EXTERNAL_CACHE_DIR / "cache_index.json"
DEFAULT_CACHE_TTL_HOURS = int(os.getenv("SCENE_ASSET_CACHE_TTL_HOURS", "168"))
OBJAVERSE_CANDIDATE_LIMIT = int(os.getenv("OBJAVERSE_CANDIDATE_LIMIT", "5"))
MIN_OBJAVERSE_SCORE = float(os.getenv("OBJAVERSE_MIN_SCORE", "0.45"))
ENABLE_PROCEDURAL_FALLBACK = os.getenv("SCENE_ENABLE_PROCEDURAL_FALLBACK", "1") != "0"
ASSET_SOURCE_NAMES = {"cache", "objaverse", "free", "local", "procedural"}


OBJECT_SPECS: Dict[str, Dict[str, object]] = {
    "bed": {
        "target_size": [2.10, 0.85, 3.00],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.45,
        "objaverse_categories": ["bed"],
        "free_sources": [],
        "local_fallback": {},
    },
    "nightstand": {
        "target_size": [0.70, 0.75, 0.55],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.45,
        "objaverse_categories": ["nightstand", "cabinet", "table"],
        "free_sources": [],
        "local_fallback": {},
    },
    "wardrobe": {
        "target_size": [1.30, 2.25, 0.65],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.45,
        "objaverse_categories": ["wardrobe", "cabinet", "closet"],
        "free_sources": [],
        "local_fallback": {},
    },
    "pillow": {
        "target_size": [0.75, 0.22, 0.48],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.40,
        "objaverse_categories": ["pillow", "cushion"],
        "free_sources": [],
        "local_fallback": {},
    },
    "blanket": {
        "target_size": [1.85, 0.12, 1.80],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.40,
        "objaverse_categories": ["blanket", "quilt", "cloth"],
        "free_sources": [],
        "local_fallback": {},
    },
    "sun": {
        "target_size": [2.40, 2.40, 2.40],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_sun.jpg",
        "fallback_color": [1.0, 0.78, 0.18],
        "local_fallback": {},
    },
    "mercury": {
        "target_size": [0.35, 0.35, 0.35],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_mercury.jpg",
        "fallback_color": [0.62, 0.60, 0.58],
        "local_fallback": {},
    },
    "venus": {
        "target_size": [0.52, 0.52, 0.52],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_venus_surface.jpg",
        "fallback_color": [0.84, 0.70, 0.42],
        "local_fallback": {},
    },
    "earth": {
        "target_size": [0.56, 0.56, 0.56],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_earth_daymap.jpg",
        "fallback_color": [0.22, 0.46, 0.86],
        "local_fallback": {},
    },
    "mars": {
        "target_size": [0.40, 0.40, 0.40],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_mars.jpg",
        "fallback_color": [0.73, 0.38, 0.22],
        "local_fallback": {},
    },
    "jupiter": {
        "target_size": [1.35, 1.35, 1.35],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_jupiter.jpg",
        "fallback_color": [0.82, 0.66, 0.46],
        "local_fallback": {},
    },
    "saturn": {
        "target_size": [1.15, 1.15, 1.15],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_saturn.jpg",
        "fallback_color": [0.88, 0.80, 0.56],
        "local_fallback": {},
    },
    "uranus": {
        "target_size": [0.82, 0.82, 0.82],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_uranus.jpg",
        "fallback_color": [0.63, 0.86, 0.88],
        "local_fallback": {},
    },
    "neptune": {
        "target_size": [0.80, 0.80, 0.80],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 1.0,
        "texture_url": "https://www.solarsystemscope.com/textures/download/2k_neptune.jpg",
        "fallback_color": [0.28, 0.44, 0.88],
        "local_fallback": {},
    },
    "wooden_desk": {
        "target_size": [1.45, 0.80, 0.70],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.55,
        "source_order": ["local", "objaverse", "procedural"],
        "objaverse_categories": ["desk", "table"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "desk.usda"), "prim_path": "/Desk"},
    },
    "table": {
        "target_size": [1.40, 0.82, 0.80],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.55,
        "source_order": ["local", "objaverse", "procedural"],
        "objaverse_categories": ["table", "desk"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "table.usda"), "prim_path": "/Table"},
    },
    "chair": {
        "target_size": [0.65, 0.95, 0.65],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.55,
        "source_order": ["local", "free", "objaverse", "procedural"],
        "objaverse_categories": ["chair", "seat"],
        "free_sources": [
            {
                "name": "SheenChair",
                "url": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/SheenChair/glTF-Binary/SheenChair.glb",
                "rotation_offset": [0.0, 0.0, 0.0],
            }
        ],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "chair.usda"), "prim_path": "/Chair"},
    },
    "blackboard": {
        "target_size": [2.20, 1.35, 0.15],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.60,
        "objaverse_categories": ["blackboard", "board"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "blackboard.usda"), "prim_path": "/Blackboard"},
    },
    "lamp": {
        "target_size": [0.45, 1.20, 0.45],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.50,
        "source_order": ["local", "free", "objaverse", "procedural"],
        "objaverse_categories": ["lamp", "lantern"],
        "free_sources": [
            {
                "name": "Lantern",
                "url": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/Lantern/glTF-Binary/Lantern.glb",
                "rotation_offset": [0.0, 0.0, 0.0],
            }
        ],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "lamp.usda"), "prim_path": "/Lamp"},
    },
    "bookshelf": {
        "target_size": [1.20, 1.90, 0.45],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.55,
        "objaverse_categories": ["bookshelf", "bookcase", "shelf"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "bookshelf.usda"), "prim_path": "/Bookshelf"},
    },
    "throne": {
        "target_size": [1.20, 1.80, 1.10],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.55,
        "objaverse_categories": ["throne"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "throne.usda"), "prim_path": "/Throne"},
    },
    "banner": {
        "target_size": [0.80, 2.20, 0.08],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.45,
        "objaverse_categories": ["banner", "flag"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "banner.usda"), "prim_path": "/Banner"},
    },
    "torch": {
        "target_size": [0.22, 1.35, 0.22],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.45,
        "objaverse_categories": ["torch", "lantern"],
        "free_sources": [
            {
                "name": "Lantern",
                "url": "https://raw.githubusercontent.com/KhronosGroup/glTF-Sample-Assets/main/Models/Lantern/glTF-Binary/Lantern.glb",
                "rotation_offset": [0.0, 0.0, 0.0],
            }
        ],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "torch.usda"), "prim_path": "/Torch"},
    },
    "barrel": {
        "target_size": [0.75, 1.00, 0.75],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.50,
        "objaverse_categories": ["barrel"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "barrel.usda"), "prim_path": "/Barrel"},
    },
    "crate": {
        "target_size": [0.90, 0.90, 0.90],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.50,
        "objaverse_categories": ["crate", "box"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "crate.usda"), "prim_path": "/Crate"},
    },
    "campfire": {
        "target_size": [1.20, 0.55, 1.20],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.45,
        "objaverse_categories": ["fireplace", "fire"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "campfire.usda"), "prim_path": "/Campfire"},
    },
    "pine_tree": {
        "target_size": [2.60, 5.50, 2.60],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.50,
        "objaverse_categories": ["tree"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "pine_tree.usda"), "prim_path": "/PineTree"},
    },
    "bench": {
        "target_size": [1.70, 0.85, 0.55],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.50,
        "objaverse_categories": ["bench"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "bench.usda"), "prim_path": "/Bench"},
    },
    "market_stall": {
        "target_size": [2.60, 2.50, 1.80],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.50,
        "objaverse_categories": ["stall", "table"],
        "free_sources": [],
        "local_fallback": {"asset_path": str(LOCAL_ASSET_ROOT / "market_stall.usda"), "prim_path": "/MarketStall"},
    },
    "clock": {
        "target_size": [1.20, 1.20, 0.20],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": 0.45,
        "objaverse_categories": ["clock", "wall clock"],
        "free_sources": [],
        "fallback_color": [0.92, 0.88, 0.72],
        "local_fallback": {},
    },
}


def canonicalize_object_name(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")
    synonyms = {
        "desk": "wooden_desk",
        "seat": "chair",
        "board": "blackboard",
        "chalkboard": "blackboard",
        "stall": "market_stall",
        "shelf": "bookshelf",
        "bookcase": "bookshelf",
        "tree": "pine_tree",
        "fire": "campfire",
        "camp_fire": "campfire",
        "bed_room": "bedroom",
        "bedside_table": "nightstand",
        "bedside_stand": "nightstand",
        "night_stand": "nightstand",
        "closet": "wardrobe",
        "duvet": "blanket",
        "quilt": "blanket",
        "cushion": "pillow",
        "clocks": "clock",
        "wall_clock": "clock",
        "grandfather_clock": "clock",
        "sol": "sun",
    }
    return synonyms.get(key, key)


def _spec_for(object_name: str) -> Dict[str, object]:
    canonical = canonicalize_object_name(object_name)
    spec = OBJECT_SPECS.get(canonical)
    if spec:
        return spec
    return {
        "target_size": [1.0, 1.0, 1.0],
        "rotation_offset": [0.0, 0.0, 0.0],
        "min_score": _min_objaverse_score(),
        "objaverse_categories": [canonical],
        "free_sources": [],
        "local_fallback": {},
    }


def _objaverse_candidate_limit() -> int:
    try:
        return max(1, int(os.getenv("OBJAVERSE_CANDIDATE_LIMIT", str(OBJAVERSE_CANDIDATE_LIMIT))))
    except ValueError:
        return OBJAVERSE_CANDIDATE_LIMIT


def _min_objaverse_score() -> float:
    try:
        return float(os.getenv("OBJAVERSE_MIN_SCORE", str(MIN_OBJAVERSE_SCORE)))
    except ValueError:
        return MIN_OBJAVERSE_SCORE


def _local_asset_map() -> Dict[str, Dict[str, object]]:
    local_map: Dict[str, Dict[str, object]] = {}
    for name, spec in OBJECT_SPECS.items():
        fallback = dict(spec.get("local_fallback", {}))
        if fallback:
            fallback["rotation_offset"] = list(spec.get("rotation_offset", [0.0, 0.0, 0.0]))
            local_map[name] = fallback
    return local_map


def _local_fallback_asset(object_name: str) -> Optional[Dict[str, object]]:
    local = _local_asset_map().get(canonicalize_object_name(object_name))
    if local and Path(str(local.get("asset_path", ""))).exists():
        return local
    return None


def _source_order_for(object_name: str) -> List[str]:
    override = os.getenv("SCENE_ASSET_SOURCE_ORDER", "").strip()
    if override:
        requested = [source.strip().lower() for source in override.split(",")]
        return [source for source in requested if source in ASSET_SOURCE_NAMES]

    spec = _spec_for(object_name)
    order = spec.get("source_order")
    if isinstance(order, list) and order:
        sources = [str(source) for source in order]
    else:
        sources = ["cache", "objaverse", "free", "local", "procedural"]

    disabled = {
        name
        for name in ASSET_SOURCE_NAMES
        if os.getenv(f"SCENE_DISABLE_{name.upper()}", "0") == "1"
    }
    if not ENABLE_PROCEDURAL_FALLBACK:
        disabled.add("procedural")
    return [source for source in sources if source not in disabled]


def _cache_allowed_for(object_name: str, entry: Dict[str, object]) -> bool:
    source = str(entry.get("source", ""))
    order = _source_order_for(object_name)
    if source.startswith("objaverse:") and "cache" not in order:
        return False
    return True


def _ensure_cache_dirs() -> None:
    EXTERNAL_CACHE_DIR.mkdir(exist_ok=True)


def _load_cache_index() -> Dict[str, Dict]:
    _ensure_cache_dirs()
    if not CACHE_INDEX_PATH.exists():
        return {}
    with CACHE_INDEX_PATH.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    return data if isinstance(data, dict) else {}


def _save_cache_index(data: Dict[str, Dict]) -> None:
    _ensure_cache_dirs()
    try:
        with CACHE_INDEX_PATH.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    except OSError:
        return


def _touch_cache_entry(key: str, entry: Dict) -> None:
    index = _load_cache_index()
    entry["last_used_ts"] = int(time.time())
    index[key] = entry
    _save_cache_index(index)


def cleanup_stale_cache(ttl_hours: int = DEFAULT_CACHE_TTL_HOURS) -> None:
    now = int(time.time())
    cutoff = now - ttl_hours * 3600
    index = _load_cache_index()
    changed = False
    for key, entry in list(index.items()):
        last_used_ts = int(entry.get("last_used_ts", 0))
        if last_used_ts and last_used_ts >= cutoff:
            continue
        for raw_path_key in ("asset_path", "source_asset_path"):
            raw_path = str(entry.get(raw_path_key, ""))
            if not raw_path:
                continue
            path = Path(raw_path)
            try:
                if path.exists():
                    path.unlink()
            except OSError:
                pass
        index.pop(key, None)
        changed = True
    if changed:
        _save_cache_index(index)


def _cache_key(object_name: str) -> str:
    return canonicalize_object_name(object_name)


def _read_fresh_cache(object_name: str) -> Optional[Dict[str, object]]:
    cleanup_stale_cache()
    index = _load_cache_index()
    entry = index.get(_cache_key(object_name))
    if not entry:
        return None
    asset_path = Path(str(entry.get("asset_path", "")))
    if not asset_path.exists():
        return None
    _touch_cache_entry(_cache_key(object_name), entry)
    return entry


def _safe_ratio(a: float, b: float) -> float:
    if a <= 1e-6 or b <= 1e-6:
        return 1.0
    return min(a, b) / max(a, b)


def _search_tokens(text: str) -> List[str]:
    return [token for token in re.findall(r"[a-z0-9]+", text.lower()) if token]


def _candidate_object_labels(object_name: str) -> List[str]:
    canonical = canonicalize_object_name(object_name)
    labels = {
        canonical,
        canonical.replace("_", " "),
    }
    if canonical.endswith("s"):
        labels.add(canonical[:-1])
    else:
        labels.add(f"{canonical}s")
    for token in _search_tokens(canonical):
        labels.add(token)
        labels.add(f"{token}s")
    return [label for label in labels if label]


def _objaverse_category_candidates(object_name: str, lvis: Dict[str, List[str]]) -> List[str]:
    labels = _candidate_object_labels(object_name)
    normalized_map = {key.lower().replace("_", " "): key for key in lvis.keys()}
    candidates: List[str] = []

    for label in labels:
        normalized_label = label.lower().replace("_", " ")
        if normalized_label in normalized_map:
            candidates.append(normalized_map[normalized_label])

    label_tokens = set()
    for label in labels:
        label_tokens.update(_search_tokens(label))
    for key in lvis.keys():
        key_tokens = set(_search_tokens(key))
        if label_tokens and (label_tokens <= key_tokens or key_tokens <= label_tokens or label_tokens & key_tokens):
            candidates.append(key)

    candidate_names = list(normalized_map.keys())
    for label in labels:
        for match in get_close_matches(label.lower().replace("_", " "), candidate_names, n=5, cutoff=0.75):
            candidates.append(normalized_map[match])

    deduped: List[str] = []
    seen = set()
    for item in candidates:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped[:8]


def _is_planet_asset(object_name: str) -> bool:
    spec = _spec_for(object_name)
    return bool(spec.get("texture_url"))


def _load_trimesh(source_path: Path):
    mesh = trimesh.load(str(source_path), force="scene")
    if isinstance(mesh, trimesh.Scene):
        mesh = mesh.dump(concatenate=True)
    return mesh


def _planet_cache_paths(object_name: str) -> Tuple[Path, Path]:
    object_name = canonicalize_object_name(object_name)
    spec = _spec_for(object_name)
    texture_url = str(spec.get("texture_url", ""))
    texture_suffix = Path(texture_url).suffix or ".jpg"
    target_dir = SAFE_GENERATED_CACHE_DIR / object_name
    target_dir.mkdir(parents=True, exist_ok=True)
    texture_path = target_dir / f"{object_name}{texture_suffix}"
    usda_path = target_dir / f"{object_name}.procedural.usda"
    return texture_path, usda_path


def _procedural_cache_paths(object_name: str, suffix: str = "procedural") -> Path:
    object_name = canonicalize_object_name(object_name)
    target_dir = SAFE_GENERATED_CACHE_DIR / object_name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir / f"{object_name}.{suffix}.usda"


def _procedural_asset_dir(object_name: str) -> Path:
    object_name = canonicalize_object_name(object_name)
    target_dir = SAFE_GENERATED_CACHE_DIR / object_name
    target_dir.mkdir(parents=True, exist_ok=True)
    return target_dir


def _build_uv_sphere(radius: float = 0.5, latitude_segments: int = 32, longitude_segments: int = 64):
    points: List[Gf.Vec3f] = []
    st_values: List[Gf.Vec2f] = []
    face_vertex_counts: List[int] = []
    face_vertex_indices: List[int] = []

    for lat in range(latitude_segments + 1):
        theta = math.pi * lat / latitude_segments
        sin_theta = math.sin(theta)
        cos_theta = math.cos(theta)
        v = 1.0 - (lat / latitude_segments)
        for lon in range(longitude_segments + 1):
            phi = 2.0 * math.pi * lon / longitude_segments
            x = radius * sin_theta * math.cos(phi)
            y = radius * cos_theta
            z = radius * sin_theta * math.sin(phi)
            u = lon / longitude_segments
            points.append(Gf.Vec3f(float(x), float(y), float(z)))
            st_values.append(Gf.Vec2f(float(u), float(v)))

    row = longitude_segments + 1
    for lat in range(latitude_segments):
        for lon in range(longitude_segments):
            a = lat * row + lon
            b = a + row
            c = b + 1
            d = a + 1
            face_vertex_counts.extend([3, 3])
            face_vertex_indices.extend([a, b, d])
            face_vertex_indices.extend([d, b, c])

    extent = [
        Gf.Vec3f(-radius, -radius, -radius),
        Gf.Vec3f(radius, radius, radius),
    ]
    return points, st_values, face_vertex_counts, face_vertex_indices, extent


def _create_preview_material(
    stage: Usd.Stage,
    material_path: str,
    texture_path: Optional[Path] = None,
    emissive: bool = False,
    fallback_color: Optional[List[float]] = None,
) -> UsdShade.Material:
    material = UsdShade.Material.Define(stage, material_path)

    shader = UsdShade.Shader.Define(stage, f"{material_path}/PreviewSurface")
    shader.CreateIdAttr("UsdPreviewSurface")
    shader.CreateInput("roughness", Sdf.ValueTypeNames.Float).Set(1.0 if emissive else 0.9)
    shader.CreateInput("metallic", Sdf.ValueTypeNames.Float).Set(0.0)
    if texture_path is not None:
        primvar_reader = UsdShade.Shader.Define(stage, f"{material_path}/PrimvarReader")
        primvar_reader.CreateIdAttr("UsdPrimvarReader_float2")
        primvar_reader.CreateInput("varname", Sdf.ValueTypeNames.Token).Set("st")
        primvar_reader.CreateOutput("result", Sdf.ValueTypeNames.Float2)

        texture = UsdShade.Shader.Define(stage, f"{material_path}/DiffuseTexture")
        texture.CreateIdAttr("UsdUVTexture")
        texture.CreateInput("file", Sdf.ValueTypeNames.Asset).Set(Sdf.AssetPath(str(texture_path)))
        texture.CreateInput("st", Sdf.ValueTypeNames.Float2).ConnectToSource(primvar_reader.ConnectableAPI(), "result")
        texture.CreateInput("sourceColorSpace", Sdf.ValueTypeNames.Token).Set("sRGB")
        texture.CreateOutput("rgb", Sdf.ValueTypeNames.Float3)
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(texture.ConnectableAPI(), "rgb")
        if emissive:
            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).ConnectToSource(texture.ConnectableAPI(), "rgb")
    else:
        color_values = fallback_color or [0.7, 0.7, 0.7]
        color = Gf.Vec3f(float(color_values[0]), float(color_values[1]), float(color_values[2]))
        shader.CreateInput("diffuseColor", Sdf.ValueTypeNames.Color3f).Set(color)
        if emissive:
            shader.CreateInput("emissiveColor", Sdf.ValueTypeNames.Color3f).Set(color)

    material.CreateSurfaceOutput().ConnectToSource(shader.ConnectableAPI(), "surface")
    return material


def _build_procedural_planet_asset(object_name: str, texture_path: Optional[Path], destination_path: Path) -> Tuple[Path, Dict[str, object]]:
    spec = _spec_for(object_name)
    diameter = float(list(spec.get("target_size", [1.0, 1.0, 1.0]))[0])
    radius = max(0.1, diameter / 2.0)
    stage = Usd.Stage.CreateNew(str(destination_path))
    root = UsdGeom.Xform.Define(stage, "/Root")
    stage.SetDefaultPrim(root.GetPrim())

    mesh = UsdGeom.Mesh.Define(stage, f"/Root/{canonicalize_object_name(object_name).title()}")
    points, st_values, face_vertex_counts, face_vertex_indices, extent = _build_uv_sphere(radius=radius)
    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
    mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)
    mesh.CreateExtentAttr(extent)
    mesh.CreateSubdivisionSchemeAttr().Set("none")

    primvars_api = UsdGeom.PrimvarsAPI(mesh)
    st_primvar = primvars_api.CreatePrimvar("st", Sdf.ValueTypeNames.TexCoord2fArray, UsdGeom.Tokens.vertex)
    st_primvar.Set(st_values)

    material = _create_preview_material(
        stage,
        f"/Root/{canonicalize_object_name(object_name).title()}Material",
        texture_path=texture_path,
        emissive=canonicalize_object_name(object_name) == "sun",
        fallback_color=list(spec.get("fallback_color", [0.7, 0.7, 0.7])),
    )
    UsdShade.MaterialBindingAPI(mesh.GetPrim()).Bind(material)

    if canonicalize_object_name(object_name) == "saturn":
        ring = UsdGeom.Cylinder.Define(stage, "/Root/SaturnRing")
        ring.CreateHeightAttr(radius * 0.06)
        ring.CreateRadiusAttr(radius * 1.9)
        ring.AddRotateXOp().Set(90.0)
        ring.AddScaleOp().Set(Gf.Vec3f(1.0, 1.0, 0.08))
        ring_material = _create_preview_material(
            stage,
            "/Root/SaturnRingMaterial",
            texture_path=None,
            emissive=False,
            fallback_color=[0.86, 0.82, 0.70],
        )
        UsdShade.MaterialBindingAPI(ring.GetPrim()).Bind(ring_material)

    stage.GetRootLayer().Save()

    metadata = {
        "scale_factor": 1.0,
        "size": [diameter, diameter, diameter],
        "original_size": [diameter, diameter, diameter],
        "face_count": len(face_vertex_counts),
        "quality_score": 1.0,
    }
    return destination_path, metadata


def _build_procedural_clock_asset(object_name: str, destination_path: Path) -> Tuple[Path, Dict[str, object]]:
    spec = _spec_for(object_name)
    diameter = float(list(spec.get("target_size", [1.2, 1.2, 0.2]))[0])
    thickness = float(list(spec.get("target_size", [1.2, 1.2, 0.2]))[2])
    texture_path = _generate_clock_texture(object_name)

    stage = Usd.Stage.CreateNew(str(destination_path))
    root = UsdGeom.Xform.Define(stage, "/Root")
    stage.SetDefaultPrim(root.GetPrim())

    body = UsdGeom.Cylinder.Define(stage, "/Root/ClockBody")
    body.CreateRadiusAttr(max(0.1, diameter / 2.0))
    body.CreateHeightAttr(max(0.05, thickness))
    body.CreateAxisAttr().Set(UsdGeom.Tokens.z)
    body_material = _create_preview_material(
        stage,
        "/Root/ClockBodyMaterial",
        texture_path=None,
        emissive=False,
        fallback_color=list(spec.get("fallback_color", [0.92, 0.88, 0.72])),
    )
    UsdShade.MaterialBindingAPI(body.GetPrim()).Bind(body_material)

    face = UsdGeom.Cylinder.Define(stage, "/Root/ClockFace")
    face.CreateRadiusAttr(max(0.08, (diameter / 2.0) * 0.88))
    face.CreateHeightAttr(max(0.02, thickness * 0.35))
    face.CreateAxisAttr().Set(UsdGeom.Tokens.z)
    face.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.0, float(thickness * 0.2)))
    face_material = _create_preview_material(
        stage,
        "/Root/ClockFaceMaterial",
        texture_path=texture_path,
        emissive=False,
        fallback_color=[0.98, 0.97, 0.94],
    )
    UsdShade.MaterialBindingAPI(face.GetPrim()).Bind(face_material)

    hour_hand = UsdGeom.Cube.Define(stage, "/Root/HourHand")
    hour_hand.CreateSizeAttr(1.0)
    hour_hand.AddScaleOp().Set(Gf.Vec3f(float(diameter * 0.06), float(diameter * 0.32), float(thickness * 0.25)))
    hour_hand.AddTranslateOp().Set(Gf.Vec3f(0.0, float(diameter * 0.16), float(thickness * 0.32)))

    minute_hand = UsdGeom.Cube.Define(stage, "/Root/MinuteHand")
    minute_hand.CreateSizeAttr(1.0)
    minute_hand.AddScaleOp().Set(Gf.Vec3f(float(diameter * 0.04), float(diameter * 0.44), float(thickness * 0.22)))
    minute_hand.AddTranslateOp().Set(Gf.Vec3f(0.0, float(diameter * 0.22), float(thickness * 0.35)))
    minute_hand.AddRotateZOp().Set(-35.0)

    hand_material = _create_preview_material(
        stage,
        "/Root/ClockHandMaterial",
        texture_path=None,
        emissive=False,
        fallback_color=[0.12, 0.12, 0.12],
    )
    UsdShade.MaterialBindingAPI(hour_hand.GetPrim()).Bind(hand_material)
    UsdShade.MaterialBindingAPI(minute_hand.GetPrim()).Bind(hand_material)

    stage.GetRootLayer().Save()

    metadata = {
        "scale_factor": 1.0,
        "size": [diameter, diameter, thickness],
        "original_size": [diameter, diameter, thickness],
        "face_count": 0,
        "quality_score": 1.0,
    }
    return destination_path, metadata


def _generate_clock_texture(object_name: str) -> Path:
    target_dir = _procedural_asset_dir(object_name)
    texture_path = target_dir / f"{canonicalize_object_name(object_name)}_face.png"
    if texture_path.exists():
        return texture_path

    size = 1024
    image = Image.new("RGB", (size, size), (245, 240, 222))
    draw = ImageDraw.Draw(image)
    center = size // 2
    radius = int(size * 0.42)

    draw.ellipse(
        (center - radius, center - radius, center + radius, center + radius),
        fill=(246, 241, 228),
        outline=(55, 45, 34),
        width=18,
    )
    inner_radius = int(radius * 0.92)
    draw.ellipse(
        (center - inner_radius, center - inner_radius, center + inner_radius, center + inner_radius),
        outline=(180, 150, 96),
        width=8,
    )

    for hour in range(12):
        angle = math.radians((hour / 12.0) * 360.0 - 90.0)
        outer = radius * 0.82
        inner = radius * (0.68 if hour % 3 == 0 else 0.74)
        x1 = center + int(math.cos(angle) * inner)
        y1 = center + int(math.sin(angle) * inner)
        x2 = center + int(math.cos(angle) * outer)
        y2 = center + int(math.sin(angle) * outer)
        draw.line((x1, y1, x2, y2), fill=(40, 35, 32), width=10 if hour % 3 == 0 else 6)

    draw.line(
        (center, center, center, center - int(radius * 0.38)),
        fill=(32, 32, 32),
        width=14,
    )
    draw.line(
        (center, center, center + int(radius * 0.28), center - int(radius * 0.14)),
        fill=(120, 28, 28),
        width=8,
    )
    draw.ellipse(
        (center - 16, center - 16, center + 16, center + 16),
        fill=(180, 150, 96),
        outline=(32, 32, 32),
        width=4,
    )

    image.save(texture_path)
    return texture_path


def _semantic_color(object_name: str) -> List[float]:
    digest = hashlib.sha256(canonicalize_object_name(object_name).encode("utf-8")).digest()
    hue = digest[0] / 255.0
    saturation = 0.38 + (digest[1] / 255.0) * 0.32
    value = 0.62 + (digest[2] / 255.0) * 0.28

    i = int(hue * 6.0)
    f = hue * 6.0 - i
    p = value * (1.0 - saturation)
    q = value * (1.0 - f * saturation)
    t = value * (1.0 - (1.0 - f) * saturation)
    choices = [
        (value, t, p),
        (q, value, p),
        (p, value, t),
        (p, q, value),
        (t, p, value),
        (value, p, q),
    ]
    return [round(float(component), 3) for component in choices[i % 6]]


def _generate_semantic_texture(object_name: str) -> Path:
    target_dir = _procedural_asset_dir(object_name)
    texture_path = target_dir / f"{canonicalize_object_name(object_name)}_texture.png"
    if texture_path.exists():
        return texture_path

    base = _semantic_color(object_name)
    base_rgb = tuple(int(max(0.0, min(1.0, channel)) * 255) for channel in base)
    accent_rgb = tuple(min(255, int(channel * 1.25 + 24)) for channel in base_rgb)
    dark_rgb = tuple(max(0, int(channel * 0.45)) for channel in base_rgb)

    size = 1024
    image = Image.new("RGB", (size, size), base_rgb)
    draw = ImageDraw.Draw(image)
    tokens = _search_tokens(object_name)
    for y in range(0, size, 64):
        fill = accent_rgb if (y // 64) % 2 == 0 else base_rgb
        draw.rectangle((0, y, size, y + 32), fill=fill)
    for x in range(-size, size, 96):
        draw.line((x, size, x + size, 0), fill=dark_rgb, width=10)
    for index, token in enumerate(tokens[:3]):
        y = 120 + index * 170
        draw.rectangle((96, y - 38, size - 96, y + 38), fill=base_rgb, outline=dark_rgb, width=6)
        draw.text((128, y - 18), token.upper(), fill=dark_rgb)

    image.save(texture_path)
    return texture_path


def generate_procedural_proxy_asset(name: str) -> Optional[Dict[str, object]]:
    if not ENABLE_PROCEDURAL_FALLBACK or os.getenv("SCENE_DISABLE_PROCEDURAL", "0") == "1":
        return None

    object_name = canonicalize_object_name(name)
    destination_path = _procedural_cache_paths(object_name, suffix="proxy")
    texture_path = _generate_semantic_texture(object_name)
    color = _semantic_color(object_name)
    stage = Usd.Stage.CreateNew(str(destination_path))
    root = UsdGeom.Xform.Define(stage, "/Root")
    stage.SetDefaultPrim(root.GetPrim())

    lower = object_name.lower()
    if lower == "bed" or lower.endswith("_bed"):
        mesh = UsdGeom.Cube.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateSizeAttr(1.0)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.35, 0.0))
        mesh.AddScaleOp().Set(Gf.Vec3f(2.1, 0.7, 3.0))
        size = [2.1, 0.7, 3.0]
    elif "pillow" in lower:
        mesh = UsdGeom.Sphere.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateRadiusAttr(0.5)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.18, 0.0))
        mesh.AddScaleOp().Set(Gf.Vec3f(0.85, 0.22, 0.55))
        size = [0.85, 0.22, 0.55]
    elif "blanket" in lower:
        mesh = UsdGeom.Cube.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateSizeAttr(1.0)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.07, 0.0))
        mesh.AddScaleOp().Set(Gf.Vec3f(1.9, 0.14, 1.8))
        size = [1.9, 0.14, 1.8]
    elif any(key in lower for key in ("nightstand", "cabinet", "dresser")):
        mesh = UsdGeom.Cube.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateSizeAttr(1.0)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.38, 0.0))
        mesh.AddScaleOp().Set(Gf.Vec3f(0.7, 0.76, 0.55))
        size = [0.7, 0.76, 0.55]
    elif any(key in lower for key in ("wardrobe", "closet")):
        mesh = UsdGeom.Cube.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateSizeAttr(1.0)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 1.1, 0.0))
        mesh.AddScaleOp().Set(Gf.Vec3f(1.25, 2.2, 0.65))
        size = [1.25, 2.2, 0.65]
    elif any(key in lower for key in ("column", "pillar", "spire", "tower")):
        mesh = UsdGeom.Cylinder.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateRadiusAttr(0.28 if "spire" not in lower else 0.18)
        mesh.CreateHeightAttr(2.4 if "spire" not in lower else 3.0)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 1.2 if "spire" not in lower else 1.5, 0.0))
        size = [0.56, 2.4 if "spire" not in lower else 3.0, 0.56]
    elif any(key in lower for key in ("arch", "gate")):
        mesh = UsdGeom.Cube.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateSizeAttr(1.0)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 1.0, 0.0))
        mesh.AddScaleOp().Set(Gf.Vec3f(1.8, 2.0, 0.28))
        size = [1.8, 2.0, 0.28]
    elif "door" in lower:
        mesh = UsdGeom.Cube.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateSizeAttr(1.0)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 1.02, 0.0))
        mesh.AddScaleOp().Set(Gf.Vec3f(1.0, 2.04, 0.12))
        size = [1.0, 2.04, 0.12]
    elif any(key in lower for key in ("noodle", "rope", "vine")):
        mesh = UsdGeom.Cylinder.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateRadiusAttr(0.16)
        mesh.CreateHeightAttr(2.8)
        mesh.CreateAxisAttr().Set(UsdGeom.Tokens.x)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.45, 0.0))
        mesh.AddRotateZOp().Set(12.0)
        size = [2.8, 0.32, 0.32]
    else:
        mesh = UsdGeom.Sphere.Define(stage, f"/Root/{object_name.title().replace('_', '')}")
        mesh.CreateRadiusAttr(0.55)
        mesh.AddTranslateOp().Set(Gf.Vec3f(0.0, 0.55, 0.0))
        size = [1.1, 1.1, 1.1]

    material = _create_preview_material(
        stage,
        f"/Root/{object_name.title().replace('_', '')}Material",
        texture_path=texture_path,
        emissive=False,
        fallback_color=color,
    )
    UsdShade.MaterialBindingAPI(mesh.GetPrim()).Bind(material)
    stage.GetRootLayer().Save()

    entry = _make_cache_entry(
        object_name=object_name,
        source_name=f"procedural-proxy:{object_name}",
        source_asset_path=texture_path,
        asset_path=destination_path,
        extra_meta={
            "scale_factor": 1.0,
            "size": size,
            "original_size": size,
            "face_count": 0,
            "quality_score": 0.35,
        },
    )
    _touch_cache_entry(_cache_key(object_name), entry)
    return entry


def _retrieve_planet_asset(object_name: str) -> Optional[Dict[str, object]]:
    object_name = canonicalize_object_name(object_name)
    spec = _spec_for(object_name)
    texture_url = str(spec.get("texture_url", ""))
    if not texture_url:
        return None

    texture_path, usda_path = _planet_cache_paths(object_name)
    texture_path_for_build: Optional[Path] = texture_path if texture_path.exists() else None
    if texture_path_for_build is None:
        try:
            with urllib.request.urlopen(texture_url, timeout=180) as response:
                with texture_path.open("wb") as handle:
                    handle.write(response.read())
            texture_path_for_build = texture_path
        except Exception:
            texture_path_for_build = None

    asset_path, extra_meta = _build_procedural_planet_asset(object_name, texture_path_for_build, usda_path)
    entry = _make_cache_entry(
        object_name=object_name,
        source_name=f"planet-texture:{object_name}",
        source_asset_path=texture_path,
        asset_path=asset_path,
        extra_meta=extra_meta,
    )
    _touch_cache_entry(_cache_key(object_name), entry)
    return entry


def generate_planet_asset(name: str) -> Optional[Dict[str, object]]:
    """
    Public deterministic planet-asset generator.

    Returns the same asset-spec structure used by `find_asset(...)` so callers
    can request a procedural planet directly when needed.
    """
    return _retrieve_planet_asset(name)


def generate_clock_asset(name: str) -> Optional[Dict[str, object]]:
    object_name = canonicalize_object_name(name)
    if object_name != "clock":
        return None

    destination_path = _procedural_cache_paths(object_name, suffix="procedural")
    asset_path, extra_meta = _build_procedural_clock_asset(object_name, destination_path)
    entry = _make_cache_entry(
        object_name=object_name,
        source_name="procedural:clock",
        source_asset_path=destination_path,
        asset_path=asset_path,
        extra_meta=extra_meta,
    )
    _touch_cache_entry(_cache_key(object_name), entry)
    return entry


def _mesh_statistics(mesh) -> Dict[str, object]:
    vertices = mesh.vertices.tolist()
    faces = mesh.faces.tolist()
    if not vertices or not faces:
        raise ValueError("Mesh has no geometry.")

    mins = [float(min(vertex[i] for vertex in vertices)) for i in range(3)]
    maxs = [float(max(vertex[i] for vertex in vertices)) for i in range(3)]
    size = [maxs[i] - mins[i] for i in range(3)]
    face_count = len(faces)
    return {
        "vertices": vertices,
        "faces": faces,
        "mins": mins,
        "maxs": maxs,
        "size": size,
        "face_count": face_count,
    }


def _score_mesh_for_object(object_name: str, mesh_stats: Dict[str, object]) -> float:
    spec = _spec_for(object_name)
    target_size = list(spec.get("target_size", [1.0, 1.0, 1.0]))
    size = list(mesh_stats["size"])
    face_count = int(mesh_stats["face_count"])

    if min(size) <= 1e-5 or face_count <= 0:
        return 0.0

    ratio_score = sum(_safe_ratio(size[i], target_size[i]) for i in range(3)) / 3.0
    height_bonus = _safe_ratio(size[1], target_size[1])
    quality_score = min(1.0, math.log10(face_count + 10) / 5.0)

    return round(0.45 * ratio_score + 0.20 * height_bonus + 0.35 * quality_score, 4)


def _normalize_vertices_for_object(object_name: str, mesh_stats: Dict[str, object]) -> Tuple[List[Tuple[float, float, float]], Dict[str, object]]:
    spec = _spec_for(object_name)
    target_size = list(spec.get("target_size", [1.0, 1.0, 1.0]))
    vertices = mesh_stats["vertices"]
    mins = mesh_stats["mins"]
    maxs = mesh_stats["maxs"]
    size = mesh_stats["size"]

    center_x = (mins[0] + maxs[0]) / 2.0
    center_z = (mins[2] + maxs[2]) / 2.0
    min_y = mins[1]

    base_vertices = [
        (float(vertex[0]) - center_x, float(vertex[1]) - min_y, float(vertex[2]) - center_z)
        for vertex in vertices
    ]

    scale_candidates = []
    for axis_size, axis_target in zip(size, target_size):
        if axis_size > 1e-6:
            scale_candidates.append(float(axis_target) / float(axis_size))
    scale_factor = min(scale_candidates) if scale_candidates else 1.0

    normalized_vertices = [
        (vx * scale_factor, vy * scale_factor, vz * scale_factor) for vx, vy, vz in base_vertices
    ]

    normalized_mins = [float(min(vertex[i] for vertex in normalized_vertices)) for i in range(3)]
    normalized_maxs = [float(max(vertex[i] for vertex in normalized_vertices)) for i in range(3)]
    normalized_size = [normalized_maxs[i] - normalized_mins[i] for i in range(3)]

    return normalized_vertices, {
        "scale_factor": scale_factor,
        "size": normalized_size,
        "original_size": size,
    }


def _convert_external_mesh_to_usda(source_path: Path, object_name: str, destination_path: Optional[Path] = None) -> Tuple[Path, Dict[str, object]]:
    """
    Convert a downloaded mesh into a normalized USDA file with a grounded pivot.
    """
    if source_path.suffix.lower() in {".usd", ".usda", ".usdc"} and destination_path is None:
        stage = Usd.Stage.Open(str(source_path))
        if stage is None:
            raise ValueError(f"Could not open USD asset: {source_path}")
        bbox = UsdGeom.BBoxCache(Usd.TimeCode.Default(), ["default", "render", "proxy"]).ComputeWorldBound(
            stage.GetDefaultPrim()
        ).ComputeAlignedBox()
        size = bbox.GetSize()
        metadata = {
            "scale_factor": 1.0,
            "size": [float(size[0]), float(size[1]), float(size[2])],
            "original_size": [float(size[0]), float(size[1]), float(size[2])],
            "face_count": 0,
            "quality_score": 1.0,
        }
        return source_path, metadata

    target_path = destination_path or source_path.with_suffix(".usda")
    mesh = _load_trimesh(source_path)
    mesh_stats = _mesh_statistics(mesh)
    normalized_vertices, normalization_meta = _normalize_vertices_for_object(object_name, mesh_stats)
    quality_score = _score_mesh_for_object(object_name, mesh_stats)

    stage = Usd.Stage.CreateNew(str(target_path))
    root = UsdGeom.Xform.Define(stage, "/Root")
    stage.SetDefaultPrim(root.GetPrim())

    prim_name = re.sub(r"[^A-Za-z0-9_]", "_", canonicalize_object_name(object_name).title()) or "Mesh"
    usd_mesh = UsdGeom.Mesh.Define(stage, f"/Root/{prim_name}")
    usd_mesh.CreatePointsAttr([Gf.Vec3f(*map(float, point)) for point in normalized_vertices])
    faces = mesh_stats["faces"]
    usd_mesh.CreateFaceVertexCountsAttr([len(face) for face in faces])
    usd_mesh.CreateFaceVertexIndicesAttr([int(index) for face in faces for index in face])
    usd_mesh.CreateSubdivisionSchemeAttr().Set("none")
    stage.GetRootLayer().Save()

    metadata = {
        "scale_factor": normalization_meta["scale_factor"],
        "size": normalization_meta["size"],
        "original_size": normalization_meta["original_size"],
        "face_count": int(mesh_stats["face_count"]),
        "quality_score": quality_score,
    }
    return target_path, metadata


def _make_cache_entry(
    object_name: str,
    source_name: str,
    source_asset_path: Path,
    asset_path: Path,
    extra_meta: Dict[str, object],
    rotation_offset: Optional[List[float]] = None,
) -> Dict[str, object]:
    spec = _spec_for(object_name)
    return {
        "asset_path": str(asset_path),
        "source_asset_path": str(source_asset_path),
        "prim_path": "/Root",
        "source": source_name,
        "rotation_offset": list(rotation_offset or spec.get("rotation_offset", [0.0, 0.0, 0.0])),
        "last_used_ts": int(time.time()),
        "quality_score": float(extra_meta.get("quality_score", 0.0)),
        "normalized_size": list(extra_meta.get("size", [1.0, 1.0, 1.0])),
        "original_size": list(extra_meta.get("original_size", [1.0, 1.0, 1.0])),
        "scale_factor": float(extra_meta.get("scale_factor", 1.0)),
        "face_count": int(extra_meta.get("face_count", 0)),
    }


def _download_to_cache(object_name: str, source_name: str, url: str, rotation_offset: Optional[List[float]] = None) -> Optional[Dict[str, object]]:
    object_name = canonicalize_object_name(object_name)
    target_dir = EXTERNAL_CACHE_DIR / object_name
    target_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1] or f"{source_name}.glb"
    target_path = target_dir / filename
    normalized_name = f"{Path(filename).stem}.normalized.usda"
    normalized_path = target_dir / normalized_name

    if not target_path.exists():
        with urllib.request.urlopen(url, timeout=180) as response:
            with target_path.open("wb") as handle:
                handle.write(response.read())

    converted_path, extra_meta = _convert_external_mesh_to_usda(target_path, object_name, normalized_path)
    entry = _make_cache_entry(object_name, source_name, target_path, converted_path, extra_meta, rotation_offset=rotation_offset)
    _touch_cache_entry(_cache_key(object_name), entry)
    return entry


def _candidate_download_path(uid: str) -> Path:
    object_cache = EXTERNAL_CACHE_DIR / "objaverse_candidates"
    object_cache.mkdir(parents=True, exist_ok=True)
    return object_cache / f"{uid}.normalized.usda"


def retrieve_objaverse_asset(object_name: str) -> Optional[Dict[str, object]]:
    object_name = canonicalize_object_name(object_name)
    spec = _spec_for(object_name)

    if os.getenv("SCENE_DISABLE_OBJAVERSE", "0") == "1":
        return None

    try:
        import objaverse
    except Exception:
        return None

    try:
        lvis = objaverse.load_lvis_annotations()
    except Exception:
        return None

    configured_categories = list(spec.get("objaverse_categories", [object_name]))
    categories = configured_categories or [object_name]
    if object_name not in OBJECT_SPECS:
        inferred = _objaverse_category_candidates(object_name, lvis)
        if inferred:
            categories = inferred

    best_entry: Optional[Dict[str, object]] = None
    best_score = -1.0

    for category in categories:
        uids = sorted(lvis.get(category, []))[:_objaverse_candidate_limit()]
        if not uids:
            continue
        for uid in uids:
            try:
                paths = objaverse.load_objects([uid], download_processes=1)
            except Exception:
                continue
            source_asset = paths.get(uid)
            if not source_asset or not Path(source_asset).exists():
                continue
            normalized_path = _candidate_download_path(uid)
            try:
                converted_path, extra_meta = _convert_external_mesh_to_usda(Path(source_asset), object_name, normalized_path)
            except Exception:
                continue
            entry = _make_cache_entry(
                object_name=object_name,
                source_name=f"objaverse:{category}:{uid}",
                source_asset_path=Path(source_asset),
                asset_path=converted_path,
                extra_meta=extra_meta,
            )
            score = float(entry.get("quality_score", 0.0))
            if score > best_score:
                best_score = score
                best_entry = entry
            if score >= _min_objaverse_score():
                break
        if best_score >= _min_objaverse_score():
            break

    min_score = _min_objaverse_score() if os.getenv("OBJAVERSE_MIN_SCORE") else float(spec.get("min_score", MIN_OBJAVERSE_SCORE))
    if best_entry and float(best_entry.get("quality_score", 0.0)) >= min_score:
        _touch_cache_entry(_cache_key(object_name), best_entry)
        return best_entry
    return None


def retrieve_free_source_asset(object_name: str) -> Optional[Dict[str, object]]:
    object_name = canonicalize_object_name(object_name)
    spec = _spec_for(object_name)
    for candidate in spec.get("free_sources", []):
        try:
            return _download_to_cache(
                object_name=object_name,
                source_name=str(candidate["name"]),
                url=str(candidate["url"]),
                rotation_offset=list(candidate.get("rotation_offset", spec.get("rotation_offset", [0.0, 0.0, 0.0]))),
            )
        except Exception:
            continue
    return None


def find_asset(object_name: str) -> Optional[Dict[str, object]]:
    """
    Resolve an asset using:
    1. per-object source order
    2. procedural fallback
    """
    object_name = canonicalize_object_name(object_name)

    if _is_planet_asset(object_name):
        planet_match = generate_planet_asset(object_name)
        if planet_match:
            return planet_match

    if object_name == "clock":
        clock_match = generate_clock_asset(object_name)
        if clock_match:
            return clock_match

    for source in _source_order_for(object_name):
        if source == "cache":
            cached = _read_fresh_cache(object_name)
            if cached and _cache_allowed_for(object_name, cached):
                if str(cached.get("source", "")).startswith("procedural-proxy:"):
                    proxy = generate_procedural_proxy_asset(object_name)
                    if proxy:
                        return proxy
                return cached
        elif source == "local":
            local = _local_fallback_asset(object_name)
            if local:
                return local
        elif source == "objaverse":
            objaverse_match = retrieve_objaverse_asset(object_name)
            if objaverse_match:
                return objaverse_match
        elif source == "free":
            free_match = retrieve_free_source_asset(object_name)
            if free_match:
                return free_match
        elif source == "procedural":
            proxy = generate_procedural_proxy_asset(object_name)
            if proxy:
                return proxy

    proxy = generate_procedural_proxy_asset(object_name)
    if proxy:
        return proxy
    return None
