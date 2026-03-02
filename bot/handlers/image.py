"""Image analysis handler — processes screenshots shared in Slack."""

from __future__ import annotations

import json
import logging

from bot.ai.llm import run_completion
from bot.ai.prompts import load_prompt
from bot.ai.vision import analyze_screenshot, unload_model
from integrations.slack_format import format_image_analysis

logger = logging.getLogger("bot.handlers.image")


def handle_image_analysis(
    image_bytes: bytes,
    user_message: str,
    user_id: str,
    say,
) -> None:
    """Analyze a screenshot and respond with structured results.

    Memory strategy: loads Florence-2 on demand, unloads it before
    running Phi-3.5 LLM for interpretation so both models never
    coexist in memory.

    Args:
        image_bytes: Raw image file bytes.
        user_message: Any text the user sent alongside the image.
        user_id: Slack user ID.
        say: Slack ``say`` callable.
    """
    say(":eyes: Analyzing your screenshot...")

    # Step 1: Run Florence-2 vision (OCR + caption)
    try:
        vision_result = analyze_screenshot(image_bytes)
    except Exception:
        logger.exception("Florence-2 inference failed")
        say(":warning: Sorry, I couldn't analyze that image. Please try again.")
        return
    finally:
        # Always free vision model memory before LLM runs
        unload_model()

    caption = vision_result.get("caption", "")
    ocr_text = vision_result.get("ocr_text", "")

    if not caption and not ocr_text:
        say(":thinking_face: I couldn't extract any information from that image. Could you describe what you'd like me to do?")
        return

    # Step 2: Run Phi-3.5 LLM to interpret vision output
    prompt_template = load_prompt("analyze_image")
    system_prompt = prompt_template.format(
        caption=caption,
        ocr_text=ocr_text,
        user_message=user_message or "(no message)",
    )

    try:
        llm_response = run_completion(
            system_prompt=system_prompt,
            user_message="Analyze the screenshot and provide structured output.",
            max_tokens=512,
            temperature=0.1,
        )
    except Exception:
        logger.exception("LLM interpretation failed")
        # Fall back to raw vision output
        say(
            f":camera: Here's what I found in your screenshot:\n\n"
            f"*Description:* {caption}\n"
            f"*Text found:* {ocr_text}"
        )
        return

    # Step 3: Parse LLM JSON and format response
    try:
        analysis = json.loads(llm_response)
    except json.JSONDecodeError:
        logger.warning("LLM returned non-JSON for image analysis: %s", llm_response)
        say(
            f":camera: Here's what I found in your screenshot:\n\n"
            f"*Description:* {caption}\n"
            f"*Text found:* {ocr_text}"
        )
        return

    blocks = format_image_analysis(analysis)
    say(blocks=blocks)
