# SceneForge

SceneForge turns a natural-language prompt, and optionally a simple blueprint image, into a USD scene. It combines local LLM scene planning, deterministic layout rules, asset retrieval, blueprint-guided placement, and USDA export into one offline-friendly pipeline.

The repo supports two scene-authoring backends:

- `direct_usd_scene.py`: pure Pixar USD path, no Omniverse Kit runtime required
- `natural_language_scene.py` via `run_omniverse_scene.py`: Omniverse Kit authoring path

The default user-facing entry point is `main.py`.

The repo also includes demo UIs:

- `app.py`: Streamlit interface for blueprint upload, pipeline execution, metrics, logs, explanation output, and Blender launch
- `api_app.py` + `frontend/`: responsive **React + Vite + Tailwind** studio with the same controls as Streamlit, a **Plotly 3D** prim picker, and **Ollama** object explanations (see `frontend/README.md`)

The single-page marketing experience (hero through workflow) lives in `frontend/src/components/SiteMarketing.tsx` and includes: platform capabilities, architecture, interoperability, research scenarios, observability, **positioning** (SceneForge vs other approaches), **sample prompts** with copy-to-clipboard, **requirements** (Python / Node / Ollama / disk plus manifest paths), **privacy and data flow**, **FAQ** (GPU, Blender vs USDA, Ollama locality, Objaverse/network, rule vs AI mode), quick start, and footer anchors. `frontend/src/App.tsx` wires those sections, header navigation, and the studio shell.

## What It Can Do

- Convert a prompt like `"a medieval classroom with wooden desks and a blackboard"` into a structured scene graph
- Use a local Ollama model for JSON scene generation
- Fall back to deterministic scene templates when AI output is invalid or unavailable
- Parse a color-coded `blueprint.png` and map it into world-space placement
- Run a refinement loop over blueprint scenes to improve spacing and relational consistency
- Extract simple object relationships from prompt text such as `on`, `beside`, and `near`
- Infer a few special-case relations such as solar-system orbital relations
- Resolve assets from:
  - cached normalized assets
  - Objaverse candidates
  - curated free-source downloads
  - local USDA fallback assets in `assets/`
- Normalize external meshes for stable placement
- Procedurally build textured planets for solar-system scenes
- Add a simple room shell around the arranged scene
- Export `generated_scene.usda`
- Try to export a flattened self-contained USDA for easier sharing
- Open a lightweight local viewer for quick inspection
- Run a Streamlit demo UI for research presentation and demos
- Run the **React + FastAPI** web studio: generation UI, Plotly object explorer, Ollama explanations, and an on-page **guide** (capabilities through FAQ, sample prompts, privacy, requirements, quick start)

## Architecture

The high-level flow is:

1. `main.py` validates Ollama availability and the selected model.
2. `main.py` launches `direct_usd_scene.py` in AI or rule mode.
3. `direct_usd_scene.py` builds a scene graph from:
   - local LLM output via `ai_scene_graph.py`, or
   - deterministic templates and constraints
4. If blueprint mode is on and the scene is not a deterministic **solar system**, `blueprint.png` is parsed and either **replaces** the scene (strict mode with regions) or **merges** positions—this applies to **both AI and rule** paths in `direct_usd_scene.build_scene_from_prompt()`.
5. Prompt relations are extracted or inferred.
6. The graph is arranged and optionally refined by layout and agent loops (skipped in deterministic / rule mode except blueprint placement above).
7. `objaverse_loader.py` resolves the best available asset for each object.
8. USD prims are authored, transformed, scaled, and exported.
9. `main.py` optionally flattens the scene and launches `view_generated_scene.py`.

## Research / Retrieval Capabilities

This repo is not a web research system, but it does have several retrieval-style capabilities that matter for scene generation:

- `ai_scene_graph.py`
  - builds few-shot prompts from `scene_dataset.json`
  - queries a local Ollama model
  - normalizes and constrains model output
  - falls back safely when the model returns bad JSON or poor structure

- `objaverse_loader.py`
  - searches Objaverse LVIS categories when the package is available
  - scores candidate meshes against object-specific target dimensions
  - downloads curated free assets for some categories
  - caches and reuses normalized assets
  - procedurally generates planets with downloaded textures when needed

- `blueprint_parser.py`
  - reads a simple blueprint image
  - identifies colored object regions
  - classifies them by nearest palette color

- `relations.py` and `relation_infer.py`
  - recover lightweight semantic relations from prompt text
  - add special inferred relations for known prompt types

In practice, the project "researches" a scene by combining local LLM reasoning, few-shot examples, asset retrieval, candidate scoring, and prompt/blueprint interpretation.

## Supported Scene Families

`ai_scene_graph.detect_scene_type()` currently recognizes:

- `courtyard` (courtyard / patio / plaza / atrium / quad, or **outdoor** prompts with garden, park, bench, tree, fountain, shade, etc.)
- `classroom`
- `throne_room`
- `forest_camp`
- `market`
- `tavern`
- `solar_system`
- `studio` fallback

Rule mode uses a fixed template per type (for example **courtyard** uses benches, pine trees, and a central **barrel** as a stand-in where no dedicated fountain mesh exists in the canonical library).

## Supported Object Library

The built-in canonical object set currently includes:

- `wooden_desk`
- `table`
- `chair`
- `blackboard`
- `lamp`
- `bookshelf`
- `throne`
- `banner`
- `torch`
- `barrel`
- `crate`
- `campfire`
- `pine_tree`
- `bench`
- `market_stall`
- `sun`
- `mercury`
- `venus`
- `earth`
- `mars`
- `jupiter`
- `saturn`
- `uranus`
- `neptune`

Synonyms such as `desk`, `board`, `bookcase`, `tree`, `fire`, `stall`, **`fountain` / `water_feature` → `barrel`**, and related forms are canonicalized into those supported names.

## Main Files And What They Do

### Entrypoints

- `main.py`
  - main CLI entry point
  - checks Ollama server reachability
  - checks the configured Ollama model is installed
  - runs the scene builder
  - exports a flattened USDA copy when possible
  - optionally opens the local previewer

- `direct_usd_scene.py`
  - primary USD builder used by `main.py`
  - authors a scene in memory with Pixar USD APIs
  - supports `--mode`, blueprint mode, output paths, help, and asset-source flags
  - applies room shells, assets, transforms, scaling, and export

- `run_omniverse_scene.py`
  - Omniverse Kit bootstrapper
  - enables `omni.usd` and `omni.kit.commands`
  - runs `natural_language_scene.build_scene_from_prompt()`

- `natural_language_scene.py`
  - Omniverse-native scene authoring path
  - creates prims and references through Kit commands
  - applies transforms and exports through an ASCII-safe temp path

- `app.py`
  - Streamlit UI for the blueprint-driven pipeline
  - saves uploaded blueprint images as `blueprint.png`
  - runs `direct_usd_scene.py -b "<prompt>"` in a subprocess
  - forces UTF-8 subprocess IO on Windows to avoid Unicode path crashes
  - displays logs, parsed metrics, explanation lines, output path, and Blender launch controls

- `api_app.py`
  - FastAPI service for the React studio (`uvicorn api_app:app --reload --host 127.0.0.1 --port 8765`)
  - `POST /api/generate` — runs `pipeline_service.run_pipeline()` (subprocess `direct_usd_scene.py` with the **resolved pipeline Python**)
  - `GET /api/scene-objects` — lists `/World` prims for Plotly (via `list_scene_objects_resolved()` / optional `list_scene_objects_json.py` subprocess)
  - `POST /api/explain-object` — Ollama-backed prim explanations via `scene_explainer.explain_object_in_scene()`
  - `GET /api/ollama-status`, `GET /api/pipeline-python`, `GET /api/health`, `POST /api/open-blender`
  - CORS defaults to local Vite origins; override with `SCENEFORGE_CORS_ORIGINS` (comma-separated)

- `pipeline_service.py`
  - shared subprocess runner, log parsing (`extract_metrics`, `extract_output_path`, `extract_explanation`), blueprint bytes to disk, Blender launch helper
  - `resolve_pipeline_python()` — prefers **`SCENEFORGE_PYTHON`** when set and the file exists, else an in-module default candidate path (override in `pipeline_service.py` for your lab), else **`sys.executable`**
  - **`list_scene_objects_resolved()`** — calls `list_scene_objects()` in-process; if `pxr` is missing in the **API** interpreter but the pipeline Python has USD, delegates to `list_scene_objects_json.py` in a subprocess so the 3D picker still works

- `list_scene_objects_json.py`
  - small CLI: prints JSON array of scene objects for a USDA path; used only by `list_scene_objects_resolved()` when the API process cannot import `pxr`

- `scene_explainer.py`
  - USD prim enumeration and Ollama `/api/generate` calls for explanations
  - connection-refused errors (including **Windows WinError 10061**) surface an actionable message (start Ollama / `ollama serve`, `OLLAMA_API_URL`, Recheck in the UI)

### Scene generation and layout

- `ai_scene_graph.py`
  - canonicalizes object names
  - detects scene type from prompt text
  - loads few-shot examples from `scene_dataset.json`
  - builds Ollama prompts
  - extracts JSON from model output
  - constrains coordinates and spacing
  - provides deterministic scene templates
  - scores layout quality
  - builds graph structures with nodes, edges, and lookup tables
  - includes a training stub for future fine-tuning

- `layout_engine.py`
  - graph-only layout helper focused on classroom-style layouts
  - arranges desks into a grid
  - places chairs relative to desks
  - places boards at the front
  - stores room dimensions in graph metadata
  - adds `near` relationship edges between chairs and desks

- `agents.py`
  - lightweight graph refinement agents
  - `domain_agent()` nudges objects to satisfy `beside`, `on`, and `near`
  - `evaluator_agent()` scores spacing quality
  - `reflection_agent()` summarizes layout quality in plain English

- `relations.py`
  - regex-based extraction of prompt relations
  - currently supports `on`, `beside`, and `near`

- `relation_infer.py`
  - adds special-case inferred relations
  - currently handles a solar-system prompt shortcut

### Blueprint pipeline

- `blueprint_parser.py`
  - reads `blueprint.png`
  - flood-fills colored regions
  - matches region colors to known object classes
  - returns normalized object positions

- `blueprint_mapper.py`
  - converts normalized blueprint coordinates into world coordinates
  - maps blueprint detections into scene objects
  - can merge blueprint positions into an existing generated scene

- `blueprint_agents.py`
  - evaluates blueprint scene placement
  - infers semantic relations such as chair-to-desk and desk-to-board
  - reflects on relational correctness
  - computes a combined refinement score
  - adaptively decides whether to continue refinement
  - refines positions and facing directions conservatively
  - generates human-readable explanation summaries

### Asset retrieval and normalization

- `objaverse_loader.py`
  - central asset resolver
  - defines target sizes and retrieval specs per object type
  - supports per-object and CLI-driven source order
  - optionally searches Objaverse candidates
  - downloads curated free-source assets for some categories
  - normalizes meshes so pivots and scale are stable
  - caches metadata and removes stale cache entries
  - procedurally builds planet assets with preview materials and textures
  - falls back to the local USDA asset library in `assets/`

### Preview and outputs

- `view_generated_scene.py`
  - simple local preview app built on `matplotlib`
  - draws custom proxy shapes for known objects
  - can also render referenced mesh geometry when available
  - supports save-only preview rendering via env var

- `scene_dataset.json`
  - few-shot examples used to improve local model prompting

- `requirements.txt`
  - lightweight dependency install file for the UI and non-Omniverse Python utilities

- `generated_scene.usda`
  - latest generated scene with references

- `generated_scene_flat_*.usda`
  - flattened export variant for easier sharing when export succeeds

### Utility / temporary files

- `tempCodeRunnerFile.py`
- `tempCodeRunnerFile.python`
  - editor scratch files, not part of the core pipeline

## Important Functions

These are the highest-leverage functions if you are modifying behavior:

- `main.py`
  - `check_ollama_server()`
  - `check_ollama_model()`
  - `run_scene_builder()`
  - `export_flattened_scene()`
  - `launch_viewer()`

- `direct_usd_scene.py`
  - `build_scene_from_prompt()` (blueprint path shared for AI and rule modes; solar-system deterministic skips blueprint merge)
  - `add_room_shell()`
  - `create_placeholder_geometry()`
  - `export_stage_safely()`
  - `_bbox_fit_scale()`

- `ai_scene_graph.py`
  - `generate_scene()`
  - `generate_rule_scene()`
  - `query_local_model()`
  - `build_few_shot_prompt()`
  - `_apply_scene_constraints()`
  - `score_layout()`
  - `build_graph()`

- `objaverse_loader.py`
  - `find_asset()`
  - `retrieve_objaverse_asset()`
  - `retrieve_free_source_asset()`
  - `_convert_external_mesh_to_usda()`
  - `_score_mesh_for_object()`
  - `_retrieve_planet_asset()`
  - `cleanup_stale_cache()`

- `pipeline_service.py`
  - `list_scene_objects_resolved()`, `run_pipeline()`, `resolve_pipeline_python()`

- `blueprint_agents.py`
  - `evaluate_scene()`
  - `infer_relationships()`
  - `reflect_scene()`
  - `compute_score()`
  - `adaptive_controller()`
  - `refine_scene()`
  - `explain_scene()`

## How To Run

### Install dependencies

For the Streamlit app and helper utilities:

```powershell
python -m pip install -r requirements.txt
```

This installs:

- `streamlit`
- `Pillow`
- `matplotlib`
- `numpy`
- `trimesh`
- `plotly`
- `fastapi`, `uvicorn`, `pydantic`, `python-multipart` (HTTP API for the React studio)
- `usd-core` (PyPI package name for Pixar USD bindings used as `pxr` when available)

Note:

- the core scene pipeline requires Pixar USD Python bindings (`pxr`); the **same** interpreter that runs `direct_usd_scene.py` should have them, or configure `SCENEFORGE_PYTHON` and use `list_scene_objects_json.py` delegation for `/api/scene-objects`
- the Omniverse backend also requires Omniverse Kit runtime support
- AI mode also requires Ollama running locally with the configured model pulled

### Default flow

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py "a medieval classroom with wooden desks and a blackboard"
```

### Show CLI help

All main entry points support `-h`, `--help`, and `-help`.

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py -help
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe direct_usd_scene.py -help
```

### Force AI scene generation

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py --mode=ai "a royal throne room with banners and torches"
```

### Force rule-based generation

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py --mode=rule "a forest camp with trees, crates and a campfire"
```

### Run strict blueprint mode

This uses `blueprint.png` as the dominant placement source.

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe direct_usd_scene.py -b "a classroom with desks and chairs"
```

### Control asset retrieval

Use these flags from `main.py`, `direct_usd_scene.py`, or `run_omniverse_scene.py`.

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe main.py --mode=rule --prefer-local-assets --disable-objaverse "a classroom with wooden desks and chairs"
```

Useful flags:

- `--prefer-local-assets`
- `--asset-source-order local,free,cache,objaverse,procedural`
- `--disable-cache`
- `--disable-objaverse`
- `--disable-free`
- `--disable-procedural`
- `--objaverse-candidate-limit 10`
- `--objaverse-min-score 0.7`
- `-o output.usda` or `--output output.usda`

### Run the Omniverse Kit backend directly

```powershell
C:\Users\arun1\omniverse-kit-venv312\Scripts\python.exe run_omniverse_scene.py --mode=ai "a medieval market with stalls and barrels"
```

### Run the web studio (FastAPI + Vite)

From the repo root, install Python deps, start the API, then follow `frontend/README.md` for `npm install` and `npm run dev` (Vite proxies `/api/*` to port **8765**).

```powershell
python -m pip install -r requirements.txt
uvicorn api_app:app --reload --host 127.0.0.1 --port 8765
```

The React client shows API error **details** for generate, scene-objects, and explain requests (not only generic status text). The studio includes a short note under **Rule** mode describing template choice and blueprint merge behavior.

### Run the Streamlit UI

```powershell
streamlit run app.py
```

UI flow:

1. Upload a blueprint image
2. Choose whether to use blueprint placement
3. Enter a prompt
4. Choose `ai` or `rule` mode
5. Mark asset flags such as local preference, Objaverse disable, cache disable, free-source disable, procedural disable, candidate limit, and minimum score
6. Click `Generate Scene`
7. Review logs, metrics, explanation output, and the exported USD path
8. Open the USD in Blender from the UI if Blender is installed at the configured path

## Environment Variables

- `SCENEFORGE_PYTHON`
  - optional absolute path to the Python interpreter used to run `direct_usd_scene.py` from the FastAPI UI
  - when unset, `pipeline_service.resolve_pipeline_python()` uses an in-repo preferred path constant if that file exists, otherwise **`sys.executable`** (the interpreter running uvicorn)

- `SCENEFORGE_CORS_ORIGINS`
  - comma-separated origins allowed by the FastAPI CORS middleware (defaults include `http://127.0.0.1:5173` and `http://localhost:5173`)

- `SCENEFORGE_BLENDER_PATH`
  - optional override for the Blender executable used by `POST /api/open-blender` and Streamlit

- `OLLAMA_API_URL`
  - default: `http://localhost:11434`
  - base URL used by `main.py` to validate Ollama and by `scene_explainer` / `ai_scene_graph` for HTTP calls

- `OLLAMA_EXPLAIN_MODEL`, `OLLAMA_EXPLAIN_NUM_CTX`, `OLLAMA_EXPLAIN_NUM_PREDICT`
  - optional overrides for prim-level explanations (`scene_explainer.py`)

- `SCENE_GRAPH_OLLAMA_MODEL`
  - default: `llama3.2:1b`
  - local Ollama model name used for scene graph generation

- **RAG (retrieval before Ollama)** — `sceneforge/rag.py` embeds `scene_dataset.json`, `sceneforge/asset_registry.py` entries, and `rag_corpus/sceneforge_rag.md`, then prepends top matches to **AI scene-graph** prompts (`build_few_shot_prompt`) and **prim explanations** (`scene_explainer`). Pull an embedding model first, e.g. `ollama pull nomic-embed-text`.
  - `OLLAMA_EMBED_MODEL` — default `nomic-embed-text`
  - `SCENEFORGE_RAG_TOP_K` — default `4`
  - `SCENEFORGE_RAG_EMBED_TIMEOUT_S` — default `20` (seconds per embedding HTTP call)
  - `SCENEFORGE_DISABLE_RAG` — set to `1` to turn retrieval off (CI/tests or when no embed model is installed)

- `OPEN_VIEWER`
  - default: `1`
  - set to `0` to skip auto-opening the preview window

- `PREVIEW_SAVE_ONLY`
  - default: `0`
  - set to `1` to save a preview PNG instead of opening a window

- `SCENE_ASSET_CACHE_DIR`
  - cache directory for normalized downloaded assets

- `SCENE_SAFE_GENERATED_CACHE_DIR`
  - cache directory for procedurally generated assets such as planets

- `SCENE_ASSET_CACHE_TTL_HOURS`
  - cache cleanup TTL

- `OBJAVERSE_CANDIDATE_LIMIT`
  - maximum Objaverse candidates to inspect per category

- `OBJAVERSE_MIN_SCORE`
  - quality threshold for accepting Objaverse matches

- `SCENE_ASSET_SOURCE_ORDER`
  - comma-separated source order, for example `local,free,cache,objaverse,procedural`

- `SCENE_DISABLE_CACHE`
  - set to `1` to skip cached normalized assets

- `SCENE_DISABLE_OBJAVERSE`
  - set to `1` to skip Objaverse

- `SCENE_DISABLE_FREE`
  - set to `1` to skip curated free downloads

- `SCENE_DISABLE_PROCEDURAL`
  - set to `1` to skip procedural fallback assets

- `OMNI_KIT_ACCEPT_EULA`
  - set automatically in `run_omniverse_scene.py`

## Dependencies

The code expects these major Python/runtime dependencies:

- Pixar USD Python bindings: `pxr`
- Omniverse Kit runtime for the Kit path
- Ollama running locally for AI mode
- `trimesh`
- `Pillow`
- `matplotlib`
- `numpy`
- optionally `objaverse`
- `streamlit`

For the pure Python/UI side, `requirements.txt` now covers the common packages used directly by this repo.

## Outputs

- `generated_scene.usda`
  - main authored scene

- `generated_scene_flat_<timestamp>.usda`
  - flattened copy exported by `main.py` when possible

- `<scene>.preview.png`
  - preview image when `PREVIEW_SAVE_ONLY=1`

- `external_asset_cache/`
  - downloaded and normalized external assets plus cache metadata

- `objaverse_cache/`
  - local Objaverse-related downloads if that path is used in your setup

## Notes On Asset Resolution

For each object, SceneForge tries to find the best asset using per-object source order. Classroom staples such as desks, tables, chairs, and lamps now prefer the local USDA library first so vague Objaverse names do not become office benches or street lamps.

You can override source order with CLI/UI flags:

1. `cache`
2. `objaverse`
3. `free`
4. `local`
5. `procedural`

If no asset is available, the scene builder creates placeholder geometry so export can still succeed.

## Blueprint Notes

Blueprint parsing is intentionally simple. It assumes:

- a mostly white background
- colored regions large enough to survive filtering
- colors close to the expected palette

The default color mapping in `blueprint_parser.py` is:

- brown-like colors for desks/tables
- blue for chairs
- green for blackboards
- brown variations for shelves
- yellow for lamps

If you want better blueprint coverage, expand `DEFAULT_COLOR_MAP` and reduce the current shape assumptions.

## Current Limitations

- `main.py` always runs `direct_usd_scene.py`; the Omniverse path is available but not the default
- `layout_engine.py` is classroom-biased even though other scene families exist
- relation extraction is intentionally shallow and only supports a few patterns
- blueprint parsing is color-and-region based, not learned or geometry-aware
- Objaverse retrieval only works when the package and local setup are available
- some external asset downloads require internet access
- flattened USDA export can still be sensitive to Windows path quirks
- the Streamlit UI and `pipeline_service` resolve the pipeline interpreter from `SCENEFORGE_PYTHON`, the preferred Omniverse USD Python path in code, or the current Python executable
- the Blender button defaults to `C:\Program Files\Blender Foundation\Blender 4.0\blender.exe` unless `SCENEFORGE_BLENDER_PATH` is set
- there is no dedicated fountain mesh in the canonical library; courtyard-style prompts map **fountain** synonyms to **barrel** for a simple central prop
- basic automated tests live under `tests/` (for example `tests/test_scene_explainer.py`); they do not cover the full pipeline end-to-end

## Good Starting Prompts

- `a medieval classroom with wooden desks and a blackboard`
- `outdoor courtyard with stone benches, a central fountain, and shaded trees along the eastern edge` (rule mode: **courtyard** template; use AI + Ollama for freer object choices)
- `a royal throne room with banners and torches`
- `a forest camp with trees, crates and a campfire`
- `a medieval market with vendor stalls and barrels`
- `a cozy tavern with tables, chairs and torches`
- `a solar system with the sun and planets`

## Suggested Next Improvements

1. Add a `pyproject.toml` and pin versions more explicitly
2. Split layout engines by scene family instead of routing everything through classroom logic
3. Expand automated tests (blueprint parsing, asset resolution, FastAPI contract tests)
4. Make `main.py` expose backend selection between direct USD and Omniverse Kit
5. Expand relation extraction beyond `on`, `beside`, and `near`
6. Add richer blueprint palettes and legend-based detection
7. Save outputs per prompt instead of overwriting the same filenames
8. Let the Streamlit UI choose the Python interpreter and Blender executable path from the interface

## Repo Reality Check

This project already has a surprisingly rich prototype stack:

- local LLM scene planning
- deterministic safety fallback and additional **rule templates** (including **courtyard**)
- asset retrieval and normalization
- blueprint-conditioned generation (**including rule mode**, except deterministic solar-system scenes)
- iterative scene refinement (skipped in pure rule/deterministic runs)
- procedural planet generation
- local USD preview
- **FastAPI + React** studio with marketing/FAQ/requirements content, Plotly exploration, and clearer Ollama connectivity errors
- **USD prim listing** that can delegate to the pipeline Python when the API host lacks `pxr`

What it does not yet have is packaging polish, broad automated verification, or a fully generalized layout system. The README reflects the code as it exists today rather than an idealized version.
