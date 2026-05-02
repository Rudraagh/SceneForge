# Extra blueprint prompts (not on the marketing page)

Use these with **blueprint mode on** and the matching PNG from `examples/blueprints/`. Colors are still the six canonical blueprint colors; names you get from `parse_blueprint` may read as `wooden_desk` / `chair` / `blackboard` / etc., while the **text prompt** carries the real scene intent (throne, hedge, stall, …).

| Blueprint file | Suggested prompt (copy into studio) |
|----------------|-------------------------------------|
| `blueprint_x01_throne_hall.png` | `a royal throne room with a central raised dais, side benches for courtiers, torches along the side walls, and a tapestry wall behind the throne` |
| `blueprint_x02_courtyard.png` | `outdoor courtyard with hedge along two sides, stone benches in an L along the paths, lanterns at the corners, and a low central stone plinth` |
| `blueprint_x03_market.png` | `a medieval market with two rows of vendor stalls facing an aisle, crates implied by stall blocks, and a storage wall at the back` |
| `blueprint_x04_tavern.png` | `a cozy tavern with scattered round tables, stools, oil lamps for warm light, and a long painted wall behind the bar` |
| `blueprint_x05_forest_camp.png` | `a forest camp with a central campfire ring, log benches in a rough circle, a few seat stones, and a dark tree line along one edge` |

Regenerate all PNGs (including these) from repo root:

```bash
python examples/blueprints/generate_blueprints.py
```

See also `README.md` in this folder for the **b1–b10** pairs used by the web sample cards.
