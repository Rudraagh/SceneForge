"""Tests for prompt ↔ blueprint filename heuristics and strict-mode notices."""

from __future__ import annotations

import unittest

from sceneforge.blueprint_warnings import collect_blueprint_warnings


class TestCollectBlueprintWarnings(unittest.TestCase):
    def test_ai_mode_strict_notice(self) -> None:
        w = collect_blueprint_warnings(
            prompt="any",
            mode="ai",
            use_blueprint=True,
            blueprint_filename="blueprint_b03_lecture_hall.png",
            blueprint_region_count=5,
        )
        self.assertTrue(any("strict" in x.lower() for x in w))

    def test_rule_mode_no_strict_notice(self) -> None:
        w = collect_blueprint_warnings(
            prompt="any",
            mode="rule",
            use_blueprint=True,
            blueprint_filename="blueprint_b03_lecture_hall.png",
            blueprint_region_count=5,
        )
        self.assertFalse(any("LLM" in x for x in w))

    def test_zero_regions_warning(self) -> None:
        w = collect_blueprint_warnings(
            prompt="classroom",
            mode="rule",
            use_blueprint=True,
            blueprint_filename="x.png",
            blueprint_region_count=0,
        )
        self.assertTrue(any("zero regions" in x.lower() for x in w))

    def test_lecture_prompt_wrong_file(self) -> None:
        w = collect_blueprint_warnings(
            prompt="small lecture hall with student desks",
            mode="rule",
            use_blueprint=True,
            blueprint_filename="blueprint_b02_home_rooms.png",
            blueprint_region_count=4,
        )
        self.assertTrue(any("b03" in x for x in w))

    def test_matching_file_no_mismatch(self) -> None:
        w = collect_blueprint_warnings(
            prompt="small lecture hall with student desks",
            mode="rule",
            use_blueprint=True,
            blueprint_filename="blueprint_b03_lecture_hall.png",
            blueprint_region_count=12,
        )
        self.assertFalse(any("Expected the filename" in x for x in w))

    def test_no_filename_skips_mismatch(self) -> None:
        w = collect_blueprint_warnings(
            prompt="small lecture hall with student desks",
            mode="rule",
            use_blueprint=True,
            blueprint_filename=None,
            blueprint_region_count=8,
        )
        self.assertFalse(any("b03" in x for x in w))


if __name__ == "__main__":
    unittest.main()
