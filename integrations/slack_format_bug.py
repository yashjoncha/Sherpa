"""Slack Block Kit formatter for bug report analysis."""

from __future__ import annotations

import json

from integrations.slack_format import PRIORITY_EMOJI


def format_bug_report(analysis: dict) -> list[dict]:
    """Format a bug report analysis as Slack Block Kit blocks.

    Includes:
    - Bug summary and extracted info
    - Similar existing tickets (if any)
    - Duplicate warning (if likely duplicate)
    - Proposed ticket fields
    - Create / Skip action buttons

    Args:
        analysis: Parsed JSON from the LLM bug analysis.

    Returns:
        A list of Block Kit block dicts.
    """
    summary = analysis.get("summary", "No summary available.")
    extracted_info = analysis.get("extracted_info", [])
    similar_tickets = analysis.get("similar_tickets", [])
    is_duplicate = analysis.get("is_likely_duplicate", False)
    duplicate_note = analysis.get("duplicate_note", "")
    ticket_fields = analysis.get("ticket_fields", {})

    blocks: list[dict] = []

    # Header
    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": ":bug: Bug Report Analysis", "emoji": True},
    })

    # Summary
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": f"*Summary:* {summary}"},
    })

    # Extracted info
    if extracted_info:
        info_lines = "\n".join(f"• {item}" for item in extracted_info)
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Extracted Details:*\n{info_lines}"},
        })

    blocks.append({"type": "divider"})

    # Similar existing tickets
    if similar_tickets:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": ":mag: *Similar Existing Tickets*"},
        })
        for ticket in similar_tickets[:3]:
            title = ticket.get("title", "Untitled")
            preview = ticket.get("preview", "")
            note = ticket.get("similarity_note", "")
            text = f"*{title}*"
            if preview:
                text += f"\n_{preview}_"
            if note:
                text += f"\n:link: {note}"
            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text},
            })
        blocks.append({"type": "divider"})

    # Duplicate warning
    if is_duplicate and duplicate_note:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f":warning: *Possible Duplicate*\n{duplicate_note}",
            },
        })
        blocks.append({"type": "divider"})

    # Proposed ticket fields
    if ticket_fields:
        title = ticket_fields.get("title", "Untitled")
        priority = ticket_fields.get("priority", "medium")
        description = ticket_fields.get("description", "")
        labels = ticket_fields.get("labels", [])

        p_emoji = PRIORITY_EMOJI.get(priority, ":grey_question:")

        fields_text = f"*Proposed Ticket:*\n*Title:* {title}\n*Priority:* {p_emoji} {priority.title()}"
        if description:
            # Truncate long descriptions for the preview
            desc_preview = description[:200] + "..." if len(description) > 200 else description
            fields_text += f"\n*Description:* {desc_preview}"
        if labels:
            label_tags = "  ".join(f"`{lbl}`" for lbl in labels)
            fields_text += f"\n*Labels:* {label_tags}"

        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": fields_text},
        })

        blocks.append({"type": "divider"})

        # Action buttons
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": ":ticket: Create Ticket", "emoji": True},
                    "style": "primary",
                    "action_id": "create_bug_ticket",
                    "value": json.dumps(ticket_fields),
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Skip", "emoji": True},
                    "action_id": "skip_bug_ticket",
                },
            ],
        })

    # Footer
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": ":robot_face: Sherpa Vision AI"},
        ],
    })

    return blocks
