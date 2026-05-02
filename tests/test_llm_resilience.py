from __future__ import annotations

import json
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sceneforge.llm import _compact_retry_prompt, parse_scene_payload, query_scene_llm
from sceneforge.orchestration import build_few_shot_prompt
from sceneforge.scene_understanding import classify_scene


def _fake_response(payload: dict) -> MagicMock:
    body = json.dumps(payload).encode("utf-8")
    mock_resp = MagicMock()
    mock_resp.__enter__.return_value.read.return_value = body
    mock_resp.__enter__.return_value.status = 200
    return mock_resp


class TestLlmResilience(unittest.TestCase):
    def test_compact_retry_prompt_extracts_final_scene_request(self):
        prompt = (
            "Prompt: a forest camp with trees and a campfire\nJSON:\n[]\n\n"
            "Prompt: a classroom with desks and chairs\nJSON:\n"
        )
        compact = _compact_retry_prompt(prompt)
        self.assertIn("Scene prompt: a classroom with desks and chairs", compact)
        self.assertIn("2 wooden_desk", compact)
        self.assertNotIn("forest camp", compact)

    def test_compact_retry_prompt_includes_generic_reasoning_for_custom_prompt(self):
        compact = _compact_retry_prompt("a cozy studio with a table, chairs, bookshelf, and crate")
        self.assertIn("choose one focal object", compact)
        self.assertIn("wall-supporting objects near the perimeter", compact)

    def test_few_shot_prompt_includes_generic_reasoning_for_non_family_scene(self):
        prompt = build_few_shot_prompt("a quiet reading studio with a table, chair, lamp, and bookshelf")
        self.assertIn("For all other scenes: choose one focal object", prompt)

    def test_parse_scene_payload_repairs_missing_commas(self):
        raw = """
        [
          {
            "name": "wooden_desk"
            "position": [0, 0, 0]
            "rotation": [0, 0, 0]
            "scale": [1, 1, 1]
          }
          {
            "name": "chair",
            "position": [0, 0, -2],
            "rotation": [0, 0, 0],
            "scale": [1, 1, 1]
          }
        ]
        """
        payload, repaired = parse_scene_payload(raw)
        self.assertTrue(repaired)
        self.assertEqual(len(payload), 2)
        self.assertEqual(payload[0]["name"], "wooden_desk")

    def test_query_scene_llm_retries_with_lighter_profile_after_timeout(self):
        config = SimpleNamespace(
            ollama_base_url="http://localhost:11434",
            ollama_generate_url="http://localhost:11434/api/generate",
            scene_graph_model="llama3.2:1b",
            llm_timeout_seconds=45.0,
            llm_retries=2,
            llm_max_predict=220,
            llm_num_ctx=2048,
        )
        captured_payloads: list[dict] = []
        responses = [
            TimeoutError("timed out"),
            _fake_response(
                {
                    "response": json.dumps(
                        [
                            {
                                "name": "wooden_desk",
                                "position": [0, 0, 0],
                                "rotation": [0, 0, 0],
                                "scale": [1, 1, 1],
                            }
                        ]
                    )
                }
            ),
        ]

        def fake_urlopen(request, timeout):
            captured_payloads.append(json.loads(request.data.decode("utf-8")))
            response = responses.pop(0)
            if isinstance(response, BaseException):
                raise response
            return response

        with patch("sceneforge.llm.get_config", return_value=config), patch(
            "sceneforge.llm.resolve_ollama_model", return_value="llama3.2:1b"
        ), patch("sceneforge.llm.urllib.request.urlopen", side_effect=fake_urlopen):
            result = query_scene_llm("generate a classroom")

        self.assertEqual(len(result.objects), 1)
        self.assertEqual(captured_payloads[0]["options"]["num_predict"], 220)
        self.assertEqual(captured_payloads[0]["options"]["num_ctx"], 2048)
        self.assertEqual(captured_payloads[1]["options"]["num_predict"], 144)
        self.assertEqual(captured_payloads[1]["options"]["num_ctx"], 1280)
        self.assertIn("Return only valid JSON", captured_payloads[1]["prompt"])

    def test_classify_scene_uses_lightweight_classifier_options(self):
        config = SimpleNamespace(
            ollama_base_url="http://localhost:11434",
            ollama_generate_url="http://localhost:11434/api/generate",
            scene_graph_model="llama3.2:1b",
            llm_timeout_seconds=45.0,
            llm_max_predict=220,
            llm_num_ctx=2048,
        )
        captured_payloads: list[dict] = []

        def fake_urlopen(request, timeout):
            captured_payloads.append(json.loads(request.data.decode("utf-8")))
            return _fake_response(
                {
                    "response": json.dumps(
                        {
                            "scene_type": "classroom",
                            "confidence": 0.88,
                            "reasoning": "Classroom-specific objects were requested.",
                        }
                    )
                }
            )

        with patch("sceneforge.scene_understanding.get_config", return_value=config), patch(
            "sceneforge.scene_understanding.resolve_ollama_model", return_value="llama3.2:1b"
        ), patch("sceneforge.scene_understanding.urllib.request.urlopen", side_effect=fake_urlopen):
            result = classify_scene("instruction area with chalkboard and stools", prefer_llm=True)

        self.assertEqual(result.scene_type, "classroom")
        self.assertEqual(captured_payloads[0]["options"]["num_predict"], 96)
        self.assertEqual(captured_payloads[0]["options"]["num_ctx"], 1024)


if __name__ == "__main__":
    unittest.main()
