"""Unit tests for blueprint PNG to world-space mapping."""

from __future__ import annotations

import unittest

from blueprint_mapper import LAMP_BLUEPRINT_Y_OFFSET, map_blueprint_to_scene, normalized_to_world


class TestNormalizedToWorld(unittest.TestCase):
    def test_image_top_toward_positive_z(self) -> None:
        _x, z = normalized_to_world(0.5, 0.0)
        self.assertGreater(z, 0.0)

    def test_image_bottom_toward_negative_z(self) -> None:
        _x, z = normalized_to_world(0.5, 1.0)
        self.assertLess(z, 0.0)

    def test_center_depth_near_zero(self) -> None:
        _x, z = normalized_to_world(0.5, 0.5)
        self.assertAlmostEqual(z, 0.0, places=5)


class TestMapBlueprintToScene(unittest.TestCase):
    def test_lamp_gets_vertical_offset(self) -> None:
        scene = map_blueprint_to_scene([{"name": "lamp_1", "x": 0.5, "y": 0.5}])
        self.assertEqual(len(scene), 1)
        self.assertAlmostEqual(scene[0]["position"][1], LAMP_BLUEPRINT_Y_OFFSET, places=5)

    def test_chair_stays_on_floor(self) -> None:
        scene = map_blueprint_to_scene([{"name": "chair_1", "x": 0.5, "y": 0.5}])
        self.assertEqual(len(scene), 1)
        self.assertAlmostEqual(scene[0]["position"][1], 0.0, places=5)


if __name__ == "__main__":
    unittest.main()
