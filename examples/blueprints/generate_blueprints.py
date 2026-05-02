"""
Generate sample blueprint PNGs for SceneForge marketing / QA prompts.

Uses the same RGB values as blueprint_parser.DEFAULT_COLOR_MAP so
parse_blueprint() classifies regions predictably. Run from repo root:

  python examples/blueprints/generate_blueprints.py

Outputs PNGs next to this script (examples/blueprints/*.png).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# Must match blueprint_parser.DEFAULT_COLOR_MAP
DESK = (160, 82, 45)
TABLE = (181, 101, 29)
CHAIR = (65, 105, 225)
BOARD = (34, 139, 34)
SHELF = (139, 69, 19)
LAMP = (255, 215, 0)
WHITE = (255, 255, 255)

W, H = 720, 540


def _new() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), WHITE)
    return img, ImageDraw.Draw(img)


def _save(img: Image.Image, name: str) -> None:
    out = Path(__file__).resolve().parent / name
    img.save(out, "PNG")
    print("wrote", out)


def gen_b1_studio() -> None:
    """Open-plan studio: desk island, chairs, shelf wall, lamp, north = top board strip."""
    img, d = _new()
    d.rectangle([40, 30, W - 40, 85], fill=BOARD)
    d.rectangle([80, 120, 320, 280], fill=DESK)
    d.rectangle([100, 290, 160, 350], fill=CHAIR)
    d.rectangle([200, 290, 260, 350], fill=CHAIR)
    d.rectangle([W - 120, 100, W - 35, 400], fill=SHELF)
    d.rectangle([W - 200, 120, W - 130, 190], fill=LAMP)
    _save(img, "blueprint_b01_studio.png")


def gen_b2_home_two_rooms() -> None:
    """Left = living (desk/chair), right = kitchen (table/chair, board, shelf)."""
    img, d = _new()
    mid = W // 2
    d.rectangle([50, 80, 300, 240], fill=DESK)
    d.rectangle([60, 260, 130, 330], fill=CHAIR)
    d.rectangle([160, 260, 230, 330], fill=CHAIR)
    d.rectangle([mid + 60, 90, mid + 300, 200], fill=TABLE)
    d.rectangle([mid + 100, 220, mid + 170, 290], fill=CHAIR)
    d.rectangle([mid + 50, 340, W - 60, 400], fill=BOARD)
    d.rectangle([mid + 50, 420, W - 60, H - 50], fill=SHELF)
    _save(img, "blueprint_b02_home_rooms.png")


def gen_b3_lecture_hall() -> None:
    """Wide green board band at top, desk rows, lamp corners."""
    img, d = _new()
    d.rectangle([30, 25, W - 30, 95], fill=BOARD)
    for row, y in enumerate([140, 220, 300]):
        x0 = 60 + row * 15
        for col in range(5):
            dx = x0 + col * 115
            d.rectangle([dx, y, dx + 75, y + 55], fill=DESK)
            d.rectangle([dx + 78, y + 10, dx + 108, y + 50], fill=CHAIR)
    d.rectangle([30, H - 90, 100, H - 35], fill=LAMP)
    d.rectangle([W - 100, H - 90, W - 35, H - 35], fill=LAMP)
    _save(img, "blueprint_b03_lecture_hall.png")


def gen_b4_l_office() -> None:
    """L-shape: vertical leg desk + horizontal leg."""
    img, d = _new()
    d.rectangle([60, 80, 140, 380], fill=DESK)
    d.rectangle([150, 300, 420, 380], fill=DESK)
    d.rectangle([160, 200, 230, 270], fill=CHAIR)
    d.rectangle([250, 200, 320, 270], fill=CHAIR)
    d.rectangle([W - 100, 60, W - 40, 200], fill=LAMP)
    d.rectangle([450, 40, W - 120, 90], fill=BOARD)
    _save(img, "blueprint_b04_l_office.png")


def gen_b5_cafeteria_row() -> None:
    """Long counter north = top as desk-brown strip; parallel chair blobs."""
    img, d = _new()
    d.rectangle([40, 40, W - 40, 110], fill=DESK)
    for i in range(8):
        x = 55 + i * 78
        d.rectangle([x, 130, x + 50, 200], fill=CHAIR)
    d.rectangle([50, H - 100, 120, H - 45], fill=DESK)
    d.rectangle([W - 130, H - 100, W - 50, H - 45], fill=DESK)
    _save(img, "blueprint_b05_cafeteria.png")


def gen_b6_library() -> None:
    """Shelf blocks along walls; desk islands center."""
    img, d = _new()
    d.rectangle([20, 20, 55, H - 20], fill=SHELF)
    d.rectangle([W - 55, 20, W - 20, H - 20], fill=SHELF)
    d.rectangle([200, 160, 360, 260], fill=DESK)
    d.rectangle([400, 160, 560, 260], fill=DESK)
    d.rectangle([250, 300, 310, 360], fill=LAMP)
    d.rectangle([480, 300, 540, 360], fill=LAMP)
    _save(img, "blueprint_b06_library.png")


def gen_b7_gallery() -> None:
    """East/west wall strips + aisle desks + bench chairs."""
    img, d = _new()
    d.rectangle([W - 80, 40, W - 25, H - 40], fill=BOARD)
    d.rectangle([25, 40, 80, H - 40], fill=BOARD)
    d.rectangle([200, 100, 520, 200], fill=DESK)
    d.rectangle([220, 220, 290, 280], fill=CHAIR)
    d.rectangle([360, 220, 430, 280], fill=CHAIR)
    d.rectangle([280, 40, 340, 90], fill=LAMP)
    d.rectangle([420, 40, 480, 90], fill=LAMP)
    _save(img, "blueprint_b07_gallery.png")


def gen_b8_dual_classroom() -> None:
    """Left and right mirrored classroom blocks."""
    img, d = _new()
    mid = W // 2
    # left half
    d.rectangle([40, 40, mid - 20, 100], fill=BOARD)
    d.rectangle([50, 130, 230, 240], fill=DESK)
    d.rectangle([250, 150, 310, 220], fill=CHAIR)
    d.rectangle([50, 280, 230, 370], fill=DESK)
    d.rectangle([250, 300, 310, 360], fill=CHAIR)
    # right half
    d.rectangle([mid + 20, 40, W - 40, 100], fill=BOARD)
    d.rectangle([mid + 40, 130, mid + 220, 240], fill=DESK)
    d.rectangle([mid + 240, 150, mid + 300, 220], fill=CHAIR)
    d.rectangle([mid + 40, 280, mid + 220, 370], fill=DESK)
    d.rectangle([mid + 240, 300, mid + 300, 360], fill=CHAIR)
    _save(img, "blueprint_b08_dual_classroom.png")


def gen_b9_retail() -> None:
    """Front counter strip, mid crates (desk brown), top banner (board green thin)."""
    img, d = _new()
    d.rectangle([40, 40, W - 40, 110], fill=DESK)
    d.rectangle([120, 200, 220, 300], fill=DESK)
    d.rectangle([280, 200, 380, 300], fill=DESK)
    d.rectangle([440, 200, 540, 300], fill=DESK)
    d.rectangle([80, 30, W - 80, 38], fill=BOARD)
    d.rectangle([W - 90, 130, W - 40, 280], fill=LAMP)
    _save(img, "blueprint_b09_retail.png")


def gen_b10_training_u() -> None:
    """
    Training lab: wide green board band at the front (top), brown desk U opening
    toward the board, small blue chair dots inside the U, shelf strip on the
    back wall (bottom) = storage behind the class / instructor zone.
    """
    img, d = _new()
    # Wide demonstration board band (front / north in typical map reads top)
    d.rectangle([40, 28, W - 40, 118], fill=BOARD)
    # U-shaped desk run: left leg, bottom bar, right leg (opening faces the board)
    d.rectangle([55, 165, 165, 455], fill=DESK)
    d.rectangle([555, 165, 665, 455], fill=DESK)
    d.rectangle([165, 385, 555, 470], fill=DESK)
    # Storage shelves along back wall (opposite the board)
    d.rectangle([35, H - 95, W - 35, H - 32], fill=SHELF)
    # Blue chair "dots" — small squares tucked along the inside of the U
    chair = 22
    dots = [
        (185, 410),
        (250, 410),
        (350, 410),
        (450, 410),
        (520, 410),
        (175, 320),
        (175, 240),
        (598, 320),
        (598, 240),
        (320, 355),
        (400, 355),
    ]
    for (cx, cy) in dots:
        d.rectangle([cx, cy, cx + chair, cy + chair], fill=CHAIR)
    _save(img, "blueprint_b10_training_lab.png")


def gen_x01_throne_hall() -> None:
    """Non-classroom: throne dais + flanking benches; lamps as torches; green rear as tapestry wall."""
    img, d = _new()
    d.rectangle([80, 50, W - 80, 130], fill=BOARD)
    d.rectangle([260, 200, 460, 360], fill=DESK)
    d.rectangle([120, 260, 220, 340], fill=TABLE)
    d.rectangle([500, 260, 600, 340], fill=TABLE)
    d.rectangle([40, 180, 95, 320], fill=LAMP)
    d.rectangle([W - 95, 180, W - 40, 320], fill=LAMP)
    d.rectangle([280, 400, 440, 470], fill=SHELF)
    _save(img, "blueprint_x01_throne_hall.png")


def gen_x02_courtyard() -> None:
    """Non-classroom: separate hedge strips (no corner merge), L-benches, lanterns, central plinth."""
    img, d = _new()
    d.rectangle([20, 20, W - 20, 65], fill=BOARD)
    d.rectangle([20, 85, 65, H - 20], fill=BOARD)
    d.rectangle([50, 400, 320, 450], fill=DESK)
    d.rectangle([400, 350, 670, 400], fill=DESK)
    d.rectangle([300, 220, 420, 320], fill=TABLE)
    d.rectangle([50, 120, 100, 200], fill=LAMP)
    d.rectangle([620, 120, 675, 200], fill=LAMP)
    d.rectangle([180, 320, 240, 380], fill=CHAIR)
    d.rectangle([480, 320, 540, 380], fill=CHAIR)
    _save(img, "blueprint_x02_courtyard.png")


def gen_x03_market() -> None:
    """Non-classroom: stall grid (table + chair), back storage shelf."""
    img, d = _new()
    d.rectangle([30, H - 85, W - 30, H - 35], fill=SHELF)
    for row in range(2):
        for col in range(3):
            x = 80 + col * 190
            y = 80 + row * 160
            d.rectangle([x, y, x + 120, y + 85], fill=TABLE)
            d.rectangle([x + 125, y + 20, x + 175, y + 75], fill=CHAIR)
    _save(img, "blueprint_x03_market.png")


def gen_x04_tavern() -> None:
    """Non-classroom: separated table islands (no touching browns), chairs, lamps, green back strip."""
    img, d = _new()
    d.rectangle([40, 40, W - 40, 95], fill=BOARD)
    islands = [(70, 150), (300, 140), (520, 160), (160, 310), (400, 300)]
    for i, (x, y) in enumerate(islands):
        fill = DESK if i % 2 == 0 else TABLE
        d.rectangle([x, y, x + 100, y + 70], fill=fill)
        d.rectangle([x + 108, y + 18, x + 158, y + 58], fill=CHAIR)
    d.rectangle([60, H - 120, 110, H - 50], fill=LAMP)
    d.rectangle([W - 110, H - 120, W - 60, H - 50], fill=LAMP)
    d.rectangle([320, H - 130, 400, H - 55], fill=LAMP)
    _save(img, "blueprint_x04_tavern.png")


def gen_x05_forest_camp() -> None:
    """Non-classroom: central fire (lamp), log ring (desk), seats (chair), green canopy band."""
    img, d = _new()
    d.rectangle([30, 25, W - 30, 75], fill=BOARD)
    d.rectangle([310, 230, 410, 330], fill=LAMP)
    for (x, y) in [(200, 280), (480, 280), (350, 380), (370, 180)]:
        d.rectangle([x, y, x + 90, y + 45], fill=DESK)
    for (cx, cy) in [(260, 250), (520, 250), (340, 340), (440, 340), (300, 200), (480, 200)]:
        d.rectangle([cx, cy, cx + 28, cy + 28], fill=CHAIR)
    d.rectangle([W - 80, 100, W - 25, H - 100], fill=SHELF)
    _save(img, "blueprint_x05_forest_camp.png")


def main() -> None:
    gen_b1_studio()
    gen_b2_home_two_rooms()
    gen_b3_lecture_hall()
    gen_b4_l_office()
    gen_b5_cafeteria_row()
    gen_b6_library()
    gen_b7_gallery()
    gen_b8_dual_classroom()
    gen_b9_retail()
    gen_b10_training_u()
    gen_x01_throne_hall()
    gen_x02_courtyard()
    gen_x03_market()
    gen_x04_tavern()
    gen_x05_forest_camp()
    print("Done. Copy a PNG as blueprint.png in the repo root to try strict blueprint mode, or upload via the UI.")


if __name__ == "__main__":
    main()
