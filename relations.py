"""Backward-compatible relation extraction facade."""

from __future__ import annotations

from sceneforge.relations import legacy_relation_tuples, parse_relations


def extract_relations(prompt: str):
    """Return legacy `(from, relation, to)` tuples from structured parsing."""

    return legacy_relation_tuples(parse_relations(prompt))

