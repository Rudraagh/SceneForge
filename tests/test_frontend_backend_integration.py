"""Focused integration tests for backend response shaping and scene understanding."""

from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from sceneforge.scene_understanding import detect_scene_type
from sceneforge.orchestration import generate_rule_scene


class TestSceneUnderstanding(unittest.TestCase):
    def test_basketball_prompt_maps_to_basketball_court(self):
        self.assertEqual(detect_scene_type("basketball"), "basketball_court")
        self.assertEqual(detect_scene_type("an outdoor basketball court with hoops"), "basketball_court")

    def test_generic_prompt_rule_scene_uses_prompt_objects(self):
        scene = generate_rule_scene("spaceship with crystal tower and drone")
        names = {item["name"] for item in scene}
        self.assertIn("spaceship", names)
        self.assertIn("crystal_tower", names)
        self.assertIn("drone", names)


class TestPipelineServicePathResolution(unittest.TestCase):
    def test_relative_output_path_resolves_under_project(self):
        from pipeline_service import PROJECT_ROOT, resolve_output_path_from_options

        resolved = resolve_output_path_from_options({"output_path": "generated_scene.usda"})
        self.assertTrue(resolved.endswith("generated_scene.usda"))
        self.assertTrue(os.path.isabs(resolved))
        self.assertIn(os.path.basename(PROJECT_ROOT), resolved)


if __name__ == "__main__":
    unittest.main()
