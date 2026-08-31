# Sherpa Tickets

View and manage your Sherpa tickets from the VS Code sidebar.

## Features

- **My Tickets** — your assigned tickets in the activity bar, auto-filtered to
  the project matching your current git repo
- **Sprint Progress** — a live breakdown of the active sprint
- **Ticket detail panel** — open a ticket, edit status, priority, and assignee
- **Create tickets** — without leaving the editor

## Setup

Sign in with GitHub when prompted — the extension uses VS Code's built-in
GitHub account, so there is no separate login.

Then point it at your server:

**Settings → Extensions → Sherpa Tickets → `sherpa.apiUrl`**

## Status

The ticket data source is currently being replaced. GitHub sign-in works; the
**My Tickets** and **Sprint Progress** views will not return data until the new
backend lands.
