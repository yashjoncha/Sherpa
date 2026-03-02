#!/usr/bin/env python
"""Pre-download Florence-2 model so first Slack image analysis isn't slow.

Usage:
    python scripts/download_florence2.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow running from project root without Django
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

MODEL_ID = "microsoft/Florence-2-base"
CACHE_DIR = PROJECT_ROOT / "models" / "florence2"


def main() -> None:
    from transformers import AutoModelForCausalLM, AutoProcessor

    print(f"Downloading Florence-2 model: {MODEL_ID}")
    print(f"Cache directory: {CACHE_DIR}")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    print("\nDownloading processor...")
    AutoProcessor.from_pretrained(
        MODEL_ID,
        cache_dir=str(CACHE_DIR),
        trust_remote_code=True,
    )
    print("Processor downloaded.")

    print("\nDownloading model weights...")
    AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        cache_dir=str(CACHE_DIR),
        trust_remote_code=True,
    )
    print("Model downloaded.")

    print(f"\nDone! Model cached at {CACHE_DIR}")


if __name__ == "__main__":
    main()
