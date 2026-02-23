"""Florence-2 vision model — on-demand loading with INT8 quantization."""

from __future__ import annotations

import gc
import io
import logging

import torch
from django.conf import settings
from PIL import Image
from transformers import AutoModelForCausalLM, AutoProcessor

logger = logging.getLogger("bot.ai.vision")

_model = None
_processor = None

MAX_IMAGE_SIZE = 1024


def _resize_image(image: Image.Image) -> Image.Image:
    """Resize image so the longest side is at most MAX_IMAGE_SIZE pixels."""
    w, h = image.size
    if max(w, h) <= MAX_IMAGE_SIZE:
        return image
    scale = MAX_IMAGE_SIZE / max(w, h)
    new_w, new_h = int(w * scale), int(h * scale)
    return image.resize((new_w, new_h), Image.LANCZOS)


def _get_vision_model():
    """Load Florence-2 with INT8 dynamic quantization (CPU-friendly)."""
    global _model, _processor
    if _model is None:
        model_id = settings.FLORENCE2_MODEL_ID
        cache_dir = settings.FLORENCE2_CACHE_DIR
        logger.info("Loading Florence-2 from %s (cache: %s)", model_id, cache_dir)

        _processor = AutoProcessor.from_pretrained(
            model_id,
            cache_dir=cache_dir,
            trust_remote_code=True,
        )
        model = AutoModelForCausalLM.from_pretrained(
            model_id,
            cache_dir=cache_dir,
            trust_remote_code=True,
            torch_dtype=torch.float32,
        )
        # INT8 dynamic quantization — reduces memory ~50%, CPU-compatible
        _model = torch.quantization.quantize_dynamic(
            model,
            {torch.nn.Linear},
            dtype=torch.qint8,
        )
        _model.eval()
        logger.info("Florence-2 loaded and quantized to INT8")
    return _model, _processor


def unload_model() -> None:
    """Free Florence-2 from memory so the LLM can run."""
    global _model, _processor
    if _model is not None:
        del _model
        _model = None
    if _processor is not None:
        del _processor
        _processor = None
    gc.collect()
    logger.info("Florence-2 unloaded from memory")


def analyze_image(image_bytes: bytes, task: str = "<DETAILED_CAPTION>") -> str:
    """Run a single Florence-2 task on an image.

    Args:
        image_bytes: Raw image bytes (PNG, JPEG, etc.).
        task: Florence-2 task token, e.g. ``"<DETAILED_CAPTION>"``,
              ``"<OCR>"``, ``"<CAPTION>"``.

    Returns:
        The model's text output for the given task.
    """
    model, processor = _get_vision_model()
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image = _resize_image(image)

    inputs = processor(text=task, images=image, return_tensors="pt")
    with torch.no_grad():
        generated_ids = model.generate(
            input_ids=inputs["input_ids"],
            pixel_values=inputs["pixel_values"],
            max_new_tokens=1024,
            num_beams=3,
        )
    result = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]
    parsed = processor.post_process_generation(result, task=task, image_size=image.size)
    return parsed.get(task, result)


def analyze_screenshot(image_bytes: bytes) -> dict:
    """Run both OCR and detailed captioning on an image.

    Returns:
        Dict with ``"caption"`` and ``"ocr_text"`` keys.
    """
    caption = analyze_image(image_bytes, task="<DETAILED_CAPTION>")
    ocr_text = analyze_image(image_bytes, task="<OCR>")
    return {
        "caption": caption,
        "ocr_text": ocr_text,
    }
