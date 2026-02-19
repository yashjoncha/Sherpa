"""
Build FAISS vector index from Sherpa RAG dataset.

Usage:
    python scripts/build_fssai_index.py                                        # defaults
    python scripts/build_fssai_index.py --data data/sherpa_rag_dataset.jsonl   # custom file
    python scripts/build_fssai_index.py --index-dir faiss_index                # custom output

Supports:
    - .jsonl  (one JSON object per line — expects "text" field)
    - .json   (list of objects — expects "text" or "content" field)

Each document's "text" field is embedded. Metadata is stored alongside the index.
"""

import argparse
import json
import sys
from pathlib import Path

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
INDEX_FILENAME = "sherpa.index"
METADATA_FILENAME = "sherpa_metadata.json"


def load_data(data_path: Path) -> list[dict]:
    """Load documents from a .jsonl or .json file."""
    documents = []

    if data_path.suffix == ".jsonl":
        with open(data_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    documents.append(json.loads(line))
    elif data_path.suffix == ".json":
        with open(data_path) as f:
            data = json.load(f)
            if isinstance(data, list):
                documents.extend(data)
            else:
                documents.append(data)
    else:
        print(f"Unsupported file format: {data_path.suffix}")
        sys.exit(1)

    print(f"  Loaded {len(documents)} documents from {data_path.name}")
    return documents


def extract_text(doc: dict) -> str:
    """Pull the embeddable text from a document."""
    # JSONL format uses "text", JSON format may use "content" or "title"+"content"
    if doc.get("text"):
        return doc["text"]
    parts = []
    if doc.get("title"):
        parts.append(doc["title"])
    if doc.get("content"):
        parts.append(doc["content"])
    return " — ".join(parts) if parts else ""


def main():
    parser = argparse.ArgumentParser(description="Build FAISS index from Sherpa RAG dataset")
    parser.add_argument(
        "--data",
        type=Path,
        default=Path("data/sherpa_rag_dataset.jsonl"),
        help="Path to .jsonl or .json data file (default: data/sherpa_rag_dataset.jsonl)",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("faiss_index"),
        help="Output directory for FAISS index (default: faiss_index)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help=f"Sentence-transformers model name (default: {MODEL_NAME})",
    )
    args = parser.parse_args()

    if not args.data.exists():
        print(f"Data file not found: {args.data}")
        sys.exit(1)

    # ── 1. Load data ──────────────────────────────────────────────
    print(f"Loading data from {args.data}...")
    documents = load_data(args.data)

    texts = [extract_text(doc) for doc in documents]
    empty_count = sum(1 for t in texts if not t)
    if empty_count:
        print(f"  Warning: {empty_count} documents have no text, skipping them")
        paired = [(doc, text) for doc, text in zip(documents, texts) if text]
        documents, texts = [p[0] for p in paired], [p[1] for p in paired]

    if not texts:
        print("No texts to embed.")
        sys.exit(1)

    # ── 2. Generate embeddings ────────────────────────────────────
    print(f"Loading embedding model: {args.model}")
    model = SentenceTransformer(args.model)

    print(f"Generating embeddings for {len(texts)} documents...")
    embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=True)
    embeddings = np.array(embeddings, dtype="float32")
    print(f"  Embedding shape: {embeddings.shape}")

    # ── 3. Build FAISS index ──────────────────────────────────────
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings)
    print(f"  FAISS index built — {index.ntotal} vectors, dim={dimension}")

    # ── 4. Save index + metadata ──────────────────────────────────
    args.index_dir.mkdir(parents=True, exist_ok=True)

    index_path = args.index_dir / INDEX_FILENAME
    faiss.write_index(index, str(index_path))
    print(f"  Index saved to {index_path}")

    metadata = []
    for i, doc in enumerate(documents):
        entry = {k: v for k, v in doc.items() if k != "text"}
        entry["_index"] = i
        entry["_text_preview"] = texts[i][:200]
        metadata.append(entry)

    meta_path = args.index_dir / METADATA_FILENAME
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Metadata saved to {meta_path}")

    print(f"\nDone! {index.ntotal} vectors indexed.")


if __name__ == "__main__":
    main()
