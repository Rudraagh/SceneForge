"""
Local RAG helpers: embed queries and corpus chunks with Ollama, rank by cosine
similarity (numpy), and inject top snippets into LLM prompts.

Env:
  SCENEFORGE_DISABLE_RAG — set to 1 to skip retrieval (tests, or no embed model).
  OLLAMA_EMBED_MODEL — default nomic-embed-text (pull with: ollama pull nomic-embed-text).
  SCENEFORGE_RAG_TOP_K — chunks to inject (default 4).
"""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from typing import List, Sequence, Tuple

import numpy as np

from sceneforge.config import get_config
from sceneforge.logging_utils import get_logger


LOGGER = get_logger(__name__)

_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text").strip()
_TOP_K = max(1, int(os.getenv("SCENEFORGE_RAG_TOP_K", "4")))
_EMBED_UNAVAILABLE = False
_CORPUS_CHUNKS: List[Tuple[str, str]] | None = None
_EMBED_MATRIX: np.ndarray | None = None


def rag_globally_disabled() -> bool:
    """Read on each call so tests can toggle SCENEFORGE_DISABLE_RAG via patch.dict."""

    return os.getenv("SCENEFORGE_DISABLE_RAG", "0").strip() == "1"


def _ollama_embed_url() -> str:
    return f"{get_config().ollama_base_url}/api/embeddings"


def _fetch_embedding(text: str, timeout_s: float) -> List[float] | None:
    payload = json.dumps({"model": _EMBED_MODEL, "prompt": text}).encode("utf-8")
    request = urllib.request.Request(
        _ollama_embed_url(),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Ollama embedding request failed: %s", exc)
        return None
    emb = body.get("embedding")
    if not isinstance(emb, list) or not emb:
        LOGGER.warning("Ollama returned no embedding vector.")
        return None
    return [float(x) for x in emb]


def _load_corpus_chunks() -> List[Tuple[str, str]]:
    """Return (chunk_id, text) pairs built from scene_dataset, asset registry, and optional markdown."""

    cfg = get_config()
    rows: List[Tuple[str, str]] = []

    if cfg.dataset_path.is_file():
        with cfg.dataset_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        if isinstance(data, list):
            for index, item in enumerate(data):
                if not isinstance(item, dict):
                    continue
                prompt = str(item.get("prompt", "")).strip()
                objects = item.get("objects")
                if not isinstance(objects, list):
                    continue
                body = (
                    f"Example scene prompt: {prompt}\n"
                    f"Example JSON objects array (name, position, rotation, scale):\n"
                    f"{json.dumps(objects, indent=2)}"
                )
                rows.append((f"scene_dataset:{index}", body))

    from sceneforge.asset_registry import registry_entries

    for desc in registry_entries():
        alias_txt = ", ".join(desc.aliases) if desc.aliases else ""
        cat_txt = ", ".join(desc.categories) if desc.categories else ""
        src_txt = ", ".join(desc.preferred_sources) if desc.preferred_sources else ""
        rows.append(
            (
                f"asset:{desc.name}",
                f"Canonical asset `{desc.name}`. Aliases: {alias_txt}. "
                f"Categories: {cat_txt}. Preferred sources: {src_txt}.",
            )
        )

    corpus_md = cfg.project_root / "rag_corpus" / "sceneforge_rag.md"
    if corpus_md.is_file():
        raw = corpus_md.read_text(encoding="utf-8", errors="replace")
        sections = re.split(r"\n##\s+", raw)
        for i, block in enumerate(sections):
            block = block.strip()
            if len(block) < 40:
                continue
            title = block.split("\n", 1)[0].strip("# ").strip()
            rows.append((f"doc:{i}:{title[:40]}", block[:6000]))

    return rows


def _ensure_corpus_loaded() -> None:
    global _CORPUS_CHUNKS
    if _CORPUS_CHUNKS is None:
        _CORPUS_CHUNKS = _load_corpus_chunks()


def _ensure_index_built(timeout_s: float) -> bool:
    """Embed all corpus rows once. Returns False if embeddings are unavailable."""

    global _EMBED_MATRIX, _EMBED_UNAVAILABLE

    if _EMBED_UNAVAILABLE or rag_globally_disabled():
        return False
    _ensure_corpus_loaded()
    if not _CORPUS_CHUNKS:
        return False
    if _EMBED_MATRIX is not None:
        return True

    vectors: List[List[float]] = []
    for _cid, text in _CORPUS_CHUNKS:
        vec = _fetch_embedding(text[:8000], timeout_s=timeout_s)
        if vec is None:
            _EMBED_UNAVAILABLE = True
            _EMBED_MATRIX = None
            LOGGER.warning(
                "Disabling RAG for this process: embedding model `%s` unreachable or not installed. "
                "Install with: ollama pull %s   Or set SCENEFORGE_DISABLE_RAG=1.",
                _EMBED_MODEL,
                _EMBED_MODEL,
            )
            return False
        vectors.append(vec)

    if not vectors:
        return False
    dim = len(vectors[0])
    if any(len(v) != dim for v in vectors):
        LOGGER.warning("Embedding dimension mismatch; disabling RAG.")
        _EMBED_UNAVAILABLE = True
        return False

    _EMBED_MATRIX = np.asarray(vectors, dtype=np.float64)
    return True


def _top_chunk_indices(query: str, k: int, timeout_s: float) -> List[int]:
    if not _ensure_index_built(timeout_s):
        return []
    assert _CORPUS_CHUNKS is not None and _EMBED_MATRIX is not None
    q = _fetch_embedding(query[:8000], timeout_s=timeout_s)
    if q is None:
        return []
    qv = np.asarray(q, dtype=np.float64)
    mat = _EMBED_MATRIX
    qn = qv / (np.linalg.norm(qv) + 1e-9)
    mn = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    sims = mn @ qn
    order = np.argsort(-sims)
    return [int(i) for i in order[: min(k, len(order))]]


def retrieved_context_block(query: str, top_k: int | None = None) -> str:
    """
    Return a single string to prepend to an Ollama prompt, or empty if RAG is off or unavailable.
    """

    if rag_globally_disabled():
        return ""
    k = top_k or _TOP_K
    timeout_s = float(os.getenv("SCENEFORGE_RAG_EMBED_TIMEOUT_S", "20"))
    try:
        indices = _top_chunk_indices(query, k=k, timeout_s=timeout_s)
    except Exception as exc:  # pragma: no cover - defensive
        LOGGER.warning("RAG retrieval failed: %s", exc)
        return ""
    if not indices or _CORPUS_CHUNKS is None:
        return ""

    parts: List[str] = [
        "The following snippets are retrieved from the SceneForge project corpus. "
        "Treat them as authoritative for asset names, JSON shape, and scene conventions. "
        "If the user prompt conflicts with a snippet, prefer the snippet for naming and layout rules.",
    ]
    chosen_ids: List[str] = []
    for i in indices:
        cid, text = _CORPUS_CHUNKS[i]
        chosen_ids.append(cid)
        parts.append(f"--- [{cid}] ---\n{text.strip()}")
    body = "\n\n".join(parts).strip()
    LOGGER.info(
        "RAG active: prepended %s chunk(s) to the next Ollama prompt (ids: %s; ~%s chars).",
        len(indices),
        ", ".join(chosen_ids),
        len(body),
    )
    return body


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Exposed for unit tests (pure numpy)."""

    va = np.asarray(a, dtype=np.float64)
    vb = np.asarray(b, dtype=np.float64)
    denom = (np.linalg.norm(va) + 1e-9) * (np.linalg.norm(vb) + 1e-9)
    return float(np.dot(va, vb) / denom)


def reset_rag_runtime_state_for_tests() -> None:
    """Clear cached corpus/index (unittest only)."""

    global _CORPUS_CHUNKS, _EMBED_MATRIX, _EMBED_UNAVAILABLE
    _CORPUS_CHUNKS = None
    _EMBED_MATRIX = None
    _EMBED_UNAVAILABLE = False
