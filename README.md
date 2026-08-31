# Sherpa

**Guiding Your Team to the Summit**

Sherpa is a VS Code extension backed by a small Django service. The service does
one job today: it identifies developers by their GitHub account. The ticket data
source the extension used to read from has been removed, and the endpoints that
served it will return with whatever replaces it.

## Layout

```
sherpa/          Django project and app in one package
  settings.py    project configuration
  urls.py        every route, in one file
  models.py      Member — the only model
  auth.py        GitHub token verification, the @endpoint decorator
  views.py       the HTTP endpoints
  github.py      outbound client for the GitHub API
  migrations/
extension/       the VS Code extension (TypeScript)
```

## Setup

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # fill in your values
python manage.py migrate
python manage.py runserver
```

## Extension

```bash
cd extension
npm install
npm run compile
```

The extension authenticates with VS Code's built-in GitHub session and sends the
token as `Authorization: Bearer <token>`.

## API

| Endpoint | Auth | Purpose |
|---|---|---|
| `GET /api/health/` | none | Health check |
| `GET /api/vscode/me/` | GitHub token | The signed-in developer; doubles as the sign-in check |
| `GET /api/vscode/extension/download/` | none | Download the packaged `.vsix` |

A developer's `Member` record is created automatically the first time they call
an authenticated endpoint, so there is no sign-up step.
