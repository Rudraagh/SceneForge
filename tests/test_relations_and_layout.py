"""Tests for structured relation parsing and constraint-based layout helpers."""

from __future__ import annotations

import unittest

from agents import domain_agent, evaluator_agent, evaluator_agent_diagnostics
from direct_usd_scene import (
    _normalized_scale_override,
    _run_multi_agent_refinement,
    _should_add_room_shell,
    _should_run_layout_and_agents,
)
from sceneforge.asset_registry import canonicalize_asset_name, find_asset
from sceneforge.layout import apply_relation_constraints, prevent_overlaps
from layout_engine import arrange_blueprint_layout, arrange_classroom_layout, arrange_semantic_layout, arrange_throne_room_layout
from layout_engine import arrange_solar_system_layout
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

    def test_evaluator_rewards_relation_satisfaction(self):
        good_graph = {
            "nodes": [
                {"name": "chair", "position": [0.0, 0.0, -1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "table", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "edges": [{"from": "chair", "relation": "near", "to": "table"}],
        }
        bad_graph = {
            "nodes": [
                {"name": "chair", "position": [5.0, 0.0, 5.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "table", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "edges": [{"from": "chair", "relation": "near", "to": "table"}],
        }
        good_diag = evaluator_agent_diagnostics(good_graph)
        bad_diag = evaluator_agent_diagnostics(bad_graph)
        self.assertGreater(good_diag["relation_score"], bad_diag["relation_score"])
        self.assertGreater(evaluator_agent(good_graph), evaluator_agent(bad_graph))

    def test_domain_agent_keeps_classroom_chair_behind_desk(self):
        graph = {
            "nodes": [
                {"name": "chair", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 180.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "wooden_desk", "position": [0.0, 0.0, -2.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "edges": [{"from": "chair", "relation": "near", "to": "wooden_desk"}],
            "lookup": {},
        }
        updated = domain_agent(graph)
        chair = updated["nodes"][0]
        desk = updated["nodes"][1]
        self.assertLess(chair["position"][2], desk["position"][2])
        self.assertEqual(float(chair["rotation"][1]), 0.0)


class TestAssetRegistry(unittest.TestCase):
    def test_does_not_map_fountain_to_barrel(self):
        self.assertEqual(canonicalize_asset_name("fountain"), "fountain")

    def test_classroom_assets_prefer_local_library(self):
        asset = find_asset("chair")
        self.assertIsNotNone(asset)
        self.assertIn("local:chair", str(asset.get("source", "")))

    def test_numbered_classroom_objects_use_base_scale_rules(self):
        self.assertEqual(
            _normalized_scale_override("wooden_desk_12", {"asset_path": "dummy.usda"}, [1.0, 1.0, 1.0]),
            [1.0, 1.0, 1.0],
        )
        self.assertEqual(
            _normalized_scale_override("chair_9", {"asset_path": "dummy.usda"}, [1.0, 1.0, 1.0]),
            [0.4, 0.4, 0.4],
        )


class TestPipelineGating(unittest.TestCase):
    def test_classroom_blueprint_in_rule_mode_still_runs_refinement(self):
        should_run = _should_run_layout_and_agents(
            selected_mode="deterministic",
            scene_type="classroom",
            blueprint_mode=True,
            blueprint_data=[{"name": "chair"}],
        )
        self.assertTrue(should_run)

    def test_non_classroom_blueprint_in_rule_mode_still_runs_blueprint_path(self):
        should_run = _should_run_layout_and_agents(
            selected_mode="deterministic",
            scene_type="studio",
            blueprint_mode=True,
            blueprint_data=[{"name": "table"}],
        )
        self.assertTrue(should_run)

    def test_deterministic_classroom_with_layout_gets_room_shell(self):
        should_add = _should_add_room_shell(
            scene_type="classroom",
            selected_mode="deterministic",
            graph={"layout": {"type": "classroom", "room": {"width": 8.0, "depth": 8.0, "height": 3.0}, "bounds": {"center_x": 0.0, "center_z": 0.0}}},
        )
        self.assertTrue(should_add)

    def test_classroom_scene_type_forces_classroom_layout(self):
        graph = {
            "nodes": [
                {"name": "wooden_desk_1", "position": [-2.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "wooden_desk_2", "position": [2.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "edges": [],
        }
        updated, _score, _iterations = _run_multi_agent_refinement(graph, prompt="minimal prompt", scene_type="classroom")
        self.assertEqual(updated.get("layout", {}).get("type"), "classroom")
        self.assertIn("center_z", updated.get("layout", {}).get("bounds", {}))


class TestClassroomLayoutOrientation(unittest.TestCase):
    def test_board_desks_and_chairs_follow_blueprint_reading_order(self):
        graph = {
            "nodes": [
                {"name": "blackboard_1", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "wooden_desk_1", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "chair_1", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ]
        }

        arranged = arrange_classroom_layout(graph, rows=1, cols=1)
        lookup = {node["name"]: node for node in arranged["nodes"]}
        board_z = lookup["blackboard_1"]["position"][2]
        desk_z = lookup["wooden_desk_1"]["position"][2]
        chair_z = lookup["chair_1"]["position"][2]

        self.assertGreater(board_z, desk_z)
        self.assertGreater(desk_z, chair_z)


class TestBlueprintAnchoring(unittest.TestCase):
    def test_generic_blueprint_layout_preserves_explicit_positions(self):
        graph = {
            "nodes": [
                {
                    "name": "table_1",
                    "position": [9.0, 0.0, 9.0],
                    "blueprint_position": [1.5, 0.0, -2.5],
                    "rotation": [0.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0],
                },
                {
                    "name": "lamp_1",
                    "position": [-9.0, 0.0, -9.0],
                    "blueprint_position": [-3.0, 0.0, 4.0],
                    "rotation": [0.0, 0.0, 0.0],
                    "scale": [1.0, 1.0, 1.0],
                },
            ]
        }

        arranged = arrange_blueprint_layout(graph)
        lookup = {node["name"]: node for node in arranged["nodes"]}
        self.assertEqual(lookup["table_1"]["position"], [1.5, 0.0, -2.5])
        self.assertEqual(lookup["lamp_1"]["position"], [-3.0, 0.0, 4.0])


class TestThroneRoomLayout(unittest.TestCase):
    def test_throne_room_layout_centers_throne_and_symmetrizes_support_objects(self):
        graph = {
            "nodes": [
                {"name": "throne_1", "position": [4.5, 0.0, -3.5], "rotation": [0.0, 45.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "banner_1", "position": [3.5, 0.0, -5.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "banner_2", "position": [4.6, 0.0, -5.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "torch_1", "position": [2.8, 0.0, -2.4], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "torch_2", "position": [5.7, 0.0, -2.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "bench_1", "position": [3.4, 0.0, 0.9], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "bench_2", "position": [-2.9, 0.0, 0.8], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ]
        }

        arranged = arrange_throne_room_layout(graph)
        lookup = {node["name"]: node for node in arranged["nodes"]}
        banner_xs = sorted(
            lookup[name]["position"][0]
            for name in lookup
            if "banner" in name
        )
        torch_xs = sorted(
            lookup[name]["position"][0]
            for name in lookup
            if "torch" in name
        )

        self.assertAlmostEqual(lookup["throne_1"]["position"][0], 0.0)
        self.assertAlmostEqual(lookup["throne_1"]["position"][2], -4.4)
        self.assertLess(banner_xs[0], 0.0)
        self.assertGreater(banner_xs[-1], 0.0)
        self.assertLess(torch_xs[0], 0.0)
        self.assertGreater(torch_xs[-1], 0.0)
        self.assertEqual(float(lookup["bench_1"]["rotation"][1]), 90.0)
        self.assertEqual(float(lookup["bench_2"]["rotation"][1]), 90.0)


class TestSemanticLayout(unittest.TestCase):
    def test_generic_semantic_layout_centers_main_surface_and_frontloads_seating(self):
        graph = {
            "nodes": [
                {"name": "table_1", "position": [4.0, 0.0, 3.0], "rotation": [0.0, 35.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "chair_1", "position": [-2.0, 0.0, -4.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "chair_2", "position": [5.0, 0.0, -4.5], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "bookshelf_1", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "crate_1", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ]
        }

        arranged = arrange_semantic_layout(graph, prompt="a studio with a table, chairs, bookshelf, and crate", scene_type="studio")
        lookup = {node["name"]: node for node in arranged["nodes"]}

        self.assertAlmostEqual(lookup["table_1"]["position"][0], 0.0)
        self.assertGreater(lookup["chair_1"]["position"][2], 0.0)
        self.assertGreater(lookup["chair_2"]["position"][2], 0.0)
        self.assertLess(lookup["bookshelf_1"]["position"][2], 0.0)


class TestSolarSystemLayout(unittest.TestCase):
    def test_solar_layout_centers_sun_and_orders_planets_by_orbit(self):
        graph = {
            "nodes": [
                {"name": "sun", "position": [9.0, 0.0, 9.0], "rotation": [0.0, 17.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "earth", "position": [-5.0, 0.0, 2.0], "rotation": [0.0, 8.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "mars", "position": [6.0, 0.0, -8.0], "rotation": [0.0, 12.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "jupiter", "position": [1.0, 0.0, 13.0], "rotation": [0.0, 40.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "saturn", "position": [-12.0, 0.0, -3.0], "rotation": [0.0, 67.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ]
        }

        arranged = arrange_solar_system_layout(graph)
        lookup = {node["name"]: node for node in arranged["nodes"]}

        self.assertAlmostEqual(lookup["sun"]["position"][0], 0.0, places=3)
        self.assertAlmostEqual(lookup["sun"]["position"][2], 0.0, places=3)

        def orbit_radius(name: str) -> float:
            x, _y, z = lookup[name]["position"]
            return (float(x) ** 2 + float(z) ** 2) ** 0.5

        self.assertLess(orbit_radius("earth"), orbit_radius("mars"))
        self.assertLess(orbit_radius("mars"), orbit_radius("jupiter"))
        self.assertLess(orbit_radius("jupiter"), orbit_radius("saturn"))
        self.assertEqual(arranged.get("layout", {}).get("type"), "solar_system")
        self.assertIn("center_z", arranged.get("layout", {}).get("bounds", {}))

    def test_refinement_prefers_solar_layout_for_solar_prompts(self):
        graph = {
            "nodes": [
                {"name": "sun", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "earth", "position": [0.2, 0.0, 0.2], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "mars", "position": [0.3, 0.0, 0.1], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "jupiter", "position": [0.4, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "edges": [],
        }

        updated, _score, _iterations = _run_multi_agent_refinement(
            graph,
            prompt="a solar system with planets orbiting the sun",
            scene_type="solar_system",
        )
        lookup = {node["name"]: node for node in updated["nodes"]}

        self.assertEqual(updated.get("layout", {}).get("type"), "solar_system")
        self.assertAlmostEqual(lookup["sun"]["position"][0], 0.0, places=3)
        self.assertAlmostEqual(lookup["sun"]["position"][2], 0.0, places=3)
        self.assertGreater(abs(float(lookup["earth"]["position"][0])) + abs(float(lookup["earth"]["position"][2])), 1.0)


if __name__ == "__main__":
    unittest.main()
