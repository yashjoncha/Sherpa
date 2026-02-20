"""Handler registry — maps intent strings to handler functions."""

from bot.handlers.simple import (
    handle_all_tickets,
    handle_greeting,
    handle_my_tickets,
    handle_stale_tickets,
    handle_ticket_detail,
)
from bot.handlers.complex import (
    handle_create_ticket,
    handle_eod_summary,
    handle_smart_assign,
    handle_sprint_health,
    handle_sprint_retro,
    handle_summary,
    handle_update_ticket,
)

HANDLER_REGISTRY: dict[str, callable] = {
    # Simple handlers (no 2nd LLM call)
    "my_tickets": handle_my_tickets,
    "all_tickets": handle_all_tickets,
    "ticket_detail": handle_ticket_detail,
    "stale_tickets": handle_stale_tickets,
    "greeting": handle_greeting,
    # Complex handlers (2nd LLM call)
    "create_ticket": handle_create_ticket,
    "update_ticket": handle_update_ticket,
    "smart_assign": handle_smart_assign,
    "summary": handle_summary,
    "sprint_health": handle_sprint_health,
    "sprint_retro": handle_sprint_retro,
    "eod_summary": handle_eod_summary,
}
