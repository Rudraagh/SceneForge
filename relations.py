import re
from ai_scene_graph import canonicalize_object_name

RELATIONS = ("on", "beside", "near")
ARTICLE_PATTERN = r"(?:a|an|the)"
STOP_WORDS = "|".join((*RELATIONS, "and", "or"))
OBJECT_PATTERN = (
    rf"((?!(?:{STOP_WORDS})\b)[a-z][a-z0-9_-]*(?:\s+(?!(?:{STOP_WORDS})\b)[a-z][a-z0-9_-]*)?)"
)


def extract_relations(prompt: str):
    text = prompt.lower()
    results = []

    for relation in RELATIONS:
        pattern = re.compile(
            rf"\b{ARTICLE_PATTERN}\s+{OBJECT_PATTERN}\s+{relation}\s+{ARTICLE_PATTERN}\s+{OBJECT_PATTERN}\b"
        )
        for match in pattern.finditer(text):
            obj1 = canonicalize_object_name(match.group(1).strip())
            obj2 = canonicalize_object_name(match.group(2).strip())
            results.append((obj1, relation, obj2))

    return list(set(results))