"""AI package — public API for intent classification, LLM completion, and RAG."""

from bot.ai.classifier import classify_intent
from bot.ai.llm import run_completion
from bot.ai.rag import retrieve_context

__all__ = ["classify_intent", "run_completion", "retrieve_context"]
