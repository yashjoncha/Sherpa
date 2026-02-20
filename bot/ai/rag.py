"""FAISS index loading and RAG context retrieval."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import faiss
import numpy as np
from django.conf import settings
from sentence_transformers import SentenceTransformer

logger = logging.getLogger("bot.ai.rag")

_index: faiss.IndexFlatL2 | None = None
_metadata: list[dict] | None = None
_embedder: SentenceTransformer | None = None


def _load_index() -> tuple[faiss.IndexFlatL2, list[dict]]:
    """Load the FAISS index and metadata singletons."""
    global _index, _metadata
    if _index is not None and _metadata is not None:
        return _index, _metadata

    index_dir = Path(settings.FAISS_INDEX_DIR)
    index_path = index_dir / "sherpa.index"
    meta_path = index_dir / "sherpa_metadata.json"

    logger.info("Loading FAISS index from %s", index_path)
    _index = faiss.read_index(str(index_path))
    logger.info("FAISS index loaded — %d vectors", _index.ntotal)

    with open(meta_path) as f:
        _metadata = json.load(f)
    logger.info("Loaded %d metadata entries", len(_metadata))

    return _index, _metadata


def _get_embedder() -> SentenceTransformer:
    """Return the singleton embedding model."""
    global _embedder
    if _embedder is None:
        model_name = settings.RAG_EMBEDDING_MODEL
        logger.info("Loading embedding model: %s", model_name)
        _embedder = SentenceTransformer(model_name)
        logger.info("Embedding model loaded")
    return _embedder


def retrieve_context(query: str, top_k: int = 5) -> list[dict]:
    """Retrieve the most relevant documents for a query.

    Args:
        query: The search query text.
        top_k: Number of results to return.

    Returns:
        A list of metadata dicts for the top-k most similar documents.
        Each dict includes a ``_text_preview`` field with the document text.
        Returns an empty list if the index is not available.
    """
    try:
        index, metadata = _load_index()
    except FileNotFoundError:
        logger.warning("FAISS index not found — RAG unavailable")
        return []

    embedder = _get_embedder()
    query_vec = embedder.encode([query])
    query_vec = np.array(query_vec, dtype="float32")

    distances, indices = index.search(query_vec, top_k)

    results = []
    for i, idx in enumerate(indices[0]):
        if idx < 0 or idx >= len(metadata):
            continue
        entry = dict(metadata[idx])
        entry["_distance"] = float(distances[0][i])
        results.append(entry)

    return results
