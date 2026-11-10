import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_env_file(path):
    """Load KEY=VALUE lines from backend/.env. Real environment variables win."""

    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("'\""))


_load_env_file(BASE_DIR / ".env")

# Values copied from .env into a hosting dashboard often keep their quotes
# ("postgresql://..."), which dashboards store literally. Strip one matching pair.
for _key, _value in list(os.environ.items()):
    _trimmed = _value.strip()
    if len(_trimmed) >= 2 and _trimmed[0] == _trimmed[-1] and _trimmed[0] in "'\"":
        os.environ[_key] = _trimmed[1:-1].strip()

DEBUG = os.getenv("DJANGO_DEBUG", "1") == "1"
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("DJANGO_SECRET_KEY must be set when DJANGO_DEBUG=0.")
    # Signs JWTs too, so keep it >= 32 bytes even in development.
    SECRET_KEY = "dev-only-insecure-secret-key-change-me-0123456789"
ALLOWED_HOSTS = [host for host in os.getenv("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if host]

INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "accounts",
    "posts",
    "media_api",
    "stories",
    "notifications",
    "messaging",
    "discovery",
    "safety",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    # Serves /static/ (Django admin assets) from the app itself in production.
    "whitenoise.middleware.WhiteNoiseMiddleware",
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
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

def _database_from_url(url):
    """postgresql://user:pass@host:port/db?sslmode=require -> Django config.

    Cloud Postgres (Neon, Supabase, Render, RDS) hands out a single URL.
    Query parameters (sslmode, channel_binding, ...) pass straight to psycopg.
    """

    parts = urlparse(url)
    if parts.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must start with postgresql://")
    options = {key: values[-1] for key, values in parse_qs(parts.query).items()}
    host = parts.hostname or ""
    if host not in {"localhost", "127.0.0.1", ""}:
        options.setdefault("sslmode", "require")  # never talk to a cloud DB in plaintext
    config = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": unquote(parts.path.lstrip("/")),
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": host,
        "PORT": str(parts.port or 5432),
        "OPTIONS": options,
        # Reuse connections instead of a new TLS handshake per request.
        "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
        "CONN_HEALTH_CHECKS": True,
    }
    if "-pooler" in host or os.getenv("DB_POOLED") == "1":
        # PgBouncer in transaction mode can't keep server-side cursors open.
        config["DISABLE_SERVER_SIDE_CURSORS"] = True
    if os.getenv("DB_POOL", "1") == "1" and os.getenv("DB_DIRECT") != "1":
        # Under ASGI (daphne) every request runs on a fresh thread, so
        # CONN_MAX_AGE never reuses anything and each request paid a full
        # TCP + TLS + auth handshake to Neon (~2s on Render). An in-process
        # psycopg pool keeps connections warm across threads instead.
        # Django itself passes check=ConnectionPool.check_connection, so each
        # connection is verified before use (Neon drops idle ones on suspend).
        config["CONN_MAX_AGE"] = 0  # required by Django when pooling
        config["CONN_HEALTH_CHECKS"] = False
        config["OPTIONS"]["pool"] = {
            "min_size": int(os.getenv("DB_POOL_MIN", "2")),
            "max_size": int(os.getenv("DB_POOL_MAX", "10")),
            "timeout": 10,
            "max_idle": 240,  # recycle idle connections before Neon closes them
        }
    return config


# Neon gives two URLs: DATABASE_URL (pooled, for the running app) and
# DATABASE_URL_UNPOOLED (direct). Run migrations, tests and data loads with
# DB_DIRECT=1 so they bypass the pooler.
_database_url = (
    os.getenv("DATABASE_URL_UNPOOLED") if os.getenv("DB_DIRECT") == "1" else None
) or os.getenv("DATABASE_URL")
if _database_url:
    DATABASES = {"default": _database_from_url(_database_url)}
elif os.getenv("POSTGRES_DB"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.getenv("POSTGRES_DB"),
            "USER": os.getenv("POSTGRES_USER", "infogram"),
            "PASSWORD": os.getenv("POSTGRES_PASSWORD", "infogram"),
            "HOST": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "PORT": os.getenv("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE_DIR / "db.sqlite3"}}

AUTH_USER_MODEL = "accounts.User"
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
        if not DEBUG
        else "django.contrib.staticfiles.storage.StaticFilesStorage"
    },
}
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ("rest_framework_simplejwt.authentication.JWTAuthentication",),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    # Leaky-bucket style per-user / per-IP limits (see Backend_API.md §3).
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.ScopedRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.getenv("THROTTLE_ANON", "60/min"),
        "user": os.getenv("THROTTLE_USER", "600/min"),
        "auth": os.getenv("THROTTLE_AUTH", "20/min"),
        "reports": os.getenv("THROTTLE_REPORTS", "30/hour"),
    },
}

# Short-lived access token + long-lived rotating refresh token. The frontend
# refreshes automatically on 401, and rotated refresh tokens are blacklisted.
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "14"))),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
}

CORS_ALLOWED_ORIGINS = [
    origin
    for origin in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(",")
    if origin
]
REDIS_URL = os.getenv("REDIS_URL", "")
if REDIS_URL:
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    # In-memory groups keep local development and single-process tests usable
    # without requiring Redis. Production should set REDIS_URL explicitly.
    CHANNEL_LAYERS = {"default": {"BACKEND": "channels.layers.InMemoryChannelLayer"}}

# Hot-path cache: ranked feed snapshots and throttle buckets. Redis in
# production (shared by all workers); per-process memory for local dev.
if REDIS_URL:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
else:
    CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}

# Email. With EMAIL_HOST set, mail goes out over SMTP; otherwise each email is
# written as a file to backend/sent_emails/ so reset links are easy to grab.
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173").rstrip("/")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "Infogram <no-reply@infogram.local>")
if os.getenv("EMAIL_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["EMAIL_HOST"]
    EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
    EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
    EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "1") == "1"
else:
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = BASE_DIR / "sent_emails"
# Reset links stop working after this many seconds (default 1 hour).
PASSWORD_RESET_TIMEOUT = int(os.getenv("PASSWORD_RESET_TIMEOUT", "3600"))

# ---- Production hardening (only when DJANGO_DEBUG=0) ----------------------
CSRF_TRUSTED_ORIGINS = [o for o in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if o]
if not DEBUG:
    # Render / most PaaS terminate TLS at a proxy and forward this header.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.getenv("SECURE_SSL_REDIRECT", "1") == "1"
    SECURE_REDIRECT_EXEMPT = [r"^healthz/?$"]  # platform health checks call over plain HTTP
    SECURE_HSTS_SECONDS = int(os.getenv("SECURE_HSTS_SECONDS", "2592000"))  # 30 days
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = "same-origin"
    X_FRAME_OPTIONS = "DENY"
    # On a shared platform domain (*.onrender.com) we don't own the parent
    # domain, so HSTS includeSubDomains / preload must stay off. Revisit with a custom domain.
    SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"plain": {"format": "%(asctime)s %(levelname)s %(name)s: %(message)s"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "plain"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
    "loggers": {"django.db.backends": {"level": "WARNING"}},
}

FEED_SNAPSHOT_TTL_SECONDS = int(os.getenv("FEED_SNAPSHOT_TTL_SECONDS", "1800"))
FEED_SNAPSHOT_MAX_ITEMS = int(os.getenv("FEED_SNAPSHOT_MAX_ITEMS", "500"))
# Media object storage (S3-compatible). Neon Object Storage writes
# AWS_ENDPOINT_URL_S3 / AWS_REGION via `neon env pull -s object-storage`;
# the AWS_S3_* names still work for AWS S3, Cloudflare R2, MinIO, etc.
# With no credentials, uploads go to the local media/ folder instead.
AWS_S3_ENDPOINT_URL = os.getenv("AWS_S3_ENDPOINT_URL") or os.getenv("AWS_ENDPOINT_URL_S3") or None
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_STORAGE_BUCKET_NAME = os.getenv("AWS_STORAGE_BUCKET_NAME", "infogram-media")
AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME") or os.getenv("AWS_REGION") or "ap-south-1"
# Custom endpoints (Neon, MinIO) need path-style URLs: endpoint/bucket/key.
AWS_S3_ADDRESSING_STYLE = os.getenv("AWS_S3_ADDRESSING_STYLE", "path" if AWS_S3_ENDPOINT_URL else "auto")
MEDIA_PUBLIC_BASE_URL = os.getenv("MEDIA_PUBLIC_BASE_URL", "")
MEDIA_UPLOAD_URL_EXPIRY_SECONDS = int(os.getenv("MEDIA_UPLOAD_URL_EXPIRY_SECONDS", "900"))
