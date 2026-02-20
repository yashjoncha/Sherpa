"""Django settings for the Sherpa project."""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
)
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "bot",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {"default": env.db("DATABASE_URL")}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": env("REDIS_URL", default="redis://localhost:6379/0"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Celery
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"

# Slack
SLACK_BOT_TOKEN = env("SLACK_BOT_TOKEN", default="")
SLACK_SIGNING_SECRET = env("SLACK_SIGNING_SECRET", default="")
SLACK_APP_TOKEN = env("SLACK_APP_TOKEN", default="")

# Tracker
TRACKER_API_URL = env("TRACKER_API_URL", default="https://tracker.blaziken.in")
TRACKER_API_TOKEN = env("TRACKER_API_TOKEN", default="")

# GitHub
GITHUB_WEBHOOK_SECRET = env("GITHUB_WEBHOOK_SECRET", default="")

# LLM
LLM_MODEL_PATH = env(
    "LLM_MODEL_PATH",
    default=str(BASE_DIR / "models" / "Phi-3.5-mini-instruct-Q4_K_M.gguf"),
)
LLM_N_CTX = env.int("LLM_N_CTX", default=2048)
LLM_N_THREADS = env.int("LLM_N_THREADS", default=2)

# RAG / FAISS
FAISS_INDEX_DIR = env("FAISS_INDEX_DIR", default=str(BASE_DIR / "faiss_index"))
RAG_EMBEDDING_MODEL = env("RAG_EMBEDDING_MODEL", default="all-MiniLM-L6-v2")
