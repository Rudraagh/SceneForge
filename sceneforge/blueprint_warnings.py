"""
Heuristic warnings for blueprint mode: prompt vs filename, parse health, strict mode.

Used by the FastAPI layer before/after parsing so the UI can surface mismatches
without changing core placement math.
"""

from __future__ import annotations

import re
from typing import List, Optional, Tuple

Rule = Tuple[re.Pattern[str], str, str]

_RULES: List[Rule] = [
    (re.compile(r"\blecture\b|instructor desk|student desks|rear exit", re.I), "blueprint_b03", "lecture hall (b03)"),
    (re.compile(r"living room|\bkitchen\b|single-story home", re.I), "blueprint_b02", "two-room home (b02)"),
    (re.compile(r"gallery walk|east.*west.*wall", re.I), "blueprint_b07", "gallery walk (b07)"),
    (re.compile(r"\bthrone\b|hall of banners", re.I), "blueprint_x01", "throne hall (x01)"),
    (re.compile(r"\bcourtyard\b|\bfountain\b", re.I), "blueprint_x02", "courtyard (x02)"),
    (re.compile(r"\bmarket\b|\bstalls?\b", re.I), "blueprint_x03", "market (x03)"),
    (re.compile(r"\btavern\b", re.I), "blueprint_x04", "tavern (x04)"),
    (re.compile(r"\bforest\b|\bcamp\b|\bcanopy\b", re.I), "blueprint_x05", "forest camp (x05)"),
    (re.compile(r"l-?shaped office|\bl shape\b office", re.I), "blueprint_b04", "L-office (b04)"),
    (re.compile(r"\bcafeteria\b", re.I), "blueprint_b05", "cafeteria row (b05)"),
    (re.compile(r"\blibrary\b", re.I), "blueprint_b06", "library (b06)"),
    (re.compile(r"open-?plan studio|drafting table", re.I), "blueprint_b01", "studio (b01)"),
    (re.compile(r"training lab|\bu-?desk", re.I), "blueprint_b10", "training lab (b10)"),
    (re.compile(r"\bretail\b|\bcheckout\b", re.I), "blueprint_b09", "retail (b09)"),
    (re.compile(r"dual classroom|mirrored.*classroom", re.I), "blueprint_b08", "dual classroom (b08)"),
]


def collect_blueprint_warnings(
    *,
    prompt: str,
    mode: str,
    use_blueprint: bool,
    blueprint_filename: Optional[str],
    blueprint_region_count: Optional[int],
    strict_blueprint: bool = True,
) -> List[str]:
    out: List[str] = []
    p = (prompt or "").strip()
    fn = (blueprint_filename or "").strip()

    if use_blueprint and strict_blueprint and mode == "ai":
        out.append(
            "Blueprint placement uses strict mode: object types and positions come from the "
            "PNG regions (legend colors), not from the LLM scene graph."
        )

    if use_blueprint and blueprint_region_count is not None and blueprint_region_count == 0:
        out.append(
            "Blueprint parsed to zero regions. Use RGB values from blueprint_parser.DEFAULT_COLOR_MAP "
            "or copy examples/blueprints/*.png."
        )

    if not (use_blueprint and fn):
        return out

    stem = fn.replace("\\", "/").split("/")[-1].lower()
    for pattern, substr, label in _RULES:
        if pattern.search(p) and substr not in stem:
            out.append(
                f'Prompt looks like a {label} layout, but the file is "{stem}". '
                f'Expected the filename to contain "{substr}" unless this is intentional.'
            )
            break

    return out
