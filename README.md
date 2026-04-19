# Omniverse Scene Builder Write-Up

## Overview

This project turns a natural-language prompt into a small 3D USD scene using:

- NVIDIA Omniverse Kit APIs for USD stage creation and asset referencing
- A free local Ollama model for object-list extraction
- A local handcrafted USDA asset library
- A flattened USDA export for online viewers
- A lightweight local preview window that opens automatically

The main entry point is:

- `main.py`

## What Was Built

### 1. Omniverse scene generation pipeline

The project now:

1. Accepts a text prompt
2. Detects the scene type
3. Uses a local LLM to suggest scene objects
4. Falls back to deterministic object sets when needed
5. Uses deterministic scene layouts to place objects cleanly
6. Creates a USD stage in Omniverse
7. References local USDA asset files into the stage
8. Exports:
   - `generated_scene.usda`
   - `generated_scene_flat.usda`

The upgraded flow is now:

- `main.py`
- `run_omniverse_scene.py`
- `natural_language_scene.py`
- `ai_scene_graph.py`
- `objaverse_loader.py`

### 2. Local asset library

The project includes a reusable local USDA asset library in `assets/`.

Current assets:

- `desk.usda`
- `table.usda`
- `chair.usda`
- `blackboard.usda`
- `lamp.usda`
- `bookshelf.usda`
- `throne.usda`
- `banner.usda`
- `torch.usda`
- `barrel.usda`
- `crate.usda`
- `campfire.usda`
- `pine_tree.usda`
- `bench.usda`
- `market_stall.usda`

### 3. Main runner

`main.py` now does the following in order:

1. Checks that Ollama is running
2. Checks that the configured model exists
3. Runs the Omniverse scene builder
4. Exports a flattened USDA copy for web viewing
5. Opens the local previewer automatically

### 4. Local previewer

`view_generated_scene.py` is a lightweight desktop previewer. It is not a full RTX renderer, but it gives a fast 3D visual sanity check and opens automatically after a successful run.

### 5. Flattened export for web viewers

The original generated scene uses referenced local asset files. Many online USD viewers do not resolve those local references correctly.

To solve that, `main.py` now exports:

- `generated_scene_flat.usda`

This file is self-contained and is the correct one to upload to online viewers.

### 6. AI scene graph module

`ai_scene_graph.py` was added to generate structured scene JSON in the form:

```json
[
  {
    "name": "wooden_desk",
    "position": [-2, 0, 1],
    "rotation": [0, 0, 0],
    "scale": [1, 1, 1]
  }
]
```

It supports:

- local Ollama prompting
- strict JSON extraction
- few-shot prompt augmentation from `scene_dataset.json`
- deterministic fallback mode
- layout constraints:
  - grounded Y
  - clamped bounds
  - overlap reduction
- a simple layout quality score

### 7. Dataset support

`scene_dataset.json` was added to support:

- few-shot prompting
- future local fine-tuning or adapter training
- prompt-to-scene examples for stable structured output

### 8. Objaverse integration layer

`objaverse_loader.py` was added as the new asset retrieval layer.

Current behavior:

- first tries a local Objaverse-style cache/index if present
- then falls back to the local handcrafted asset library

This keeps the project runnable offline and without cloud APIs.

## Problems Fixed So Far

### Problem 1: Missing Omniverse runtime

What happened:
- The machine had Python 3.13, but current Omniverse Kit Python packages require Python 3.12.

Fix:
- Installed Python 3.12
- Created a dedicated Omniverse virtual environment
- Installed `omniverse-kit`

### Problem 2: No free LLM path

What happened:
- The original flow assumed OpenAI.

Fix:
- Installed Ollama
- Pulled `llama3.2:1b`
- Switched extraction to local Ollama

### Problem 3: Online viewers only showed cubes

What happened:
- The generated scene referenced external local asset files
- Online viewers typically do not resolve local references

Fix:
- Added flattened export: `generated_scene_flat.usda`

### Problem 4: Object positioning was bad

What happened:
- The system used raw LLM coordinates directly
- That caused floating, underground, and scattered assets

Fix:
- Replaced direct LLM positioning with scene-template placement
- The LLM now suggests objects, but the script controls layout
- All default placements now keep `Y = 0.0` for grounded scenes

### Problem 5: Need AI-driven structured generation without breaking stability

Fix:
- Added `ai_scene_graph.py`
- Added `scene_dataset.json`
- Added `--mode=ai` and `--mode=rule`
- Added constraint and fallback logic

## Current Prompt Types

The project now supports these scene families:

- Classroom
- Throne room
- Forest camp
- Market
- Tavern
- Generic studio fallback

Example prompts:

- `a medieval classroom with wooden desks and a blackboard`
- `a royal throne room with banners and torches`
- `a forest camp with trees, crates and a campfire`
- `a medieval market with vendor stalls and barrels`
- `a cozy tavern with tables, chairs and torches`

## Placement Strategy

The new placement strategy works like this:

1. Detect the scene family from the prompt
2. Build a few-shot prompt from `scene_dataset.json`
3. Ask the local model for structured scene JSON
4. Normalize names and transforms
5. Clamp and clean positions
6. Resolve overlaps
7. Fall back to deterministic rule mode if parsing fails

Examples:

- Classroom:
  - desks arranged in rows
  - chairs placed behind desks
  - blackboard at the front
  - bookshelf and lamp at the sides

- Throne room:
  - throne centered at the back
  - banners flanking the throne
  - torches near the walls
  - benches in front

- Forest camp:
  - campfire at the center
  - trees around the perimeter
  - crates and barrels near the fire

## Important Files

- `main.py`
  Main entry point

- `run_omniverse_scene.py`
  Starts Omniverse Kit and calls the scene builder

- `natural_language_scene.py`
  Omniverse stage building and transform application

- `ai_scene_graph.py`
  AI scene graph generation, few-shot prompting, constraints, scoring, and fallback

- `objaverse_loader.py`
  Objaverse-style asset resolution with local cache and fallback

- `scene_dataset.json`
  Few-shot scene examples

- `view_generated_scene.py`
  Local quick preview window

- `generated_scene.usda`
  Working scene with references

- `generated_scene_flat.usda`
  Self-contained file for online viewers

- `RUN_ORDER.txt`
  Short operational guide

## How To Run

Use:

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py "a medieval classroom with wooden desks and a blackboard"
```

Force AI mode:

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py --mode=ai "a medieval classroom with wooden desks and a blackboard"
```

Force rule mode:

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py --mode=rule "a medieval classroom with wooden desks and a blackboard"
```

If you do not want the preview window to auto-open:

```powershell
set OPEN_VIEWER=0
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py "a royal throne room with banners and torches"
```

## What To Upload To Online Viewers

Upload:

- `generated_scene_flat.usda`

Do not upload:

- `generated_scene.usda`

because that file relies on local asset references.

## Current Limitations

- The local previewer is a simplified visualization, not full USD rendering
- The local LLM sometimes returns unsupported object names or invalid JSON, so the system may fall back to deterministic rule mode
- Assets are handcrafted USDA models, not photoreal production assets
- The current system is best for compact scene demos rather than large open worlds
- The Objaverse layer is implemented as a local-cache-first integration point; it does not depend on network access
- Flattened export may fail in the current OneDrive Unicode path because Pixar USD safe-write rename is path-sensitive on this machine

## Recommended Next Improvements

1. Improve the Ollama prompt so the model returns more useful supported asset names
2. Add floor, walls, and environment shells for each scene family
3. Add decorative props such as books, chandeliers, rugs, shields, tents, and signs
4. Export per-prompt scene filenames instead of always overwriting the same output files
5. Add a GUI prompt box instead of only command-line execution
