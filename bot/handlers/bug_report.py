"""Bug report handler — analyzes bug screenshots with RAG duplicate check."""

from __future__ import annotations

import json
import logging

from bot.ai.llm import run_completion
from bot.ai.prompts import load_prompt
from bot.ai.rag import retrieve_context
from bot.ai.vision import analyze_screenshot, unload_model
from integrations.slack_format_bug import format_bug_report

logger = logging.getLogger("bot.handlers.bug_report")


def handle_bug_screenshot(
    image_bytes: bytes,
    user_message: str,
    user_id: str,
    say,
) -> None:
    """Analyze a bug screenshot, check for duplicates via RAG, and propose a ticket.

    Flow:
    1. Run Florence-2 vision (OCR + caption)
    2. Query RAG for similar existing tickets
    3. Run Phi-3.5 LLM to interpret and produce structured bug report
    4. Format and send Block Kit response with "Create Ticket" button

    Args:
        image_bytes: Raw image file bytes.
        user_message: Any text the user sent alongside the image.
        user_id: Slack user ID.
        say: Slack ``say`` callable.
    """
    say(":mag: Analyzing bug screenshot...")

    # Step 1: Run Florence-2 vision (OCR + caption)
    try:
        vision_result = analyze_screenshot(image_bytes)
    except Exception:
        logger.exception("Florence-2 inference failed for bug screenshot")
        say(":warning: Sorry, I couldn't analyze that image. Please try again.")
        return
    finally:
        unload_model()

    caption = vision_result.get("caption", "")
    ocr_text = vision_result.get("ocr_text", "")

    if not caption and not ocr_text:
        say(
            ":thinking_face: I couldn't extract any information from that image. "
            "Could you describe the bug you're seeing?"
        )
        return

    # Step 2: RAG — find similar existing tickets
    rag_query = f"{caption} {ocr_text}".strip()
    try:
        context_docs = retrieve_context(rag_query, top_k=5)
    except Exception:
        logger.warning("RAG retrieval failed; continuing without context")
        context_docs = []

    if context_docs:
        rag_context = "\n".join(
            f"- [{doc.get('ticket_id', 'N/A')}] {doc.get('_text_preview', 'N/A')}"
            for doc in context_docs
        )
    else:
        rag_context = "No similar tickets found in the knowledge base."

    # Step 3: Run Phi-3.5 LLM to interpret vision output + RAG context
    prompt_template = load_prompt("analyze_bug_screenshot")
    system_prompt = prompt_template.format(
        caption=caption,
        ocr_text=ocr_text,
        user_message=user_message or "(no message)",
        rag_context=rag_context,
    )

    try:
        llm_response = run_completion(
            system_prompt=system_prompt,
            user_message="Analyze the bug screenshot and provide structured output.",
            max_tokens=700,
            temperature=0.1,
        )
    except Exception:
        logger.exception("LLM interpretation failed for bug screenshot")
        say(
            f":bug: Here's what I found in your screenshot:\n\n"
            f"*Description:* {caption}\n"
            f"*Text found:* {ocr_text}"
        )
        return

    # Step 4: Parse JSON and format response
    try:
        analysis = json.loads(llm_response)
    except json.JSONDecodeError:
        # Try to extract JSON from mixed output
        analysis = _extract_json(llm_response)

    if not analysis:
        logger.warning("LLM returned non-JSON for bug analysis: %s", llm_response)
        say(
            f":bug: Here's what I found in your screenshot:\n\n"
            f"*Description:* {caption}\n"
            f"*Text found:* {ocr_text}"
        )
        return

    blocks = format_bug_report(analysis)
    say(blocks=blocks)


def _extract_json(raw: str) -> dict | None:
    """Extract the first valid JSON object from LLM output."""
    import re

    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", raw):
        try:
            obj, _ = decoder.raw_decode(raw, match.start())
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None
