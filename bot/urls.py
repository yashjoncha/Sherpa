"""URL routes for the bot app."""

from django.urls import path

from . import views

app_name = "bot"

urlpatterns = [
    path("health/", views.health_check, name="health_check"),
    path("slack/events/", views.slack_events, name="slack_events"),
    path("vscode/my-tickets/", views.vscode_my_tickets, name="vscode_my_tickets"),
]
