# config/settings.py

from pathlib import Path
import os

from dotenv import load_dotenv


# =============================================================================
# BASE DIRECTORY AND ENVIRONMENT
# =============================================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Used for local development.
# Cloud Run will normally provide environment variables through its service
# configuration and Secret Manager.
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    """
    Read a boolean environment variable.

    Accepted true values:
    1, true, yes, on
    """
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def env_list(name: str, default: str = "") -> list[str]:
    """
    Read a comma-separated environment variable as a cleaned list.
    """
    value = os.getenv(name, default)

    return [
        item.strip()
        for item in value.split(",")
        if item.strip()
    ]


def env_int(name: str, default: int) -> int:
    """
    Read an integer environment variable safely.
    """
    value = os.getenv(name)

    if value is None:
        return default

    try:
        return int(value)
    except (TypeError, ValueError):
        return default


# Cloud Run automatically provides K_SERVICE at runtime.
IS_CLOUD_RUN = bool(os.getenv("K_SERVICE"))


# =============================================================================
# DJANGO SECURITY
# =============================================================================

# Local development defaults to True.
# Cloud Run defaults to False.
DEBUG = env_bool(
    "DJANGO_DEBUG",
    default=not IS_CLOUD_RUN,
)


SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "",
).strip()

if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "local-dev-secret-key-change-this"
    else:
        raise RuntimeError(
            "DJANGO_SECRET_KEY is required when DJANGO_DEBUG=False."
        )


default_allowed_hosts = "127.0.0.1,localhost"

if IS_CLOUD_RUN:
    # Allows the generated Cloud Run hostname.
    # After deployment, you can replace this with the exact Cloud Run hostname.
    default_allowed_hosts += ",.run.app"


ALLOWED_HOSTS = env_list(
    "DJANGO_ALLOWED_HOSTS",
    default=default_allowed_hosts,
)


# Enter complete origins including https://
#
# Example:
# https://amoracare-ai-123456789.asia-southeast1.run.app
#
# This is normally unnecessary for Laravel server-to-server requests, but it
# can be needed for Django Admin, browser forms, or browser-based requests.
CSRF_TRUSTED_ORIGINS = env_list(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default="",
)


# Cloud Run terminates HTTPS before forwarding requests to the container.
SECURE_PROXY_SSL_HEADER = (
    "HTTP_X_FORWARDED_PROTO",
    "https",
)

SECURE_SSL_REDIRECT = env_bool(
    "DJANGO_SECURE_SSL_REDIRECT",
    default=IS_CLOUD_RUN,
)

SESSION_COOKIE_SECURE = env_bool(
    "DJANGO_SESSION_COOKIE_SECURE",
    default=not DEBUG,
)

CSRF_COOKIE_SECURE = env_bool(
    "DJANGO_CSRF_COOKIE_SECURE",
    default=not DEBUG,
)

SESSION_COOKIE_HTTPONLY = True

SESSION_COOKIE_SAMESITE = "Lax"

CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True

X_FRAME_OPTIONS = "DENY"

SECURE_REFERRER_POLICY = "same-origin"


# Keep HSTS disabled until the Cloud Run deployment and custom domain are
# confirmed working correctly.
SECURE_HSTS_SECONDS = env_int(
    "DJANGO_SECURE_HSTS_SECONDS",
    default=0,
)

SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool(
    "DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS",
    default=False,
)

SECURE_HSTS_PRELOAD = env_bool(
    "DJANGO_SECURE_HSTS_PRELOAD",
    default=False,
)


# =============================================================================
# APPLICATIONS
# =============================================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    "rest_framework",

    "apps.core",
    "apps.legal_guidance",
    "apps.matching",
]


# =============================================================================
# MIDDLEWARE
# =============================================================================

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",

    # Serves collected static files from the Cloud Run container.
    "whitenoise.middleware.WhiteNoiseMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# =============================================================================
# URL AND WSGI CONFIGURATION
# =============================================================================

ROOT_URLCONF = "config.urls"

WSGI_APPLICATION = "config.wsgi.application"


# =============================================================================
# TEMPLATES
# =============================================================================

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]


# =============================================================================
# DATABASE
# =============================================================================

DB_ENGINE = os.getenv(
    "DB_ENGINE",
    "sqlite",
).strip().lower()

if DB_ENGINE == "mysql":
    required_database_variables = [
        "DB_HOST",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
    ]

    missing_database_variables = [
        variable
        for variable in required_database_variables
        if not os.getenv(variable, "").strip()
    ]

    if missing_database_variables:
        raise RuntimeError(
            "Missing required MySQL environment variables: "
            + ", ".join(missing_database_variables)
        )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.mysql",
            "NAME": os.getenv(
                "DB_NAME",
                "",
            ).strip(),
            "USER": os.getenv(
                "DB_USER",
                "",
            ).strip(),
            "PASSWORD": os.getenv(
                "DB_PASSWORD",
                "",
            ),
            "HOST": os.getenv(
                "DB_HOST",
                "",
            ).strip(),
            "PORT": os.getenv(
                "DB_PORT",
                "3306",
            ).strip(),
            "CONN_MAX_AGE": env_int(
                "DB_CONN_MAX_AGE",
                default=60,
            ),
            "CONN_HEALTH_CHECKS": True,
            "OPTIONS": {
                "charset": "utf8mb4",
                "connect_timeout": env_int(
                    "DB_CONNECT_TIMEOUT",
                    default=15,
                ),
                "init_command": (
                    "SET sql_mode="
                    "'STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,"
                    "NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,"
                    "NO_ENGINE_SUBSTITUTION'"
                ),
            },
        },
    }

else:
    SQLITE_DATABASE_PATH = Path(
        os.getenv(
            "SQLITE_DATABASE_PATH",
            str(BASE_DIR / "db.sqlite3"),
        )
    )

    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": SQLITE_DATABASE_PATH,
            "OPTIONS": {
                "timeout": 20,
            },
        },
    }

# =============================================================================
# AUTHENTICATION AND PASSWORD VALIDATION
# =============================================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# =============================================================================
# INTERNATIONALIZATION
# =============================================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "Asia/Manila"

USE_I18N = True

USE_TZ = True


# =============================================================================
# STATIC AND MEDIA FILES
# =============================================================================

STATIC_URL = "/static/"

STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage."
            "CompressedManifestStaticFilesStorage"
        ),
    },
}

MEDIA_URL = "/media/"

MEDIA_ROOT = BASE_DIR / "media"


# =============================================================================
# DEFAULT PRIMARY KEY
# =============================================================================

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# =============================================================================
# DJANGO REST FRAMEWORK
# =============================================================================

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.AllowAny",
    ],
}


# =============================================================================
# LARAVEL-TO-DJANGO INTERNAL AUTHENTICATION
# =============================================================================

# This is the primary setting used by LegalGuidanceAskView.
#
# Laravel must send:
#
# X-Legal-Guidance-Key: your-secret-key
#
# The fallback names are retained temporarily for compatibility with your
# previous configuration.
LEGAL_GUIDANCE_INTERNAL_API_KEY = (
    os.getenv("LEGAL_GUIDANCE_INTERNAL_API_KEY")
    or os.getenv("DJANGO_AI_SERVICE_API_KEY")
    or os.getenv("LARAVEL_API_KEY")
    or ""
).strip()


if not LEGAL_GUIDANCE_INTERNAL_API_KEY and not DEBUG:
    raise RuntimeError(
        "LEGAL_GUIDANCE_INTERNAL_API_KEY is required in production."
    )


# Backward-compatible aliases.
DJANGO_AI_SERVICE_API_KEY = LEGAL_GUIDANCE_INTERNAL_API_KEY

LARAVEL_API_KEY = LEGAL_GUIDANCE_INTERNAL_API_KEY


# =============================================================================
# OPENAI
# =============================================================================

OPENAI_API_KEY = os.getenv(
    "OPENAI_API_KEY",
    "",
).strip()

OPENAI_CHAT_MODEL = os.getenv(
    "OPENAI_CHAT_MODEL",
    "gpt-4.1-mini",
).strip()

OPENAI_EMBEDDING_MODEL = os.getenv(
    "OPENAI_EMBEDDING_MODEL",
    "text-embedding-3-small",
).strip()


if not OPENAI_API_KEY and not DEBUG:
    raise RuntimeError(
        "OPENAI_API_KEY is required in production."
    )


# =============================================================================
# TAVILY WEB SEARCH
# =============================================================================

TAVILY_API_KEY = os.getenv(
    "TAVILY_API_KEY",
    "",
).strip()

TAVILY_ENABLED = env_bool(
    "TAVILY_ENABLED",
    default=bool(TAVILY_API_KEY),
)


# =============================================================================
# LEGAL DOCUMENTS AND VECTOR STORE
# =============================================================================

LEGAL_DOCUMENTS_DIR = Path(
    os.getenv(
        "LEGAL_DOCUMENTS_DIR",
        str(BASE_DIR / "legal_documents"),
    )
)

LEGAL_VECTOR_STORE_DIR = Path(
    os.getenv(
        "LEGAL_VECTOR_STORE_DIR",
        str(BASE_DIR / "knowledge_base" / "vector_store"),
    )
)


# =============================================================================
# LEGACY SETTINGS
# =============================================================================
#
# These settings are retained only in case another part of the project still
# imports them. The current legal-guidance implementation uses OpenAI and the
# JSON vector store instead of Ollama and ChromaDB.
#
# You may remove these after confirming no Python file references them.

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL",
    "http://localhost:11434",
)

OLLAMA_CHAT_MODEL = os.getenv(
    "OLLAMA_CHAT_MODEL",
    "gemma3:4b",
)

OLLAMA_EMBEDDING_MODEL = os.getenv(
    "OLLAMA_EMBEDDING_MODEL",
    "nomic-embed-text",
)

CHROMA_DB_DIR = os.getenv(
    "CHROMA_DB_DIR",
    str(BASE_DIR / "chroma_db"),
)

LEGAL_RAG_COLLECTION = os.getenv(
    "LEGAL_RAG_COLLECTION",
    "amoracare_legal_documents",
)


# =============================================================================
# LOGGING
# =============================================================================

LOG_LEVEL = os.getenv(
    "DJANGO_LOG_LEVEL",
    "INFO",
).upper()

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {
            "format": (
                "%(asctime)s %(levelname)s "
                "%(name)s %(message)s"
            ),
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "standard",
        },
    },
    "root": {
        "handlers": [
            "console",
        ],
        "level": LOG_LEVEL,
    },
    "loggers": {
        "django": {
            "handlers": [
                "console",
            ],
            "level": LOG_LEVEL,
            "propagate": False,
        },
        "apps": {
            "handlers": [
                "console",
            ],
            "level": LOG_LEVEL,
            "propagate": False,
        },
    },
}