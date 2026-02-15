"""Slack Block Kit message formatting helpers."""

from __future__ import annotations


def format_ticket_summary(title: str, status: str, assignee: str) -> list[dict]:
    """Format a ticket summary as Block Kit blocks.

    Args:
        title: The ticket title.
        status: Current ticket status.
        assignee: Display name of the assignee.

    Returns:
        A list of Block Kit block dicts.
    """
    return []


def format_sprint_report(sprint_name: str, stats: dict) -> list[dict]:
    """Format a sprint report as Block Kit blocks.

    Args:
        sprint_name: Human-readable sprint name.
        stats: Dict with keys like ``completed``, ``in_progress``, ``remaining``.

    Returns:
        A list of Block Kit block dicts.
    """
    return []


def format_code_review(file_path: str, comments: list[dict]) -> list[dict]:
    """Format code-review feedback as Block Kit blocks.

    Args:
        file_path: Path of the reviewed file.
        comments: List of comment dicts with ``line``, ``message``, ``severity``.

    Returns:
        A list of Block Kit block dicts.
    """
    return []


def format_error_message(error: str) -> list[dict]:
    """Format an error message as Block Kit blocks.

    Args:
        error: The error description.

    Returns:
        A list of Block Kit block dicts.
    """
    return []
