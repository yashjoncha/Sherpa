"""URL routes for the bot app."""

from django.urls import path

from . import views

app_name = "bot"

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path("slack/events/", views.slack_events, name="slack_events"),
    # VS Code extension endpoints
    path("vscode/extension/download/", views.vscode_download_extension, name="vscode_download_extension"),
    path("vscode/my-tickets/", views.vscode_my_tickets, name="vscode_my_tickets"),
    path("vscode/tickets/", views.vscode_all_tickets, name="vscode_all_tickets"),
    path("vscode/tickets/create/", views.vscode_create_ticket, name="vscode_create_ticket"),
    path("vscode/tickets/<str:ticket_id>/", views.vscode_ticket_detail_or_update, name="vscode_ticket_detail_or_update"),
    path("vscode/members/", views.vscode_members, name="vscode_members"),
    path("vscode/sprints/", views.vscode_sprints, name="vscode_sprints"),
]
