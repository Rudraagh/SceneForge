"""Structured relation parsing, validation, and inference."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence

from sceneforge.logging_utils import get_logger
from sceneforge.models import SUPPORTED_RELATIONS


LOGGER = get_logger(__name__)
ARTICLE_PATTERN = r"(?:a|an|the)"
RELATION_PATTERNS: Dict[str, Sequence[str]] = {
    "aligned_with": ("aligned with",),
    "facing": ("facing", "faces"),
    "inside": ("inside", "in"),
    "under": ("under", "below", "beneath"),
    "beside": ("beside", "next to", "alongside"),
    "near": ("near", "close to"),
    "on": ("on", "atop"),
}
STOP_WORDS = {
    "and",
    "or",
    "with",
    "of",
    "to",
    "in",
    "on",
    "under",
    "inside",
    "beside",
    "near",
    "facing",
    "aligned",
}


@dataclass(frozen=True)
class ParsedRelation:
    """Normalized relation tuple."""

    source: str
    relation: str
    target: str


def _canonicalize(name: str) -> str:
    from ai_scene_graph import canonicalize_object_name

    return canonicalize_object_name(name)


def _normalize_phrase(text: str) -> str:
    lowered = re.sub(r"[^a-z0-9\s_-]+", " ", text.lower())
    return re.sub(r"\s+", " ", lowered).strip()


def _parse_object_phrase(raw: str) -> str:
    tokens = [token for token in _normalize_phrase(raw).split() if token not in STOP_WORDS]
    return _canonicalize(" ".join(tokens))


def _relation_regex(phrase: str) -> re.Pattern[str]:
    object_token = r"(?!(?:a|an|the)\b)(?!(?:and|or|with)\b)[a-z][a-z0-9_-]*"
    object_pattern = rf"({object_token}(?:\s+{object_token}){{0,2}})"
    return re.compile(
        rf"^\s*{ARTICLE_PATTERN}\s+{object_pattern}\s+{re.escape(phrase)}\s+{ARTICLE_PATTERN}\s+{object_pattern}\s*$"
    )


def parse_relations(prompt: str) -> List[ParsedRelation]:
    """Extract structured relations from prompt text."""

    results: set[ParsedRelation] = set()
    raw_text = (prompt or "").lower()
    clauses = [chunk.strip() for chunk in re.split(r",|\band\b", raw_text) if chunk.strip()]
    for clause in clauses:
        normalized_clause = _normalize_phrase(clause)
        for relation_name, phrases in RELATION_PATTERNS.items():
            for phrase in phrases:
                for match in _relation_regex(phrase).finditer(normalized_clause):
                    source = _parse_object_phrase(match.group(1))
                    target = _parse_object_phrase(match.group(2))
                    if source and target and source != target:
                        results.add(ParsedRelation(source=source, relation=relation_name, target=target))
    return sorted(results, key=lambda item: (item.source, item.relation, item.target))


def infer_relations(prompt: str) -> List[ParsedRelation]:
    """Infer deterministic relations for prompts with implied structure."""

    normalized = _normalize_phrase(prompt)
    if "solar system" in normalized:
        planets = ["mercury", "venus", "earth", "mars", "jupiter", "saturn", "uranus", "neptune"]
        return [
            ParsedRelation(source=_canonicalize(planet), relation="orbits", target=_canonicalize("sun"))
            for planet in planets
        ]
    return []


def validate_relations(relations: Iterable[ParsedRelation], object_names: Iterable[str]) -> List[ParsedRelation]:
    """Keep only valid relations that refer to known objects and supported verbs."""

    names = {str(name) for name in object_names}
    valid: List[ParsedRelation] = []
    for relation in relations:
        if relation.relation not in SUPPORTED_RELATIONS:
            LOGGER.warning("Skipping unsupported relation '%s'", relation.relation)
            continue
        if relation.source not in names or relation.target not in names:
            LOGGER.warning(
                "Skipping relation with unknown objects: %s %s %s",
                relation.source,
                relation.relation,
                relation.target,
            )
            continue
        valid.append(relation)
    return valid


def legacy_relation_tuples(relations: Iterable[ParsedRelation]) -> List[tuple[str, str, str]]:
    """Convert structured relations back to the legacy tuple format."""

    return [(item.source, item.relation, item.target) for item in relations]
