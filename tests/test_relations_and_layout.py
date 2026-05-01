"""Tests for structured relation parsing and constraint-based layout helpers."""

from __future__ import annotations

import unittest

from sceneforge.asset_registry import canonicalize_asset_name
from sceneforge.layout import apply_relation_constraints, prevent_overlaps
from sceneforge.relations import ParsedRelation, parse_relations, validate_relations


class TestStructuredRelations(unittest.TestCase):
    def test_parses_extended_relation_types(self):
        prompt = (
            "a chair beside a table, a lamp on a table, "
            "a crate under a table, and a bench aligned with a blackboard"
        )
        relations = parse_relations(prompt)
        tuples = {(item.source, item.relation, item.target) for item in relations}
        self.assertIn(("chair", "beside", "table"), tuples)
        self.assertIn(("lamp", "on", "table"), tuples)
        self.assertIn(("crate", "under", "table"), tuples)
        self.assertIn(("bench", "aligned_with", "blackboard"), tuples)

    def test_validates_only_known_objects(self):
        relations = [
            ParsedRelation("chair", "near", "table"),
            ParsedRelation("lamp", "inside", "cabinet"),
        ]
        valid = validate_relations(relations, {"chair", "table", "lamp"})
        self.assertEqual([(item.source, item.relation, item.target) for item in valid], [("chair", "near", "table")])


class TestConstraintLayout(unittest.TestCase):
    def test_applies_relation_constraints_and_spacing(self):
        graph = {
            "nodes": [
                {"name": "chair", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "table", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ]
        }
        apply_relation_constraints(graph, [ParsedRelation("chair", "beside", "table")])
        prevent_overlaps(graph, min_spacing=1.0)
        chair = next(node for node in graph["nodes"] if node["name"] == "chair")
        table = next(node for node in graph["nodes"] if node["name"] == "table")
        self.assertGreater(abs(chair["position"][0] - table["position"][0]), 0.5)


class TestAssetRegistry(unittest.TestCase):
    def test_does_not_map_fountain_to_barrel(self):
        self.assertEqual(canonicalize_asset_name("fountain"), "fountain")


if __name__ == "__main__":
    unittest.main()
