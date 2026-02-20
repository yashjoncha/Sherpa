"""
Upload PDF documents to the Sherpa RAG (FAISS) index.

Usage:
    python scripts/upload_pdf_to_rag.py report.pdf                         # single file
    python scripts/upload_pdf_to_rag.py docs/*.pdf                         # multiple files
    python scripts/upload_pdf_to_rag.py report.pdf --chunk-size 800        # custom chunk size
    python scripts/upload_pdf_to_rag.py report.pdf --rebuild               # rebuild index from scratch

The script extracts text from PDFs, splits it into chunks, embeds them,
and adds them to the existing FAISS index (or creates a new one).
"""

import argparse
import json
import sys
from pathlib import Path

import faiss
import numpy as np
import pdfplumber
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"
BATCH_SIZE = 64
INDEX_FILENAME = "sherpa.index"
METADATA_FILENAME = "sherpa_metadata.json"


def extract_text_from_pdf(pdf_path: Path) -> list[dict]:
    """Extract text from a PDF, returning one entry per page."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            text = page.extract_text() or ""
            text = text.strip()
            if text:
                pages.append({"page": i, "text": text})
    return pages


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 100) -> list[str]:
    """Split text into overlapping chunks by character count.

    Uses paragraph boundaries when possible, falling back to
    sentence boundaries, then hard splits.
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        if end >= len(text):
            chunks.append(text[start:].strip())
            break

        # Try to break at a paragraph boundary
        slice_ = text[start:end]
        para_break = slice_.rfind("\n\n")
        if para_break > chunk_size // 3:
            end = start + para_break + 2
        else:
            # Try sentence boundary
            for sep in (". ", "? ", "! ", "\n"):
                sent_break = slice_.rfind(sep)
                if sent_break > chunk_size // 3:
                    end = start + sent_break + len(sep)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        start = end - overlap

    return chunks


def process_pdf(pdf_path: Path, chunk_size: int, overlap: int) -> list[dict]:
    """Extract and chunk a single PDF into RAG documents."""
    filename = pdf_path.name
    print(f"  Processing {filename}...")

    pages = extract_text_from_pdf(pdf_path)
    if not pages:
        print(f"    Warning: no text extracted from {filename}")
        return []

    documents = []
    for page_info in pages:
        chunks = chunk_text(page_info["text"], chunk_size, overlap)
        for j, chunk in enumerate(chunks):
            doc = {
                "id": f"pdf-{pdf_path.stem}-p{page_info['page']}-c{j}",
                "source": "pdf",
                "type": "document",
                "text": chunk,
                "metadata": {
                    "filename": filename,
                    "page": page_info["page"],
                    "chunk": j,
                    "total_chunks_on_page": len(chunks),
                },
            }
            documents.append(doc)

    print(f"    Extracted {len(pages)} pages → {len(documents)} chunks")
    return documents


def load_existing_index(index_dir: Path):
    """Load existing FAISS index and metadata, or return None."""
    index_path = index_dir / INDEX_FILENAME
    meta_path = index_dir / METADATA_FILENAME

    if not index_path.exists() or not meta_path.exists():
        return None, []

    index = faiss.read_index(str(index_path))
    with open(meta_path) as f:
        metadata = json.load(f)

    return index, metadata


def main():
    parser = argparse.ArgumentParser(description="Upload PDFs to Sherpa RAG index")
    parser.add_argument(
        "pdfs",
        type=Path,
        nargs="+",
        help="One or more PDF files to upload",
    )
    parser.add_argument(
        "--index-dir",
        type=Path,
        default=Path("faiss_index"),
        help="FAISS index directory (default: faiss_index)",
    )
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Max characters per chunk (default: 500)",
    )
    parser.add_argument(
        "--overlap",
        type=int,
        default=100,
        help="Character overlap between chunks (default: 100)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=MODEL_NAME,
        help=f"Embedding model (default: {MODEL_NAME})",
    )
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Rebuild index from scratch instead of appending",
    )
    args = parser.parse_args()

    # ── 1. Validate inputs ────────────────────────────────────────
    for pdf_path in args.pdfs:
        if not pdf_path.exists():
            print(f"File not found: {pdf_path}")
            sys.exit(1)
        if pdf_path.suffix.lower() != ".pdf":
            print(f"Not a PDF file: {pdf_path}")
            sys.exit(1)

    # ── 2. Extract and chunk PDFs ─────────────────────────────────
    print("Extracting text from PDFs...")
    all_documents = []
    for pdf_path in args.pdfs:
        docs = process_pdf(pdf_path, args.chunk_size, args.overlap)
        all_documents.extend(docs)

    if not all_documents:
        print("No text extracted from any PDF.")
        sys.exit(1)

    texts = [doc["text"] for doc in all_documents]
    print(f"\nTotal: {len(texts)} chunks from {len(args.pdfs)} file(s)")

    # ── 3. Generate embeddings ────────────────────────────────────
    print(f"\nLoading embedding model: {args.model}")
    model = SentenceTransformer(args.model)

    print(f"Generating embeddings for {len(texts)} chunks...")
    embeddings = model.encode(texts, batch_size=BATCH_SIZE, show_progress_bar=True)
    embeddings = np.array(embeddings, dtype="float32")
    print(f"  Embedding shape: {embeddings.shape}")

    # ── 4. Update or create FAISS index ───────────────────────────
    args.index_dir.mkdir(parents=True, exist_ok=True)

    if args.rebuild:
        existing_index, existing_metadata = None, []
        print("\nRebuilding index from scratch...")
    else:
        existing_index, existing_metadata = load_existing_index(args.index_dir)

    if existing_index is not None:
        print(f"\nAppending to existing index ({existing_index.ntotal} vectors)...")
        start_idx = existing_index.ntotal
        existing_index.add(embeddings)
        index = existing_index
        metadata = existing_metadata
    else:
        print("\nCreating new index...")
        start_idx = 0
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatL2(dimension)
        index.add(embeddings)
        metadata = []

    # ── 5. Build metadata entries ─────────────────────────────────
    for i, doc in enumerate(all_documents):
        entry = {k: v for k, v in doc.items() if k != "text"}
        entry["_index"] = start_idx + i
        entry["_text_preview"] = texts[i][:200]
        metadata.append(entry)

    # ── 6. Save ───────────────────────────────────────────────────
    index_path = args.index_dir / INDEX_FILENAME
    faiss.write_index(index, str(index_path))
    print(f"  Index saved to {index_path} ({index.ntotal} vectors)")

    meta_path = args.index_dir / METADATA_FILENAME
    with open(meta_path, "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"  Metadata saved to {meta_path} ({len(metadata)} entries)")

    print(f"\nDone! Added {len(all_documents)} chunks to the index.")


if __name__ == "__main__":
    main()
