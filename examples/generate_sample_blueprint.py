"""
Draw a simple classroom-style blueprint PNG for SceneForge manual tests.

Run from repo root:
  python examples/generate_sample_blueprint.py

Writes examples/blueprint_classroom.png and blueprint.png (repo root).
"""

from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUT_EXAMPLE = Path(__file__).resolve().parent / "blueprint_classroom.png"
OUT_DEFAULT = PROJECT_ROOT / "blueprint.png"

# Saturated colors (RGB) — strong contrast on white helps simple color-region parsers.
WHITE = (255, 255, 255)
DESK_BROWN = (120, 72, 40)
CHAIR_BLUE = (30, 90, 200)
BOARD_GREEN = (40, 140, 60)
LAMP_YELLOW = (240, 200, 40)


def main() -> None:
    w, h = 960, 640
    image = Image.new("RGB", (w, h), WHITE)
    draw = ImageDraw.Draw(image)

    # Blackboard band at the "front" of the room (top of image).
    draw.rectangle([80, 40, w - 80, 140], fill=BOARD_GREEN)

    # Two desk clusters (brown) with chair blobs (blue) in front.
    draw.ellipse([120, 320, 340, 480], fill=DESK_BROWN)
    draw.ellipse([160, 500, 300, 580], fill=CHAIR_BLUE)

    draw.ellipse([620, 320, 840, 480], fill=DESK_BROWN)
    draw.ellipse([660, 500, 800, 580], fill=CHAIR_BLUE)

    # Teacher desk / table (brown) center-bottom.
    draw.rounded_rectangle([380, 400, 580, 520], radius=16, fill=DESK_BROWN)

    # Lamp (yellow) — corner.
    draw.ellipse([w - 120, 160, w - 40, 240], fill=LAMP_YELLOW)

    OUT_EXAMPLE.parent.mkdir(parents=True, exist_ok=True)
    image.save(OUT_EXAMPLE, format="PNG", optimize=True)
    image.save(OUT_DEFAULT, format="PNG", optimize=True)
    print(f"Wrote: {OUT_EXAMPLE}")
    print(f"Wrote: {OUT_DEFAULT}")


if __name__ == "__main__":
    main()
