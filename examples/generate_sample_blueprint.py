"""
Draw blueprint PNGs for SceneForge manual tests.

Colors match blueprint_parser.DEFAULT_COLOR_MAP so regions classify reliably:
  wooden_desk (160,82,45), table (181,101,29), chair (65,105,225),
  blackboard (34,139,34), bookshelf (139,69,19), lamp (255,215,0)

Run from repo root:
  python examples/generate_sample_blueprint.py

Writes:
  examples/blueprint_case1_classroom.png
  examples/blueprint_case2_library_nook.png
  examples/blueprint_case3_cafe_tables.png
  examples/blueprint_classroom.png  (alias of case 1)
  blueprint.png  (repo root — copy of case 1 for quick Streamlit tests)
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = Path(__file__).resolve().parent

# Must match blueprint_parser.DEFAULT_COLOR_MAP (RGB).
DESK = (160, 82, 45)
TABLE = (181, 101, 29)
CHAIR = (65, 105, 225)
BOARD = (34, 139, 34)
SHELF = (139, 69, 19)
LAMP = (255, 215, 0)
WHITE = (255, 255, 255)


def _base_canvas() -> tuple[Image.Image, ImageDraw.ImageDraw, int, int]:
    w, h = 960, 640
    image = Image.new("RGB", (w, h), WHITE)
    return image, ImageDraw.Draw(image), w, h


def draw_case1_classroom() -> Image.Image:
    """Front wall board + two desk rows + lamp (classroom-style)."""
    image, draw, w, h = _base_canvas()
    draw.rectangle([60, 36, w - 60, 132], fill=BOARD)
    draw.rounded_rectangle([100, 280, 280, 420], radius=20, fill=DESK)
    draw.ellipse([130, 440, 250, 560], fill=CHAIR)
    draw.rounded_rectangle([400, 280, 580, 420], radius=20, fill=DESK)
    draw.ellipse([430, 440, 550, 560], fill=CHAIR)
    draw.rounded_rectangle([680, 280, 880, 420], radius=20, fill=DESK)
    draw.ellipse([720, 440, 840, 560], fill=CHAIR)
    draw.rounded_rectangle([360, 460, 600, 560], radius=18, fill=TABLE)
    draw.ellipse([w - 140, 150, w - 48, 238], fill=LAMP)
    draw.rounded_rectangle([40, 200, 120, 380], radius=14, fill=SHELF)
    return image


def draw_case2_library_nook() -> Image.Image:
    """Reading corner: tall shelf, chairs, board, lamp."""
    image, draw, w, h = _base_canvas()
    draw.rectangle([w // 2 - 200, 40, w // 2 + 200, 120], fill=BOARD)
    draw.rounded_rectangle([60, 140, 160, 520], radius=12, fill=SHELF)
    draw.ellipse([220, 380, 320, 500], fill=CHAIR)
    draw.ellipse([360, 380, 460, 500], fill=CHAIR)
    draw.rounded_rectangle([500, 400, 760, 500], radius=16, fill=TABLE)
    draw.ellipse([800, 380, 900, 500], fill=CHAIR)
    draw.ellipse([w - 100, 200, w - 40, 280], fill=LAMP)
    return image


def draw_case3_cafe_tables() -> Image.Image:
    """Several small tables + chairs (good for grid / tavern-style prompts)."""
    image, draw, w, h = _base_canvas()
    draw.rectangle([80, 40, w - 80, 100], fill=BOARD)
    positions = [
        (140, 200, 240, 300),
        (320, 200, 420, 300),
        (500, 200, 600, 300),
        (680, 200, 780, 300),
        (230, 360, 330, 460),
        (410, 360, 510, 460),
        (590, 360, 690, 460),
    ]
    for x0, y0, x1, y1 in positions:
        draw.rounded_rectangle([x0, y0, x1, y1], radius=14, fill=TABLE)
        cx = (x0 + x1) // 2
        draw.ellipse([cx - 40, y1 + 20, cx + 40, y1 + 100], fill=CHAIR)
    draw.ellipse([w - 110, 120, w - 50, 200], fill=LAMP)
    return image


def main() -> None:
    cases = [
        ("blueprint_case1_classroom.png", draw_case1_classroom),
        ("blueprint_case2_library_nook.png", draw_case2_library_nook),
        ("blueprint_case3_cafe_tables.png", draw_case3_cafe_tables),
    ]
    EXAMPLES.mkdir(parents=True, exist_ok=True)
    for name, fn in cases:
        path = EXAMPLES / name
        fn().save(path, format="PNG", optimize=True)
        print(f"Wrote: {path}")

    img1 = draw_case1_classroom()
    img1.save(EXAMPLES / "blueprint_classroom.png", format="PNG", optimize=True)
    print(f"Wrote: {EXAMPLES / 'blueprint_classroom.png'} (same as case 1)")

    root_bp = PROJECT_ROOT / "blueprint.png"
    img1.save(root_bp, format="PNG", optimize=True)
    print(f"Wrote: {root_bp}")


if __name__ == "__main__":
    main()
