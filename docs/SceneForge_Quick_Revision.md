# SceneForge Quick Revision

## Learn These First

- SceneForge is a **hybrid text-to-3D scene composition system**
- Input: prompt + optional blueprint
- Output: USDA/USD scene
- Core idea: **scene graph first, 3D scene later**
- Modes: `ai` and `rule`
- Key strengths: explainable, controllable, robust
- Key novelty: combines text understanding, scene graph reasoning, blueprint guidance, asset reuse, and fallback logic
- Recent improvement: generic prompts now get prompt-object completion and semantic layout cleanup instead of only family-specific fixes

## Pipeline in One Line

`Prompt -> Scene classification -> Scene object generation -> Relations and layout -> Blueprint mapping -> Asset retrieval -> USD export`

For non-deterministic scenes, add:

`-> domain correction -> evaluation -> reflection -> controller -> refinement`

## Research Gap

There is a lack of a fast, explainable, controllable scene-level text-to-3D system that combines:

- natural language understanding
- explicit object relations
- user-guided layout
- practical asset reuse
- robust fallback behavior

## Why Scene Graph?

- represents objects explicitly
- represents relations explicitly
- helps layout reasoning
- easier to debug and explain

## Why Not Pure AI?

- pure AI can hallucinate
- pure AI may return invalid layouts
- fallback logic improves reliability
- sparse AI output can now be repaired from prompt-derived object expectations

## Why Not Pure Rules?

- pure rules are rigid
- AI mode gives flexibility for broader prompts

## Blueprint Math

- `world_x = (x_n - 0.5) * world_width`
- `world_z = (y_n - 0.5) * world_depth`

## Important Geometry Math

- distance on floor:
- `d = sqrt((x1-x2)^2 + (z1-z2)^2)`

- yaw toward target:
- `yaw = atan2(target_x - source_x, target_z - source_z)`

## Adaptive Score from Report

- `D = alpha*T + beta*M - gamma*C`

where:

- `T` = technical score
- `M` = reasoning score
- `C` = complexity/load penalty

In current code:

- `T` is mainly `placement_score`
- `M` is mainly `reasoning_score`
- `C` is not a separate formal metric; it is best treated as violation/instability penalty

## Improved Scoring

- breakdown is computed by `evaluator_agent_diagnostics(graph)`
- current evaluator combines:
- spacing quality
- bounds compliance
- relation satisfaction
- weighted score:
- `0.45 * spacing_score + 0.20 * bounds_score + 0.35 * relation_score`

## Is There a Multi-Agent Pipeline?

- yes, but it is **lightweight and role-based**
- `agents.py` has:
- `domain_agent` for layout correction
- `evaluator_agent` for scoring
- `reflection_agent` for critique
- `direct_usd_scene.py` runs a refinement loop with these
- `blueprint_agents.py` also contributes evaluation, control, and refinement signals
- it is not a swarm of autonomous LLM agents
- safest phrasing: **lightweight role-based multi-agent refinement architecture**

## Best Multi-Agent Viva Line

"SceneForge uses multi-agent reasoning in a lightweight architectural sense: different specialized modules handle correction, evaluation, reflection, control, and refinement instead of one monolithic step."

## Improved Scoring

- scoring is no longer only pairwise spacing
- current evaluator combines:
- spacing quality
- room-bound compliance
- relation satisfaction
- overlap and tight-clutter penalties

Best phrasing:

"The evaluator uses a weighted composite score that measures geometric spacing, bounds compliance, and relation satisfaction, instead of relying only on raw pairwise distance."

## Key Files

- `main.py`: CLI entry
- `direct_usd_scene.py`: main builder
- `sceneforge/orchestration.py`: generation + fallback + graph logic
- `sceneforge/scene_understanding.py`: scene classification
- `blueprint_parser.py`: parse blueprint image
- `blueprint_mapper.py`: map image coords to world coords
- `sceneforge/layout.py`: relation constraints and overlap prevention
- `layout_engine.py`: family-specific and generic semantic layout cleanup
- `objaverse_loader.py`: asset retrieval
- `api_app.py`: FastAPI backend
- `app.py`: Streamlit UI

## What Makes It Practical

- uses real assets
- uses fallback logic
- supports multiple interfaces
- exports to USD
- works locally with Ollama
- classroom staples now prefer curated local assets over odd cached/generated substitutes
- deterministic classroom blueprints can still run layout/refinement instead of blindly freezing raw blueprint placement
- strict blueprint mode can reinterpret ambiguous blueprint regions from the prompt, such as remapping a library board-like region into a bookshelf
- non-family prompts can still be completed into fuller scenes from prompt nouns even when the AI returns only one object

## Limitations

- limited scene families
- simple blueprint parser
- lightweight spatial reasoning
- depends on asset quality
- benchmarking should be refreshed for current code

## Safe Viva Answer

"SceneForge is a hybrid scene-generation pipeline that converts natural language and optional blueprint input into a structured 3D USD scene using scene graphs, local AI planning, rule-based constraints, asset retrieval, and reliable fallback logic."
