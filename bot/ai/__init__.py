"""AI package — public API for intent classification, LLM completion, RAG, and vision."""

from bot.ai.classifier import classify_intent
from bot.ai.llm import run_completion
from bot.ai.rag import retrieve_context
from bot.ai.vision import analyze_image, analyze_screenshot

__all__ = [
    "classify_intent",
    "run_completion",
    "retrieve_context",
    "analyze_image",
    "analyze_screenshot",
]
