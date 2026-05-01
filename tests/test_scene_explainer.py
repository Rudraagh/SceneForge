"""
QA tests for scene_explainer: parsing, Ollama integration (mocked), and USD listing when pxr exists.
"""

from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from scene_explainer import (
    SceneObject,
    explain_object_in_scene,
    list_scene_objects,
    split_explanation_text,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "minimal_world_scene.usda"


class TestSplitExplanation(unittest.TestCase):
    def test_paragraphs(self):
        raw = "First blurb here.\n\nSecond blurb.\n\nThird is longer text."
        steps = split_explanation_text(raw)
        self.assertGreaterEqual(len(steps), 2)
        self.assertLessEqual(len(steps), 5)

    def test_single_block_splits_by_sentence(self):
        raw = "Mars is the fourth planet. It has a thin atmosphere. Robots have landed there."
        steps = split_explanation_text(raw)
        self.assertGreaterEqual(len(steps), 2)


class TestExplainObjectMocked(unittest.TestCase):
    """Three scene families: classroom, solar system, forest — Ollama HTTP mocked."""

    def _fake_response(self, text: str) -> MagicMock:
        body = json.dumps({"response": text}).encode("utf-8")
        mock_resp = MagicMock()
        mock_resp.__enter__.return_value.read.return_value = body
        mock_resp.__enter__.return_value.status = 200
        return mock_resp

    @patch("scene_explainer.urllib.request.urlopen")
    def test_classroom_blackboard(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_response(
            "A blackboard is a large dark panel for chalk writing.\n\n"
            "In medieval classrooms it held lessons and schedules.\n\n"
            "Students faced it from their desks."
        )
        obj = SceneObject(
            prim_path="/World/blackboard_1",
            prim_name="blackboard_1",
            kind="blackboard",
            label="Blackboard",
            position=(0.0, 0.0, -5.5),
        )
        steps = explain_object_in_scene("a medieval classroom with wooden desks", obj)
        self.assertGreaterEqual(len(steps), 2)
        self.assertIn("blackboard", steps[0].lower())

    @patch("scene_explainer.urllib.request.urlopen")
    def test_solar_mars(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_response(
            "Mars is the fourth planet from the Sun. It is smaller than Earth. "
            "Its surface is cold and dusty. Two small moons orbit Mars."
        )
        obj = SceneObject(
            prim_path="/World/mars_1",
            prim_name="mars_1",
            kind="mars",
            label="Mars",
            position=(-2.0, 0.0, -0.2),
        )
        steps = explain_object_in_scene("a solar system with the sun and planets", obj)
        self.assertGreaterEqual(len(steps), 1)
        joined = " ".join(steps).lower()
        self.assertIn("mars", joined)

    @patch("scene_explainer.urllib.request.urlopen")
    def test_forest_tree(self, mock_urlopen):
        mock_urlopen.return_value = self._fake_response(
            "Pines are evergreen conifers.\n\nThey add vertical mass to a camp scene.\n\n"
            "Needles stay year-round in cold climates."
        )
        obj = SceneObject(
            prim_path="/World/pine_tree_1",
            prim_name="pine_tree_1",
            kind="pine_tree",
            label="Pine Tree",
            position=(-5.5, 0.0, -4.0),
        )
        steps = explain_object_in_scene("a forest camp with trees and a campfire", obj)
        self.assertGreaterEqual(len(steps), 2)


@unittest.skipUnless(FIXTURE.is_file(), "fixture missing")
class TestListSceneObjectsUsd(unittest.TestCase):
    @unittest.skipUnless(
        importlib.util.find_spec("pxr") is not None,
        "Pixar USD (pxr) not installed",
    )
    def test_fixture_lists_three_prims(self):
        objs = list_scene_objects(str(FIXTURE))
        kinds = sorted(o.kind for o in objs)
        self.assertEqual(kinds, ["blackboard", "mars", "pine_tree"])
        paths = {o.prim_path for o in objs}
        self.assertIn("/World/blackboard_1", paths)


if __name__ == "__main__":
    unittest.main()
