"""Data-phase logic for AI-powered assignee suggestions."""

from __future__ import annotations

import json
import logging
import re

from bot.ai.llm import run_completion

logger = logging.getLogger("bot.assignee")

SUGGEST_ASSIGNEE_SYSTEM = """\
You are a project-management assistant. Given a ticket and candidate project team \
members with their similar ticket history, pick the best person to assign.

Consider: who worked on similar tickets (strongest signal) and overall project experience.

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


_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "can", "shall", "to", "of", "in", "for",
    "on", "with", "at", "by", "from", "as", "into", "about", "not",
    "and", "or", "but", "if", "then", "so", "than", "that", "this",
    "it", "its", "we", "they", "them", "their", "our", "your", "my",
    "i", "you", "he", "she", "me", "us", "no", "up", "out",
})


def _extract_keywords(text: str, max_keywords: int = 20) -> set[str]:
    """Extract significant lowercase keywords from text."""
    if not text:
        return set()
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    keywords = {w for w in words if w not in _STOPWORDS}
    if len(keywords) > max_keywords:
        seen: set[str] = set()
        for w in words:
            if w not in _STOPWORDS:
                seen.add(w)
                if len(seen) >= max_keywords:
                    break
        return seen
    return keywords


def _compute_ticket_similarity(
    target_labels: set[str],
    target_keywords: set[str],
    other_ticket: dict,
) -> tuple[float, list[str]]:
    """Compute similarity between target ticket and another ticket.

    Returns (score, matched_keywords_list).
    """
    other_labels = _extract_label_names(other_ticket)
    label_score = len(target_labels & other_labels) * 2.0

    other_text = (other_ticket.get("title") or "") + " " + (other_ticket.get("description") or "")
    other_keywords = _extract_keywords(other_text)
    matched = target_keywords & other_keywords
    keyword_score = len(matched) * 1.0

    return label_score + keyword_score, sorted(matched)[:3]


def build_candidate_profiles(
    target_ticket: dict,
    all_tickets: list[dict],
) -> list[dict]:
    """Build per-assignee candidate profiles with relevance stats.

    Only considers candidates from the same project as the target ticket.

    Args:
        target_ticket: The ticket that needs an assignee.
        all_tickets: All tickets from the tracker.

    Returns:
        A list of candidate dicts sorted by relevance_score descending.
        Each dict contains: name, key, total_tickets, project_tickets,
        label_overlap, similarity_score, similar_tickets, relevance_score.
    """
    target_project = _extract_project_name(target_ticket.get("project"))
    target_labels = _extract_label_names(target_ticket)
    target_keywords = _extract_keywords(
        (target_ticket.get("title") or "") + " " + (target_ticket.get("description") or "")
    )

    # Filter to same-project tickets only
    if target_project:
        tickets = [t for t in all_tickets if _extract_project_name(t.get("project")) == target_project]
    else:
        tickets = all_tickets

    candidates: dict[str, dict] = {}

    for ticket in tickets:
        assignee_list = ticket.get("assignees")
        if not assignee_list:
            continue
        if not isinstance(assignee_list, list):
            assignee_list = [assignee_list]

        sim_score, matched_kw = _compute_ticket_similarity(target_labels, target_keywords, ticket)

        for assignee in assignee_list:
            name, key = _extract_assignee_key(assignee)
            if key not in candidates:
                candidates[key] = {
                    "name": name, "key": key,
                    "project_tickets": 0, "total_tickets": 0,
                    "label_overlap": 0,
                    "similarity_score": 0.0,
                    "similar_tickets": [],
                }

            c = candidates[key]
            c["project_tickets"] += 1
            c["total_tickets"] += 1

            ticket_labels = _extract_label_names(ticket)
            if target_labels and ticket_labels:
                c["label_overlap"] += len(target_labels & ticket_labels)

            if sim_score > 0:
                c["similarity_score"] += sim_score
                c["similar_tickets"].append({
                    "id": ticket.get("id", "?"),
                    "title": ticket.get("title", ""),
                    "score": sim_score,
                    "keywords": matched_kw,
                })

    # Sort each candidate's similar_tickets by score, keep top 3
    for c in candidates.values():
        c["similar_tickets"] = sorted(c["similar_tickets"], key=lambda x: x["score"], reverse=True)[:3]
        c["relevance_score"] = (
            c["similarity_score"] * 3.0
            + c["label_overlap"] * 2.0
            + c["total_tickets"] * 0.5
        )

    return sorted(candidates.values(), key=lambda c: c["relevance_score"], reverse=True)


def build_suggestion_prompt(
    target_ticket: dict,
    candidates: list[dict],
    max_candidates: int = 5,
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
    project = _extract_project_name(raw_project) or "Unknown"
    raw_priority = target_ticket.get("priority", "unknown")
    priority = ((raw_priority.get("name") or "unknown") if isinstance(raw_priority, dict) else str(raw_priority)) if raw_priority else "unknown"
    labels = _extract_label_names(target_ticket)
    labels_str = ", ".join(sorted(labels)) if labels else "none"
    desc = (target_ticket.get("description") or "")[:100]

    lines = [
        f"Ticket: {title}",
        f"Project: {project} | Priority: {priority} | Labels: {labels_str}",
        f"Desc: {desc}",
        "",
        f"Candidates (project members of {project}):",
    ]

    for i, c in enumerate(candidates[:max_candidates], 1):
        lines.append(
            f"{i}. {c['name']} ({c['total_tickets']} total tickets in project)"
        )
        similar = c.get("similar_tickets", [])
        if similar:
            parts = []
            for s in similar[:2]:
                kw = ",".join(s["keywords"][:3]) if s["keywords"] else ""
                short_title = s["title"][:30]
                parts.append(f'{s["id"]} "{short_title}" [{kw}]')
            lines.append(f"   Similar: {', '.join(parts)}")
        else:
            lines.append("   Similar: (none)")

    lines.append("")
    lines.append(
        'Pick the best assignee considering similar ticket history and project experience. '
        'Respond ONLY with JSON: {"assignee": "<name>", "reason": "...", "alternative": "<name>", "alt_reason": "..."}'
    )

    return "\n".join(lines)
