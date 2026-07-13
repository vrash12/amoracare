import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-secret-key")

DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"

ALLOWED_HOSTS = ["*"]
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
TAVILY_SEARCH_URL = os.getenv("TAVILY_SEARCH_URL", "https://api.tavily.com/search")
TAVILY_ENABLED = os.getenv("TAVILY_ENABLED", "false").lower() == "true"

INSTALLED_APPS = [
    # default django apps...
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # third-party
    "rest_framework",

    # local apps
    "apps.core",
    "apps.legal_guidance",
]

LEGAL_DOCUMENTS_DIR = BASE_DIR / "legal_documents"

QWEN_CLOUD_RUN_URL = os.getenv("QWEN_CLOUD_RUN_URL", "").rstrip("/")
QWEN_MODEL = os.getenv("QWEN_MODEL", "qwen3-4b")

LEGAL_MAX_CONTEXT_CHARACTERS = int(
    os.getenv("LEGAL_MAX_CONTEXT_CHARACTERS", "6000")
)