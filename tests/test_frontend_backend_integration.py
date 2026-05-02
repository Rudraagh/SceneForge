"""Focused integration tests for backend response shaping and scene understanding."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sceneforge.scene_understanding import detect_scene_type
from blueprint_parser import _apply_prompt_object_overrides
from sceneforge.orchestration import generate_rule_scene, generate_scene, _augment_scene_for_family, _augment_scene_for_prompt


class TestSceneUnderstanding(unittest.TestCase):
    def test_basketball_prompt_maps_to_basketball_court(self):
        self.assertEqual(detect_scene_type("basketball"), "basketball_court")
        self.assertEqual(detect_scene_type("an outdoor basketball court with hoops"), "basketball_court")

    def test_library_prompt_maps_to_studio_family(self):
        self.assertEqual(detect_scene_type("library"), "studio")

    def test_generic_prompt_rule_scene_uses_prompt_objects(self):
        scene = generate_rule_scene("spaceship with crystal tower and drone")
        names = {item["name"] for item in scene}
        self.assertIn("spaceship", names)
        self.assertIn("crystal_tower", names)
        self.assertIn("drone", names)

    def test_generic_prompt_rule_scene_preserves_plural_courtyard_objects(self):
        scene = generate_rule_scene("outdoor courtyard with stone benches, a central fountain, and shaded trees along the eastern edge")
        names = [item["name"] for item in scene]
        self.assertGreaterEqual(sum(1 for name in names if "bench" in name), 2)
        self.assertIn("fountain", names)
        self.assertGreaterEqual(sum(1 for name in names if "tree" in name), 2)

    def test_under_specified_ai_classroom_gets_completed(self):
        scene = _augment_scene_for_family(
            [
                {"name": "wooden_desk", "position": [-2.0, 0.0, 1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "wooden_desk", "position": [2.0, 0.0, 1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "classroom",
            "classroom",
        )
        names = [item["name"] for item in scene]
        self.assertGreaterEqual(sum(1 for name in names if "chair" in name), 2)
        self.assertTrue(any("board" in name for name in names))
        self.assertGreaterEqual(len(scene), 5)

    def test_under_specified_ai_classroom_with_numbered_names_gets_completed(self):
        scene = _augment_scene_for_family(
            [
                {"name": "wooden_desk_1", "position": [-2.0, 0.0, 1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "wooden_desk_2", "position": [2.0, 0.0, 1.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "classroom",
            "classroom",
        )
        names = [item["name"] for item in scene]
        self.assertEqual(sum(1 for name in names if "desk" in name), 2)
        self.assertGreaterEqual(sum(1 for name in names if "chair" in name), 2)
        self.assertTrue(any("board" in name for name in names))

    def test_under_specified_ai_throne_room_gets_completed(self):
        scene = _augment_scene_for_family(
            [
                {"name": "throne", "position": [0.0, 0.0, -4.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "banner", "position": [-4.0, 0.0, -5.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
                {"name": "torch", "position": [-5.0, 0.0, -2.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "a royal throne room with banners and torches",
            "throne_room",
        )
        names = [item["name"] for item in scene]
        self.assertGreaterEqual(sum(1 for name in names if "banner" in name), 2)
        self.assertGreaterEqual(sum(1 for name in names if "torch" in name), 2)
        self.assertGreaterEqual(sum(1 for name in names if "bench" in name), 2)
        self.assertGreaterEqual(sum(1 for name in names if "throne" in name), 1)

    def test_generate_scene_backfills_sparse_ai_classroom_output(self):
        sparse_scene = [
            {"name": "wooden_desk_1", "position": [-1.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            {"name": "wooden_desk_2", "position": [1.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ]
        with patch("sceneforge.orchestration.query_local_model", return_value=sparse_scene):
            scene = generate_scene("a medieval classroom with wooden desks", mode="ai")
        names = [item["name"] for item in scene]
        self.assertGreaterEqual(sum(1 for name in names if "desk" in name), 2)
        self.assertGreaterEqual(sum(1 for name in names if "chair" in name), 2)
        self.assertTrue(any("board" in name for name in names))

    def test_under_specified_ai_generic_prompt_gets_completed_from_prompt(self):
        scene = _augment_scene_for_prompt(
            [
                {"name": "pine_tree", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
            ],
            "outdoor courtyard with stone benches, a central fountain, and shaded trees along the eastern edge",
        )
        names = [item["name"] for item in scene]
        self.assertGreaterEqual(sum(1 for name in names if "bench" in name), 2)
        self.assertIn("fountain", names)
        self.assertGreaterEqual(sum(1 for name in names if "tree" in name), 2)

    def test_generate_scene_backfills_sparse_ai_generic_prompt_output(self):
        sparse_scene = [
            {"name": "pine_tree", "position": [0.0, 0.0, 0.0], "rotation": [0.0, 0.0, 0.0], "scale": [1.0, 1.0, 1.0]},
        ]
        prompt = "outdoor courtyard with stone benches, a central fountain, and shaded trees along the eastern edge"
        with patch("sceneforge.orchestration.query_local_model", return_value=sparse_scene):
            scene = generate_scene(prompt, mode="ai")
        names = [item["name"] for item in scene]
        self.assertGreaterEqual(sum(1 for name in names if "bench" in name), 2)
        self.assertIn("fountain", names)
        self.assertGreaterEqual(sum(1 for name in names if "tree" in name), 2)

    def test_throne_room_rule_scene_uses_smaller_throne_and_bigger_benches(self):
        scene = generate_rule_scene("a royal throne room with banners and torches")
        throne = next(item for item in scene if item["name"] == "throne")
        banners = [item for item in scene if item["name"] == "banner"]
        benches = [item for item in scene if item["name"] == "bench"]

        self.assertLess(throne["scale"][0], 1.0)
        self.assertTrue(all(item["scale"][1] < 1.0 for item in banners))
        self.assertTrue(all(item["scale"][0] > 1.0 for item in benches))

    def test_rule_scene_applies_prompt_scale_hints(self):
        scene = generate_rule_scene("a royal throne room with a small throne and huge banners")
        throne = next(item for item in scene if item["name"] == "throne")
        banners = [item for item in scene if item["name"] == "banner"]

        self.assertLess(throne["scale"][0], 0.62)
        self.assertTrue(all(item["scale"][1] > 1.0 for item in banners))


class TestPipelineServicePathResolution(unittest.TestCase):
    def test_relative_output_path_resolves_under_project(self):
        from pipeline_service import PROJECT_ROOT, resolve_output_path_from_options

        resolved = resolve_output_path_from_options({"output_path": "generated_scene.usda"})
        self.assertTrue(resolved.endswith("generated_scene.usda"))
        self.assertTrue(os.path.isabs(resolved))
        self.assertIn(os.path.basename(PROJECT_ROOT), resolved)


class TestBlueprintPromptOverrides(unittest.TestCase):
    def test_library_prompt_remaps_blackboard_like_blueprint_region_to_bookshelf(self):
        remapped = _apply_prompt_object_overrides(
            [
                {"name": "blackboard", "x": 0.5, "y": 0.1},
                {"name": "bookshelf", "x": 0.1, "y": 0.5},
                {"name": "chair", "x": 0.3, "y": 0.7},
            ],
            "library",
        )
        names = [item["name"] for item in remapped]
        self.assertEqual(sum(1 for name in names if name == "bookshelf"), 2)
        self.assertNotIn("blackboard", names)


if __name__ == "__main__":
    unittest.main()
