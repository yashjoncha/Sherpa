"""AI-powered project matching for repos that don't match via string matching."""

from __future__ import annotations

import json
import logging
import re

from bot.ai.llm import run_completion
from bot.ai.prompts import load_prompt

logger = logging.getLogger("bot.ai.project_matcher")


def match_project_ai(repo_name: str, project_names: list[str]) -> str | None:
    """Use the LLM to pick the best project for a repo name.

    Returns the matched project name (exactly as it appears in *project_names*)
    or ``None`` if no project is a reasonable match.
    """
    if not repo_name or not project_names:
        return None

    system_prompt = load_prompt("project_match")
    user_message = f'Repo: "{repo_name}", Projects: {json.dumps(project_names)}'

    try:
        raw = run_completion(system_prompt, user_message, max_tokens=60, temperature=0.0)
    except Exception:
        logger.exception("LLM inference failed for project matching: %s", repo_name)
        return None

    # Extract JSON from response
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", raw):
        try:
            obj, _ = decoder.raw_decode(raw, match.start())
            if isinstance(obj, dict) and "project" in obj:
                project = obj["project"]
                if project is None:
                    return None
                if isinstance(project, str) and project in project_names:
                    return project
                logger.warning("LLM returned project not in list: %s", project)
                return None
        except json.JSONDecodeError:
            continue

    logger.warning("No valid JSON found in LLM response: %s", raw)
    return None
