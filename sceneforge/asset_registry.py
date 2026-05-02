"""Thin asset registry helpers layered over the existing asset loader."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from sceneforge.logging_utils import get_logger


LOGGER = get_logger(__name__)


@dataclass(frozen=True)
class AssetDescriptor:
    """Registry descriptor for asset matching."""

    name: str
    aliases: tuple[str, ...]
    categories: tuple[str, ...]
    preferred_sources: tuple[str, ...]


_REGISTRY: Dict[str, AssetDescriptor] = {
    "wooden_desk": AssetDescriptor("wooden_desk", ("desk", "school_desk", "teacher_desk"), ("desk", "table"), ("local", "objaverse", "procedural")),
    "table": AssetDescriptor("table", ("table",), ("table", "desk"), ("local", "objaverse", "procedural")),
    "chair": AssetDescriptor("chair", ("chair", "seat", "stool"), ("chair", "seat"), ("local", "free", "objaverse", "procedural")),
    "blackboard": AssetDescriptor("blackboard", ("board", "chalkboard"), ("blackboard", "board"), ("local", "objaverse", "procedural")),
    "bookshelf": AssetDescriptor("bookshelf", ("bookshelf", "bookcase", "shelf"), ("bookshelf", "shelf"), ("local", "objaverse", "procedural")),
    "lamp": AssetDescriptor("lamp", ("lamp", "lantern"), ("lamp", "lantern"), ("local", "free", "objaverse", "procedural")),
    "door": AssetDescriptor("door", ("door", "exit", "doorway"), ("door", "gate"), ("local", "objaverse", "procedural")),
    "barrel": AssetDescriptor("barrel", ("barrel",), ("barrel",), ("local", "objaverse", "procedural")),
    "fountain": AssetDescriptor("fountain", ("fountain", "water_feature"), ("fountain", "decor"), ("procedural", "local")),
}


def canonicalize_asset_name(name: str) -> str:
    """Resolve a name against the registry without forcing unrelated substitutions."""

    normalized = (name or "").strip().lower().replace("-", "_").replace(" ", "_")
    for asset_name, descriptor in _REGISTRY.items():
        if normalized == asset_name or normalized in descriptor.aliases:
            return asset_name
    from ai_scene_graph import canonicalize_object_name

    return canonicalize_object_name(name)


def registry_entries() -> List[AssetDescriptor]:
    """Expose asset registry entries for plugin-style extension later."""

    return list(_REGISTRY.values())


def find_asset(object_name: str) -> Optional[Dict[str, object]]:
    """Compatibility wrapper around the legacy asset loader with improved naming."""

    from objaverse_loader import find_asset as legacy_find_asset

    resolved_name = canonicalize_asset_name(object_name)
    if resolved_name == "fountain":
        LOGGER.warning("No dedicated fountain asset yet; falling back through legacy loader for '%s'.", object_name)
    return legacy_find_asset(resolved_name)

