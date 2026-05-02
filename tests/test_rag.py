"""Unit tests for sceneforge.rag and RAG wiring into scene prompts (no live Ollama)."""

from __future__ import annotations

import os
import unittest
from unittest.mock import MagicMock, patch

import sceneforge.rag as rag_mod
from sceneforge.rag import (
    cosine_similarity,
    rag_globally_disabled,
    reset_rag_runtime_state_for_tests,
    retrieved_context_block,
)


class TestRagCosineSimilarity(unittest.TestCase):
    """Case 1–3: vector similarity helper used for ranking."""

    def test_identical_vector_is_one(self):
        v = [1.0, 2.0, 3.0]
        self.assertAlmostEqual(cosine_similarity(v, v), 1.0, places=5)

    def test_orthogonal_vectors_are_zero(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 0.0], [0.0, 1.0]), 0.0, places=5)

    def test_same_direction_different_length_still_one(self):
        """Cosine ignores magnitude; parallel vectors score 1."""
        self.assertAlmostEqual(cosine_similarity([1.0, 2.0], [3.0, 6.0]), 1.0, places=5)


class TestRagEnvDisable(unittest.TestCase):
    """Case 4: SCENEFORGE_DISABLE_RAG must turn retrieval off."""

    def tearDown(self) -> None:
        reset_rag_runtime_state_for_tests()

    @patch.dict(os.environ, {"SCENEFORGE_DISABLE_RAG": "1"}, clear=False)
    def test_disable_rag_returns_empty_context(self):
        self.assertTrue(rag_globally_disabled())
        self.assertEqual(retrieved_context_block("any prompt about desks"), "")

    @patch.dict(os.environ, {"SCENEFORGE_DISABLE_RAG": "0"}, clear=False)
    def test_explicit_zero_allows_rag_path(self):
        self.assertFalse(rag_globally_disabled())


class TestRagRetrievalWithMocks(unittest.TestCase):
    """Case 5–6: retrieval ranking and graceful empty return."""

    def tearDown(self) -> None:
        reset_rag_runtime_state_for_tests()

    @patch.dict(os.environ, {"SCENEFORGE_DISABLE_RAG": "0", "SCENEFORGE_RAG_TOP_K": "1"}, clear=False)
    def test_retrieved_context_prefers_matching_chunk(self):
        """
        Two corpus rows with 2-D embeddings; query aligned with second row
        should surface that chunk id in the formatted block.
        """
        reset_rag_runtime_state_for_tests()

        def fake_load() -> list[tuple[str, str]]:
            return [
                ("chunk:desks", "wooden_desk chair blackboard classroom layout"),
                ("chunk:space", "mercury venus earth mars solar orbit sun"),
            ]

        emb_desk = [1.0, 0.0]
        emb_space = [0.0, 1.0]
        emb_query = [0.05, 0.95]

        calls: list[list[float]] = []

        def fake_embed(_text: str, timeout_s: float) -> list[float] | None:
            calls.append([timeout_s])
            if len(calls) == 1:
                return emb_desk
            if len(calls) == 2:
                return emb_space
            return emb_query

        with patch.object(rag_mod, "_load_corpus_chunks", side_effect=fake_load):
            with patch.object(rag_mod, "_fetch_embedding", side_effect=fake_embed):
                block = retrieved_context_block("tell me about mars and the solar system", top_k=1)

        self.assertIn("chunk:space", block)
        self.assertIn("mercury venus", block.lower())
        self.assertEqual(len(calls), 3)

    @patch.dict(os.environ, {"SCENEFORGE_DISABLE_RAG": "0"}, clear=False)
    def test_retrieved_context_empty_when_embedding_returns_none(self):
        reset_rag_runtime_state_for_tests()

        with patch.object(rag_mod, "_load_corpus_chunks", return_value=[("only", "some text")]):
            with patch.object(rag_mod, "_fetch_embedding", return_value=None):
                self.assertEqual(retrieved_context_block("prompt"), "")


class TestRagOrchestrationWiring(unittest.TestCase):
    """Case 6 (integration): scene prompt builder prepends RAG when non-empty."""

    def test_build_few_shot_prompt_prepends_rag_block(self):
        from sceneforge.orchestration import build_few_shot_prompt

        fake_ctx = "RETRIEVED_CONTEXT_MARKER\n--- [doc:test] ---\nSynopsis for tests."

        with patch("sceneforge.rag.rag_globally_disabled", return_value=False):
            with patch("sceneforge.rag.retrieved_context_block", return_value=fake_ctx):
                out = build_few_shot_prompt("a small test scene with a lamp")

        self.assertTrue(out.startswith(fake_ctx), msg="RAG block should be prepended to the LLM prompt")
        self.assertIn("You generate 3D scene graphs", out)
        self.assertIn("a small test scene with a lamp", out)


if __name__ == "__main__":
    unittest.main()
