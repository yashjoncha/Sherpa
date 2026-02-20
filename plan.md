# Plan: Implement `/hii` Slack Slash Command

## Goal
Register a `/hii` slash command so that when a user types `/hii` in Slack, the bot responds with "hii" in the same channel.

---

## What I Need From You (Before Coding)

### 1. Confirm Slack App Token Validity
You already have these in `.env`:
- `SLACK_BOT_TOKEN` (xoxb-...) — bot token
- `SLACK_APP_TOKEN` (xapp-...) — app-level token (means Socket Mode is available)
- `SLACK_SIGNING_SECRET` — for verifying HTTP requests

**Question:** Are these tokens still active/valid, or were they revoked after the earlier PR revert?

### 2. Register the `/hii` Command in Slack Admin
Before the code works, you need to register the slash command in your Slack App config:
- Go to https://api.slack.com/apps → select your app
- **Slash Commands** → **Create New Command**
  - Command: `/hii`
  - Request URL: (not needed if using Socket Mode)
  - Short Description: "Says hii back"
- **Socket Mode** → make sure it's **enabled** (since you have an `xapp-` token, this is likely already on)
- **OAuth & Permissions** → confirm the bot has `commands` and `chat:write` scopes

No user IDs, workspace IDs, or usernames are needed from you — the tokens already encode which workspace the bot belongs to. Slack sends all that context automatically with every command invocation.

---

## Implementation Plan

### Step 1: Create a Slack Bolt app module
**New file:** `bot/slack_app.py`

- Initialize a Slack Bolt `App` using `SLACK_BOT_TOKEN` and `SLACK_SIGNING_SECRET` from Django settings
- Register a handler for the `/hii` command that responds with "hii"
- This is ~15 lines of code

```python
# Pseudocode
from slack_bolt import App

app = App(token=..., signing_secret=...)

@app.command("/hii")
def handle_hii(ack, respond):
    ack()              # acknowledge within 3 seconds (Slack requirement)
    respond("hii")     # send "hii" back to the user
```

### Step 2: Create a management command to run the bot via Socket Mode
**New file:** `bot/management/commands/run_slack_bot.py`

- Django management command: `python manage.py run_slack_bot`
- Starts the Bolt app in **Socket Mode** using `SLACK_APP_TOKEN`
- Socket Mode means no public URL / ngrok needed — it connects to Slack via WebSocket

```python
# Pseudocode
from slack_bolt.adapter.socket_mode import SocketModeHandler

handler = SocketModeHandler(app, app_token=...)
handler.start()  # blocks and listens
```

### Step 3: Wire up settings
- No new env vars needed — `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, and `SLACK_SIGNING_SECRET` are already in `config/settings.py`

### Step 4: Test it
- Run `python manage.py run_slack_bot`
- Go to Slack, type `/hii` in any channel the bot is in
- Bot should respond with "hii"

---

## Architecture Decision: Socket Mode vs HTTP

| | Socket Mode | HTTP Mode |
|---|---|---|
| Needs public URL? | No | Yes (ngrok for dev) |
| Token needed | `xapp-` (you have it) | Not needed |
| How it works | WebSocket connection | Slack POSTs to your server |
| Best for | Development, small scale | Production at scale |

**Recommendation:** Use **Socket Mode** for now — zero infrastructure needed, and you already have the `xapp-` token. Can switch to HTTP later for production.

---

## Files Changed

| File | Action | Purpose |
|---|---|---|
| `bot/slack_app.py` | **Create** | Bolt app + `/hii` handler |
| `bot/management/commands/run_slack_bot.py` | **Create** | `manage.py run_slack_bot` command |
| `bot/management/__init__.py` | **Create** | Package init (empty) |
| `bot/management/commands/__init__.py` | **Create** | Package init (empty) |

No changes to existing files. No new dependencies (slack-bolt and slack-sdk already in requirements.txt).

---

## Summary
- **From you:** Confirm tokens are valid + register `/hii` in Slack App admin
- **From me:** 2 real files (~30 lines total), 2 empty `__init__.py` files
- **To run:** `python manage.py run_slack_bot`
- **No** ngrok, no public URL, no database changes, no migrations
