# Sherpa

**Guiding Your Team to the Summit**

Sherpa is an AI-powered Slack bot that acts as a Project Manager for engineering teams. It integrates with GitHub and uses local LLMs to provide sprint management, code review assistance, and team coordination — all from within Slack.

## Tech Stack

- **Backend:** Django, Django REST Framework, Celery
- **Integrations:** Slack (Bolt), GitHub API
- **Infrastructure:** PostgreSQL, Redis

## Setup

```bash
git clone <repo-url> && cd Sherpa
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your values
python manage.py migrate
python manage.py runserver
```
