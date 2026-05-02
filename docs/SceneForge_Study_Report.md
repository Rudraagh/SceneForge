# SceneForge Study Report

## 1. Title

**SceneForge: Natural Language and Blueprint Driven 3D Scene Generation Using Local LLMs, Graph Reasoning, Asset Retrieval, and USD Authoring**

## 2. Purpose of the Project

SceneForge is a text-to-3D scene generation system that converts a user prompt, and optionally a simple blueprint image, into a structured 3D USD scene. The project is designed as a practical alternative to heavy end-to-end generative 3D systems. Instead of trying to synthesize geometry from scratch for every prompt, SceneForge breaks the problem into smaller stages:

- understand the scene intent from text
- generate or select scene objects
- build a structured scene graph
- enforce spatial relations and spacing constraints
- retrieve suitable 3D assets
- place them into a valid 3D scene
- export the final result as a USDA/USD scene

The core idea is that structured reasoning plus modular asset reuse can produce useful 3D scenes much faster and more reliably than pure generative 3D pipelines.

## 3. Problem Statement

Many text-to-3D pipelines focus on producing a single object or rely on very expensive diffusion or neural rendering methods. Even when they produce visually impressive output, they often have these weaknesses:

- they are computationally expensive
- they do not naturally produce full scenes with strong object-to-object logic
- they do not explicitly model relations such as `near`, `beside`, `on`, or `facing`
- they can hallucinate objects or produce invalid layouts
- they are difficult to control and validate

SceneForge addresses this by using a hybrid pipeline that combines:

- deterministic scene templates
- local LLM-assisted scene graph generation
- graph-based spatial reasoning
- blueprint-guided placement
- rule-based refinement
- asset retrieval with fallbacks
- standard USD export

## 3.1 Research Gap Filled by This Project

The main research gap filled by SceneForge is the gap between:

- highly flexible but unreliable generative prompt-based systems, and
- reliable but rigid rule/template-based 3D scene construction systems

Existing text-to-3D and scene-generation approaches usually have one of the following limitations:

- they generate single objects rather than full multi-object scenes
- they produce scenes without explicitly modeling object relationships
- they require heavy computation and long generation time
- they do not provide an interpretable intermediate representation
- they do not give users a simple way to guide layout spatially
- they lack robust fallback behavior when AI output is poor

In other words, current systems often miss a practical middle layer between text understanding and final 3D scene authoring.

SceneForge fills this gap by introducing a hybrid pipeline with:

- a structured scene graph as an intermediate representation
- graph-based spatial relation enforcement
- lightweight blueprint-guided layout control
- local LLM planning with deterministic fallback
- reusable asset retrieval instead of full geometry synthesis
- export into a professional scene format, USD

So the specific research gap can be stated as:

**There is a lack of a fast, explainable, controllable, scene-level text-to-3D system that combines natural language understanding, explicit relational structure, lightweight user-guided layout input, practical asset reuse, and robust fallback logic in a single pipeline.**

Another good viva phrasing is:

**Most prior work optimizes either realism or generation novelty, but not structured scene correctness, controllability, and deployment practicality together. SceneForge addresses that missing combination.**

## 4. High-Level Idea

The system follows a "think before build" philosophy.

Instead of directly generating a full 3D world in one step, SceneForge first creates an intermediate structured representation of the scene. That representation is a graph-like list of scene objects with:

- object name
- position `[x, y, z]`
- rotation `[rx, ry, rz]`
- scale `[sx, sy, sz]`

This structured representation is then refined and validated before assets are placed into the final world.

In simple terms:

`Prompt -> Scene Understanding -> Scene Graph -> Constraints/Relations -> Asset Resolution -> USD Scene`

If a blueprint image is provided, the blueprint can either:

- replace the generated layout in strict blueprint mode, or
- merge positional hints into an AI/rule-generated layout

## 5. Main Objectives

The project aims to:

- generate 3D scenes from plain English prompts
- support both AI-driven and deterministic generation
- improve layout correctness using graph and relation reasoning
- allow simple blueprint-conditioned scene placement
- reuse existing 3D assets efficiently
- export scenes in USD format for interoperability
- provide usable interfaces through CLI, Streamlit, and FastAPI + React

## 6. What the Current System Actually Implements

Based on the current codebase, SceneForge supports:

- prompt-to-scene generation in `ai` mode and `rule` mode
- scene classification into families such as classroom, courtyard, tavern, market, forest camp, throne room, studio, basketball court, and solar system
- object canonicalization, such as converting `desk` to `wooden_desk`
- scene graph generation using a local Ollama model
- compact retry prompting when local LLM JSON generation fails
- safe fallback from AI generation to deterministic templates
- prompt-driven completion for sparse AI scenes, including arbitrary non-family prompts
- relation parsing from prompts, including `on`, `near`, `beside`, `inside`, `under`, `facing`, and `aligned_with`
- basic inference for solar-system relations
- overlap prevention and spacing correction
- classroom, throne-room, and solar-system specific layout improvement
- generic semantic layout cleanup for arbitrary prompts
- blueprint parsing based on color regions
- prompt-aware blueprint reinterpretation for ambiguous regions
- blueprint-to-world coordinate mapping
- asset lookup from local sources, free sources, cache, Objaverse, and procedural generation
- planet generation for solar-system scenes
- USD authoring using Pixar USD APIs
- a local preview workflow
- a FastAPI backend and React frontend for generation, explanation, and object inspection

## 7. System Architecture

The architecture is modular. The major components are:

### 7.1 Input Layer

Inputs can include:

- a natural language prompt
- an optional blueprint image
- user options such as AI/rule mode and asset source configuration

### 7.2 Scene Understanding Layer

This stage identifies the likely scene family from the prompt. It uses:

- keyword-based classification first
- optional LLM-based classification when needed

Example:

- "a medieval classroom with desks and a board" -> `classroom`
- "a solar system with the sun and planets" -> `solar_system`

### 7.3 Scene Graph Generation Layer

Two paths are available:

- `ai` mode: use Ollama to produce scene objects in JSON form
- `rule` mode: use deterministic scene templates

If the AI output is invalid or empty, the system falls back to:

1. deterministic scene generation
2. minimal safe fallback scene

### 7.4 Relation and Constraint Layer

After scene objects are created, the system:

- extracts relations from the prompt
- validates them against known objects
- applies position and orientation constraints
- pushes objects apart to prevent overlaps
- runs a role-based refinement cycle for correction, scoring, reflection, and controlled refinement

### 7.5 Blueprint Layer

If blueprint mode is enabled, the system:

- reads the blueprint image
- detects colored object regions
- maps image coordinates into world coordinates
- can reinterpret some ambiguous blueprint objects from prompt semantics
- either replaces or merges the generated layout

### 7.6 Asset Resolution Layer

For each object name, the system tries to find a matching 3D asset using an ordered fallback strategy. This may involve:

- local curated assets
- cached normalized assets
- curated free assets
- Objaverse retrieval
- procedural generation
- placeholder geometry if nothing is found

### 7.7 USD Authoring Layer

After positions, rotations, scales, and assets are finalized, the system:

- creates a `/World` root
- adds room geometry for non-deterministic indoor scenes
- references external assets
- applies transforms
- exports the result as a USDA file

## 8. End-to-End Pipeline

The working pipeline in the repo can be described as follows:

1. User enters a prompt in CLI, Streamlit, or React UI.
2. The system selects generation mode: `ai` or `rule`.
3. The scene is classified into a known scene family.
4. A scene object list is generated.
5. If blueprint mode is active, blueprint positions are parsed and applied.
6. A graph is built from scene objects and relations.
7. Spatial constraints are applied.
8. Optional family-specific or generic semantic layout arrangement runs when relevant.
9. A role-based multi-agent refinement loop runs for non-deterministic scenes:
10. domain correction
11. numeric scoring
12. qualitative reflection
13. controller-based stop/continue decision
14. additional controlled refinement
15. Assets are resolved per object.
16. A USD stage is authored.
17. The stage is exported to `generated_scene.usda`.
18. A flattened export and preview can optionally be produced.

## 9. Key Modules and Their Roles

### 9.1 `main.py`

The main CLI entry point. It:

- checks whether Ollama is reachable
- checks whether the required model is installed
- launches the scene builder
- optionally exports a flattened scene
- optionally launches a previewer

### 9.2 `direct_usd_scene.py`

This is the core builder. It:

- creates the USD stage
- chooses AI or deterministic generation
- handles blueprint logic
- builds the graph
- runs layout/refinement logic
- resolves assets
- places prims in `/World`
- exports the final stage

### 9.3 `sceneforge/orchestration.py`

This is the central orchestration layer for:

- canonicalization
- few-shot prompt building
- scene graph generation
- compact retry prompt construction for stricter JSON output
- safe fallback logic
- prompt-based scene completion for sparse AI outputs
- graph construction
- relation enrichment
- overlap prevention

### 9.4 `sceneforge/scene_understanding.py`

This module performs scene classification using:

- keyword rules
- optional LLM-based classification

### 9.5 `blueprint_parser.py`

This module interprets a blueprint image by:

- reading RGB pixels
- finding connected non-background regions
- averaging region colors
- assigning each region to the nearest known object color
- converting region centroids into normalized coordinates

### 9.6 `blueprint_mapper.py`

This module converts blueprint coordinates into world coordinates.

### 9.7 `sceneforge/layout.py`

This module applies:

- relation constraints
- spacing constraints
- overlap prevention

### 9.8 `agents.py`

This module powers the main role-based refinement loop:

- `domain_agent()` for relation-aware correction
- `evaluator_agent()` for numeric layout scoring
- `evaluator_agent_diagnostics()` for score breakdown and diagnostics
- `reflection_agent()` for qualitative self-critique

### 9.9 `objaverse_loader.py` and `sceneforge/asset_registry.py`

These modules handle:

- asset retrieval
- asset matching
- normalization
- fallback behavior

### 9.10 `pipeline_service.py` and `api_app.py`

These power the FastAPI service and web UI integration.

## 10. Mathematical and Algorithmic Foundations

This project is not a purely neural model. Its strength comes from combining lightweight mathematical rules with symbolic structure.

### 10.1 Coordinate Representation

Every object is represented using:

- position: `[x, y, z]`
- rotation: `[rx, ry, rz]`
- scale: `[sx, sy, sz]`

The world uses a 3D Cartesian-style coordinate system, with USD configured to use:

- Y as the up-axis

### 10.2 Blueprint Coordinate Mapping

Blueprint objects are first found in normalized image coordinates:

- `x_n in [0, 1]`
- `y_n in [0, 1]`

They are then mapped into world coordinates using:

- `world_x = (x_n - 0.5) * world_width`
- `world_z = (y_n - 0.5) * world_depth`

This means:

- the center of the image maps to the center of the room
- left/right in the image map to negative/positive X
- top/bottom in the image map to negative/positive Z

### 10.3 Color Distance for Blueprint Object Detection

Blueprint parsing uses average region color and nearest-palette matching. The Euclidean color distance is:

`d(c1, c2) = sqrt((r1-r2)^2 + (g1-g2)^2 + (b1-b2)^2)`

The object class whose reference color is closest to the region color is selected.

### 10.4 Region Detection

The blueprint parser uses flood fill over neighboring pixels. A region is collected by exploring 4-connected neighbors:

- `(x+1, y)`
- `(x-1, y)`
- `(x, y+1)`
- `(x, y-1)`

Only pixels similar enough to the seed color are included.

### 10.5 Object Centroid

The center of a detected region is:

- `centroid_x = (sum of x coordinates) / N`
- `centroid_y = (sum of y coordinates) / N`

where `N` is the number of pixels in the region.

### 10.6 Layout Quality Scoring

The current evaluator is stronger than a simple spacing-only score. It now uses a weighted composite layout score with three main components:

- spacing quality
- bounds compliance
- relation satisfaction

Conceptually:

`final_score = 0.45 * spacing_score + 0.20 * bounds_score + 0.35 * relation_score`

In code:

- the score breakdown is computed by `evaluator_agent_diagnostics(graph)`
- `spacing_score` rewards healthy pairwise spacing and penalizes overlap and crowding
- `bounds_score` penalizes objects placed outside expected room limits
- `relation_score` measures how well scene relations such as `near`, `beside`, `on`, `facing`, and `aligned_with` are satisfied

So the scoring is now more meaningful because it captures both geometry and semantics, while still staying lightweight and fast.

### 10.7 Overlap Prevention

For object pairs, horizontal distance in the XZ plane is computed as:

`distance = sqrt((x1-x2)^2 + (z1-z2)^2)`

If the distance is smaller than the target spacing, the objects are pushed apart along the normalized direction vector between them.

This is a simple geometric relaxation approach.

### 10.8 Relation Enforcement

The system applies deterministic relation rules:

- `on`: align X and Z, raise Y
- `under`: align X and Z, lower Y
- `inside`: align positions
- `near`: keep within a spacing band
- `beside`: shift laterally by required spacing
- `facing`: rotate the source toward the target
- `aligned_with`: align orientation and depth axis

### 10.9 Yaw Orientation Toward a Target

For relations like `facing`, the yaw angle is computed using:

`yaw = atan2(target_x - source_x, target_z - source_z)`

and converted to degrees.

This allows desks to face boards and chairs to face desks.

### 10.10 Bounding Box Based Asset Scaling

When an asset is referenced, the system estimates its world-space bounding box and computes a scale factor so the object better fits an expected target size.

For each dimension:

`ratio_i = target_size_i / current_size_i`

The chosen fit scale is:

`fit_scale = min(ratio_x, ratio_y, ratio_z)`

This helps keep mismatched external assets from appearing absurdly large or tiny.

### 10.11 Adaptive Score Formula from the Submitted Paper

Your submitted paper describes an adaptive difficulty/control score:

`D = alpha*T + beta*M - gamma*C`

where:

- `T` = technical score
- `M` = metacognitive or reasoning score
- `C` = cognitive load

The current codebase includes a directly related function in `blueprint_agents.py`:

`compute_score(T, M, C, alpha=0.5, beta=0.3, gamma=0.2)`

So this part is not just theoretical. It exists in the implementation, especially in the blueprint-refinement logic.

### 10.12 Blueprint Refinement Logic

The blueprint agent pipeline computes:

- placement quality
- reasoning quality
- overlap penalties
- whether to continue refining

It also contains an adaptive controller that changes:

- stopping threshold
- continuation decision
- refinement weight

This is a lightweight feedback loop rather than a learned RL controller.

### 10.13 Improved Multi-Agent Refinement in the Current Pipeline

The current non-deterministic pipeline now has a clearer refinement cycle than a simple one-pass scoring loop.

The implemented role sequence is:

1. optional classroom arrangement
2. `domain_agent()` for relation-aware correction
3. `evaluator_agent()` for composite layout scoring
4. `reflection_agent()` for qualitative feedback
5. blueprint-style placement and reasoning diagnostics
6. `adaptive_controller()` for stop/continue control
7. `refine_scene()` for an additional controlled refinement pass

So the pipeline now more explicitly supports:

- proposal
- evaluation
- reflection
- control
- refinement

The `evaluator_agent()` is no longer only a spacing checker. It now examines:

- overlap severity
- crowding
- whether objects stay inside room bounds
- whether relations are actually satisfied

This makes the refinement loop more meaningful because the score reflects scene quality more realistically.

## 11. Scene Graph Representation

The graph has two important parts:

- nodes: scene objects
- edges: object relations

A typical node contains:

- `name`
- `position`
- `rotation`
- `scale`

A typical edge contains:

- `from`
- `relation`
- `to`

Example:

- `chair near wooden_desk`
- `wooden_desk facing blackboard`

This graph representation is central because it creates a structured intermediate format between natural language and 3D geometry.

## 12. AI Path vs Rule Path

### 12.1 AI Path

In AI mode:

- the prompt is converted into a few-shot LLM prompt
- a local Ollama model is queried
- the response is extracted as JSON
- invalid JSON is repaired when possible
- the result is validated against a strict schema
- the final scene is constrained and cleaned

Advantages:

- more flexible
- can respond to richer prompts
- better for creative prompts not covered by templates

Limitations:

- depends on local model quality
- can still fail and require fallback

### 12.2 Rule Path

In rule mode:

- the prompt is classified into a scene family
- a predefined object template is selected
- spatial positions are filled deterministically

Advantages:

- fast
- predictable
- robust

Limitations:

- less expressive
- dependent on manually defined scene families

## 13. Blueprint-Guided Scene Generation

One of the most distinctive parts of SceneForge is that it can use a simple blueprint image as a layout guide.

The blueprint pipeline works as follows:

1. Read the blueprint image.
2. Treat white or near-white regions as background.
3. Find connected colored regions.
4. Average the color of each region.
5. Match the color to an object class.
6. Compute the region centroid.
7. Convert the centroid into normalized coordinates.
8. Convert normalized coordinates into world coordinates.
9. Place the corresponding scene objects into the world.

This is useful because it gives the user lightweight control over placement without requiring a full CAD system or complex GUI.

## 14. Asset Retrieval Strategy

SceneForge is not generating all geometry from scratch. It intelligently reuses existing assets.

Typical source order may include:

- local assets
- free-source downloads
- cached normalized assets
- Objaverse candidates
- procedural generation

If no asset is found:

- placeholder geometry is created so the pipeline still completes

This is a practical engineering choice. It improves speed and reliability while keeping the pipeline explainable.

## 15. Output Format and Why USD Matters

The output is a USD/USDA scene.

USD is valuable because it is:

- modular
- interoperable
- widely used in graphics pipelines
- suitable for referencing assets rather than duplicating geometry

This means SceneForge is not just a demo. It produces output in a format that can integrate with professional 3D pipelines.

## 16. Interfaces Provided

The project currently exposes multiple interfaces:

### 16.1 CLI

Good for direct execution and testing.

### 16.2 Streamlit App

Useful for demonstrations and quick user interaction.

### 16.3 FastAPI + React Studio

This is the richer modern interface. It includes:

- scene generation controls
- blueprint upload
- metrics and logs
- scene object listing
- per-object explanation using Ollama
- Plotly-based scene inspection

## 17. Novelty of the Project

The novelty of SceneForge is not that it invents text-to-3D from scratch. Its novelty comes from how it combines multiple practical ideas into one coherent system.

### 17.1 Hybrid Text-to-3D Architecture

Most pipelines choose one approach:

- pure generative model
- pure template system
- pure rule engine

SceneForge combines:

- local LLM generation
- deterministic fallback
- graph reasoning
- blueprint conditioning
- asset retrieval
- standard USD export

That combination is a key contribution.

### 17.2 Structured Intermediate Reasoning

Instead of going directly from prompt to mesh, the system creates a structured scene representation first. This improves:

- explainability
- controllability
- debugging
- fallback behavior

### 17.3 Blueprint as a Lightweight Spatial Interface

The blueprint feature is particularly novel for a student project because it gives users a low-cost visual way to control the scene without building a full 3D editor.

### 17.4 Practical Multi-Strategy Robustness

The system is robust because it has multiple fallback layers:

- AI generation
- deterministic rule generation
- minimal fallback scene
- local asset fallback
- placeholder geometry fallback

This makes it more deployable than a single fragile generation model.

### 17.5 Local-First Design

The project is designed around local execution:

- local Ollama
- local USD authoring
- local viewer
- optional local asset caches

This is useful for privacy, reproducibility, and lab demos.

## 18. Strengths of the Project

- modular pipeline
- easy to explain in a viva
- structured graph reasoning
- controllable output
- practical fallback design
- blueprint-guided placement
- support for both deterministic and AI modes
- professional output format through USD
- real interfaces, not just research code

## 19. Limitations of the Current Implementation

It is important to explain the limitations honestly during the viva.

### 19.1 Scene Diversity Is Still Bounded

The system supports several scene families, but it is not yet a universal scene generator.

### 19.2 Spatial Reasoning Is Lightweight

The reasoning is mostly rule-based and geometric. It does not simulate:

- physics
- collisions
- dynamics
- material behavior

### 19.3 Blueprint Parsing Is Simple

The blueprint parser is color-based. It assumes:

- a mostly white background
- known region colors
- reasonably large and clean object regions

### 19.4 Some Project Claims in the Older Submitted Paper Are Broader Than the Current Repo

The older paper discusses:

- adaptive education
- interview systems
- broader domain-agnostic cognitive simulation

The current repository is much more concretely focused on 3D scene generation and related interfaces. So in the viva, it is safest to say:

- the broader framework idea inspired the project
- the implemented prototype is primarily a structured text-to-3D scene generation system

### 19.5 Metrics in the Submitted Paper Should Be Treated Carefully

The submitted report mentions values like:

- scene generation success above 92%
- object placement accuracy around 87 to 90%
- relationship consistency around 89 to 92%
- generation time 4 to 6 seconds

These values are useful as reported experimental claims from the submitted study, but they are not automatically guaranteed by the current repo state unless benchmarked again on the current code.

## 20. Comparison with End-to-End Generative 3D Methods

Compared with diffusion-based text-to-3D methods, SceneForge:

- is lighter and faster
- uses existing assets instead of synthesizing geometry every time
- is more explainable
- is easier to validate
- is more suited to full structured scene composition

However, diffusion-based methods can outperform SceneForge in:

- visual novelty
- organic geometry synthesis
- highly detailed single-object generation

So SceneForge is best described as a structured scene composition system rather than a fully generative 3D synthesis model.

## 21. Suggested Viva Explanation

If you need to explain the project in simple words:

"SceneForge is a hybrid text-to-3D scene generation pipeline. It takes a natural language prompt and optionally a color-coded blueprint, converts them into a structured scene graph, applies spatial reasoning and layout constraints, retrieves suitable 3D assets, and exports the final scene as USD. The project is novel because it combines local LLM reasoning, deterministic fallback, graph-based structure, blueprint-guided placement, and practical asset reuse in one pipeline."

## 22. Suggested Questions and Answers for Viva

### Q1. Why use a scene graph?

A scene graph gives a structured intermediate representation between text and 3D geometry. It helps the system represent objects and relations explicitly, making the output more logical and easier to validate.

### Q2. Why not directly generate 3D objects using diffusion models?

Direct 3D generation is expensive and often focuses on single objects. Our system is designed for faster and more controllable full-scene generation using asset reuse and structured reasoning.

### Q3. What is the role of the blueprint?

The blueprint acts as a simple visual layout guide. It lets the user influence object placement using a 2D image without needing a full 3D editor.

### Q4. How does the system maintain logical placement?

It uses relation extraction, geometric spacing rules, overlap prevention, and orientation logic such as making desks face the blackboard or chairs stay near desks.

### Q5. What happens if the AI model fails?

The system falls back to deterministic rule-based scene generation, and if that still fails, it uses a minimal safe scene.

### Q6. Why use USD?

USD is a standard scene representation format used in 3D pipelines. It supports hierarchy, transformations, and asset references, which makes the output portable and professional.

### Q7. What is the novelty of this project?

The novelty lies in integrating structured scene graphs, local LLM planning, blueprint-based conditioning, rule-based validation, asset retrieval, and USD export into one coherent system.

## 23. Future Work

Good future improvements include:

- support more scene families
- learn blueprint parsing from data instead of color heuristics
- add physics-aware reasoning
- improve object relation extraction
- expand automatic testing
- benchmark the current version rigorously
- support interactive editing after generation
- add richer asset ranking with semantic and geometric scoring
- support animated or dynamic scenes

## 24. Conclusion

SceneForge is a strong example of practical hybrid AI engineering. Its value is not in producing the most photorealistic geometry, but in creating logically structured 3D scenes in a controllable, explainable, and efficient way. By using a scene graph as the central representation, combining AI and deterministic logic, and exporting to USD, the project demonstrates a realistic pathway from natural language understanding to usable 3D world generation.

For viva preparation, the most important points to remember are:

- it is a hybrid text-to-3D scene composition system
- the scene graph is the central structured representation
- blueprint guidance is one of the distinctive features
- graph constraints and relation rules enforce logical placement
- assets are retrieved and normalized instead of always being generated from scratch
- the final output is a USD scene ready for downstream 3D tools

## 25. Important Accuracy Note for Your Team

Your earlier submitted report includes some broader claims and experimental numbers. For study and viva use, the safest interpretation is:

- the paper presents the larger research vision
- the current repository is the concrete prototype implementation
- the implemented prototype most strongly demonstrates structured text-to-3D generation with blueprint-conditioned scene layout

That distinction will help you answer questions confidently and avoid overclaiming features that are not fully implemented in this exact repo.
