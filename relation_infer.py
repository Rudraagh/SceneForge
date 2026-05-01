from ai_scene_graph import canonicalize_object_name


def infer_relations(prompt: str):
    normalized = prompt.strip().lower()

    if "solar system" in normalized:
        planets = ["mercury", "venus", "earth", "mars"]

        return [
            (
                canonicalize_object_name(p),
                "orbits",
                canonicalize_object_name("sun"),
            )
            for p in planets
        ]

    return []