# SceneForge RAG corpus

## Scene graph JSON

SceneForge expects a JSON array of objects. Each object uses keys: name, position, rotation, scale. Position uses world units with Y near ground level for furniture.

## Courtyard and outdoor prompts

Courtyard-style prompts include benches, trees, fountains, shade, plazas, and patios. The pipeline may map fountain or water_feature synonyms to a stand-in prop when no dedicated fountain mesh exists; prefer canonical names from the asset list when possible.

## Classroom and medieval interiors

Classroom scenes use wooden_desk, chair, blackboard, bookshelf, and lamp. Desks and chairs are usually paired; the blackboard sits at the front of the room.

## Solar system

Solar prompts use sun, mercury, venus, earth, mars, jupiter, saturn, uranus, neptune in order from the star outward. Explanations should stay astronomically reasonable for educational blurbs.

## Blueprint mode

Blueprint images map colored regions to object classes. Brown regions often mean desks, blue can mean chairs, green can mean blackboards. Placement from blueprints can override or merge with AI-generated positions depending on mode.
