# Sample blueprint PNGs

These images use the same RGB palette as `blueprint_parser.DEFAULT_COLOR_MAP` (brown ≈ desk/table, blue ≈ chair, green ≈ blackboard, darker brown ≈ bookshelf, gold ≈ lamp, **dark slate ≈ door/exit**) on a white background so `parse_blueprint()` can detect regions.

## Files ↔ “Best with blueprint” prompts (marketing ids b1–b10)

| File | Use with prompt (summary) |
|------|---------------------------|
| `blueprint_b01_studio.png` | b1 — Open-plan studio; desk, chair, shelf, lamp; north wall strip |
| `blueprint_b02_home_rooms.png` | b2 — Living + kitchen; brown desk/table zones, blue chairs, green board strip in **each** room + kitchen shelf |
| `blueprint_b03_lecture_hall.png` | b3 — Lecture hall grid; board band + desk/chair rows + lamps + **rear door** (slate blob) |
| `blueprint_b04_l_office.png` | b4 — L-shaped office; desks, chairs, lamp, board |
| `blueprint_b05_cafeteria.png` | b5 — Long counter + parallel chairs + end barrels as desk blobs |
| `blueprint_b06_library.png` | b6 — Perimeter shelves + central study tables + corner lamps |
| `blueprint_b07_gallery.png` | b7 — Side wall board strips + aisle desk + benches/chairs + lamps |
| `blueprint_b08_dual_classroom.png` | b8 — Mirrored left/right classroom halves |
| `blueprint_b09_retail.png` | b9 — Front counter + mid-floor desk blocks + thin top strip + lamp |
| `blueprint_b10_training_lab.png` | b10 — Wide green board band (front), brown U-desks opening toward it, small blue chair dots inside the U, brown shelf strip on the back wall |

Exact prompt strings live in `frontend/src/components/SiteMarketing.tsx` (`SamplePromptsSection`, entries `b1`–`b10`).

## How to try in SceneForge

1. **Web UI:** Enable blueprint mode, upload the matching PNG (or paste base64 if your flow supports it).
2. **CLI / root file:** Copy one PNG to the repo root as `blueprint.png` (your `.gitignore` ignores this name so it is not committed), then run `direct_usd_scene.py` / `main.py` with blueprint mode as you usually do.

## Non-classroom prompts (not in the frontend)

Extra prompt ↔ PNG pairs for throne hall, courtyard, market, tavern, and forest camp live in **`extra_prompts.md`** (`blueprint_x01` … `blueprint_x05`). Those files are **not** linked from the React marketing page.

## Regenerate artwork

From repo root:

```bash
python examples/blueprints/generate_blueprints.py
```
