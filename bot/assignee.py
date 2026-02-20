"""Data-phase logic for AI-powered assignee suggestions."""

from __future__ import annotations

import json
import logging
import re

from bot.ai.llm import run_completion

logger = logging.getLogger("bot.assignee")

SUGGEST_ASSIGNEE_SYSTEM = """\
You are a project-management assistant. Given a ticket description and a list of \
team-member candidates with their workload stats, pick the best person to assign.

Consider: project experience, label/topic similarity, current workload (fewer active \
tickets is better), and overall experience.

Respond ONLY with a JSON object. No extra text.
/no_think"""


def suggest_assignee(prompt: str) -> dict:
    """Use the LLM to pick the best assignee from a candidate prompt.

    Args:
        prompt: The candidate-summary prompt built by ``build_suggestion_prompt``.

    Returns:
        A dict with ``assignee``, ``reason``, ``alternative``, and ``alt_reason``.
        Falls back to empty strings on any failure.
    """
    fallback = {"assignee": "", "reason": "", "alternative": "", "alt_reason": ""}

    try:
        raw = run_completion(SUGGEST_ASSIGNEE_SYSTEM, prompt, max_tokens=150, temperature=0.1)
    except Exception:
        logger.exception("LLM inference failed for assignee suggestion")
        return fallback

    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        logger.warning("No JSON found in assignee suggestion response: %s", raw)
        return fallback

    try:
        parsed = json.loads(match.group())
    except json.JSONDecodeError:
        logger.warning("Failed to parse assignee suggestion JSON: %s", raw)
        return fallback

    return {
        "assignee": parsed.get("assignee", ""),
        "reason": parsed.get("reason", ""),
        "alternative": parsed.get("alternative", ""),
        "alt_reason": parsed.get("alt_reason", ""),
    }


ACTIVE_STATUSES = {
    "open", "in_progress", "in_review", "review", "todo", "planning", "blocked",
}


def _extract_project_name(project) -> str:
    """Extract a lowercase project name from a project value.

    Handles both ``{"id": 1, "title": "X"}`` dicts and plain strings.
    """
    if isinstance(project, dict):
        return (project.get("title") or project.get("name") or "").lower()
    return (str(project) if project else "").lower()


def _extract_assignee_key(assignee) -> tuple[str, str]:
    """Extract (display_name, canonical_key) from an assignee value.

    Handles both ``{"name": "X", "username": "x"}`` dicts and plain strings.
    """
    if isinstance(assignee, dict):
        name = assignee.get("name", assignee.get("username", "Unknown"))
        key = assignee.get("username", name).lower()
        return name, key
    s = str(assignee)
    return s, s.lower()


def _extract_label_names(ticket: dict) -> set[str]:
    """Normalize labels from a ticket into a lowercase set of label names."""
    labels = ticket.get("labels")
    if not labels:
        return set()
    if not isinstance(labels, list):
        return {str(labels).lower()}
    result = set()
    for label in labels:
        if isinstance(label, dict):
            result.add(label.get("name", str(label)).lower())
        else:
            result.add(str(label).lower())
    return result


def build_candidate_profiles(
    target_ticket: dict,
    all_tickets: list[dict],
) -> list[dict]:
    """Build per-assignee candidate profiles with workload and relevance stats.

    Args:
        target_ticket: The ticket that needs an assignee.
        all_tickets: All tickets from the tracker.

    Returns:
        A list of candidate dicts sorted by relevance_score descending.
        Each dict contains: name, key, total_tickets, active_tickets,
        project_tickets, label_overlap, relevance_score.
    """
    target_project = _extract_project_name(target_ticket.get("project"))
    target_labels = _extract_label_names(target_ticket)

    candidates: dict[str, dict] = {}

    for ticket in all_tickets:
        assignee_list = ticket.get("assignees")
        if not assignee_list:
            continue
        if not isinstance(assignee_list, list):
            assignee_list = [assignee_list]

        status = (ticket.get("status") or "").lower()
        ticket_project = _extract_project_name(ticket.get("project"))
        ticket_labels = _extract_label_names(ticket)

        for assignee in assignee_list:
            name, key = _extract_assignee_key(assignee)
            if key not in candidates:
                candidates[key] = {
                    "name": name,
                    "key": key,
                    "total_tickets": 0,
                    "active_tickets": 0,
                    "project_tickets": 0,
                    "label_overlap": 0,
                }

            c = candidates[key]
            c["total_tickets"] += 1

            if status in ACTIVE_STATUSES:
                c["active_tickets"] += 1

            if target_project and ticket_project == target_project:
                c["project_tickets"] += 1

            if target_labels and ticket_labels:
                c["label_overlap"] += len(target_labels & ticket_labels)

    for c in candidates.values():
        c["relevance_score"] = (
            c["project_tickets"] * 3
            + c["label_overlap"] * 2
            + c["total_tickets"] * 0.5
            - c["active_tickets"] * 1.5
        )

    return sorted(candidates.values(), key=lambda c: c["relevance_score"], reverse=True)


def build_suggestion_prompt(
    target_ticket: dict,
    candidates: list[dict],
    max_candidates: int = 6,
) -> str:
    """Build a compact LLM prompt for assignee suggestion.

    Args:
        target_ticket: The ticket that needs an assignee.
        candidates: Candidate profiles from build_candidate_profiles().
        max_candidates: Maximum candidates to include in the prompt.

    Returns:
        A prompt string for the LLM.
    """
    title = target_ticket.get("title", "Untitled")
    raw_project = target_ticket.get("project", "Unknown")
    if isinstance(raw_project, dict):
        project = raw_project.get("title") or raw_project.get("name") or "Unknown"
    else:
        project = str(raw_project) if raw_project else "Unknown"
    priority = target_ticket.get("priority", "unknown")
    labels = _extract_label_names(target_ticket)
    labels_str = ", ".join(sorted(labels)) if labels else "none"
    desc = (target_ticket.get("description") or "")[:80]

    lines = [
        f"Ticket: {title}",
        f"Project: {project} | Priority: {priority} | Labels: {labels_str}",
        f"Desc: {desc}",
        "",
        "Candidates:",
    ]

    for c in candidates[:max_candidates]:
        lines.append(
            f"- {c['name']}: {c['project_tickets']} project tickets, "
            f"{c['label_overlap']} similar, {c['active_tickets']} active, "
            f"{c['total_tickets']} total"
        )

    lines.append("")
    lines.append(
        'Pick the best assignee. Respond ONLY with JSON: '
        '{"assignee": "<name>", "reason": "...", "alternative": "<name>", "alt_reason": "..."}'
    )

    return "\n".join(lines)
