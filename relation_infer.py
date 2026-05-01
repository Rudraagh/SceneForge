"""Backward-compatible inferred relation facade."""

from __future__ import annotations

from sceneforge.relations import infer_relations as infer_structured_relations, legacy_relation_tuples


def infer_relations(prompt: str):
    """Return legacy inferred relation tuples."""

    return legacy_relation_tuples(infer_structured_relations(prompt))
