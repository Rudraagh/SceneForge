from __future__ import annotations

from collections import deque
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PIL import Image

from ai_scene_graph import canonicalize_object_name


DEFAULT_COLOR_MAP = {
    "wooden_desk": (160, 82, 45),
    "table": (181, 101, 29),
    "chair": (65, 105, 225),
    "blackboard": (34, 139, 34),
    "bookshelf": (139, 69, 19),
    "lamp": (255, 215, 0),
    # Dark slate — distinct from chair blue and desk browns; use for exits/doors on plans.
    "door": (60, 60, 72),
}
BACKGROUND_THRESHOLD = 235
MIN_REGION_PIXELS = 20


def infer_layout_intent(prompt: str) -> str:
    text = prompt.lower()
    if any(word in text for word in ("grid", "rows", "columns", "classroom", "desks")):
        return "grid"
    if any(word in text for word in ("circle", "round", "around")):
        return "radial"
    if any(word in text for word in ("hallway", "corridor", "aisle")):
        return "linear"
    return "freeform"


def parse_blueprint(
    image_path: str,
    prompt: str = "",
    color_map: Optional[Dict[str, Tuple[int, int, int]]] = None,
) -> List[Dict]:
    path = Path(image_path)
    if not path.exists():
        return []

    try:
        image = Image.open(path).convert("RGB")
    except OSError:
        return []

    width, height = image.size
    pixels = image.load()
    visited = set()
    palette = color_map or DEFAULT_COLOR_MAP
    objects: List[Dict] = []

    for y in range(height):
        for x in range(width):
            if (x, y) in visited:
                continue

            color = pixels[x, y]
            visited.add((x, y))
            if _is_background(color):
                continue

            region = _collect_region(pixels, width, height, x, y, visited)
            if len(region) < MIN_REGION_PIXELS:
                continue

            region_color = _average_color(region, pixels)
            object_name = _nearest_object_name(region_color, palette)
            center_x, center_y = _region_centroid(region)
            objects.append(
                {
                    "name": canonicalize_object_name(object_name),
                    "x": round(center_x / max(1, width - 1), 4),
                    "y": round(center_y / max(1, height - 1), 4),
                }
            )

    objects.sort(key=lambda item: (item["y"], item["x"], item["name"]))
    return objects


def parse_blueprint_or_empty(
    image_path: str,
    prompt: str = "",
    color_map: Optional[Dict[str, Tuple[int, int, int]]] = None,
) -> List[Dict]:
    return parse_blueprint(image_path=image_path, prompt=prompt, color_map=color_map)


def _is_background(color: Tuple[int, int, int]) -> bool:
    return all(channel >= BACKGROUND_THRESHOLD for channel in color)


def _collect_region(pixels, width: int, height: int, start_x: int, start_y: int, visited: set) -> List[Tuple[int, int]]:
    seed_color = pixels[start_x, start_y]
    queue = deque([(start_x, start_y)])
    region = [(start_x, start_y)]

    while queue:
        x, y = queue.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nx < 0 or ny < 0 or nx >= width or ny >= height:
                continue
            if (nx, ny) in visited:
                continue
            candidate = pixels[nx, ny]
            visited.add((nx, ny))
            if _is_background(candidate):
                continue
            if _color_distance(seed_color, candidate) > 55.0:
                continue
            queue.append((nx, ny))
            region.append((nx, ny))

    return region


def _average_color(region: List[Tuple[int, int]], pixels) -> Tuple[int, int, int]:
    total_r = total_g = total_b = 0
    for x, y in region:
        r, g, b = pixels[x, y]
        total_r += r
        total_g += g
        total_b += b
    count = max(1, len(region))
    return (round(total_r / count), round(total_g / count), round(total_b / count))


def _nearest_object_name(color: Tuple[int, int, int], palette: Dict[str, Tuple[int, int, int]]) -> str:
    return min(palette, key=lambda name: _color_distance(color, palette[name]))


def _color_distance(color1: Tuple[int, int, int], color2: Tuple[int, int, int]) -> float:
    return sum((float(a) - float(b)) ** 2 for a, b in zip(color1, color2)) ** 0.5


def _region_centroid(region: List[Tuple[int, int]]) -> Tuple[float, float]:
    total_x = sum(x for x, _y in region)
    total_y = sum(y for _x, y in region)
    count = max(1, len(region))
    return total_x / count, total_y / count
