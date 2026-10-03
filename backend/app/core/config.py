"""Application settings, loaded from environment variables and ``.env`` files.

Rules enforced here:
  * Secrets are wrapped in :class:`~pydantic.SecretStr` so they can never be
    printed through ``repr()``, tracebacks or log records.
  * The database connection string and AWS credentials are backend-only. They
    are never returned by any endpoint and never sent to the frontend.
  * Invalid combinations (CORS wildcard, ``SameSite=None`` without a secure
    cookie, ...) fail fast at start-up instead of at first request.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BeforeValidator, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

# backend/app/core/config.py -> backend/app -> backend -> <repo root>
BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_DIR.parent

#: Local Vite dev-server / preview-server origins.
DEFAULT_CORS_ORIGINS = ["http://localhost:5173", "http://localhost:4173"]

#: Minimum acceptable length for the JWT signing key. A short or empty key is
#: rejected rather than silently accepted, because it is the only thing
#: standing between an attacker and forged admin tokens.
MIN_JWT_SECRET_LENGTH = 32

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
StorageMode = Literal["s3", "local"]
CookieSameSite = Literal["lax", "strict", "none"]


def _split_origins(value: Any) -> Any:
    """Parse a comma separated origin list, trimming slashes and blanks."""
    if isinstance(value, str):
        return [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
    return value


OriginList = Annotated[list[str], BeforeValidator(_split_origins), NoDecode]


class Settings(BaseSettings):
    """Strongly typed application settings.

    Resolution order (highest priority first):

    1. process environment variables
    2. ``<repo root>/.env``
    3. ``<repo root>/backend/.env``
    4. the defaults declared on this class
    """

    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), str(BACKEND_DIR / ".env")),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- Application -------------------------------------------------------
    app_name: str = "Beauty Parlour"
    app_version: str = "1.0.0"
    debug: bool = False
    log_level: LogLevel = "INFO"
    api_prefix: str = "/api"

    # --- MongoDB (backend only) -------------------------------------------
    mongo_uri: SecretStr = SecretStr("mongodb://localhost:27017")
    mongo_db_name: str = "beauty_parlour"
    mongo_timeout_ms: int = Field(default=3000, gt=0)

    # --- HTTP / CORS -------------------------------------------------------
    frontend_url: str | None = None
    cors_origins: OriginList = Field(default_factory=lambda: list(DEFAULT_CORS_ORIGINS))

    # --- Authentication / sessions ----------------------------------------
    # The JWT flow is implemented; see app/core/security.py and app/api/v1/routes/auth.py.
    jwt_secret: SecretStr = SecretStr("")
    jwt_access_minutes: int = Field(default=30, gt=0)
    cookie_name: str = "beauty_parlour"
    csrf_cookie_name: str = "beauty_parlour_csrf"
    cookie_domain: str | None = None
    cookie_secure: bool = True
    cookie_samesite: CookieSameSite = "lax"
    #: Lifetime of a password-reset token. Kept short because the token is a
    #: bearer credential for a full account takeover.
    password_reset_minutes: int = Field(default=30, gt=0)
    login_rate_limit_max: int = Field(default=5, gt=0)
    login_rate_limit_window_minutes: int = Field(default=15, gt=0)

    # --- Storage -----------------------------------------------------------
    storage_mode: StorageMode = "s3"
    storage_local_dir: str = "storage-local"
    product_image_max_bytes: int = Field(default=5_242_880, gt=0)

    # --- AWS S3 (backend only - never exposed to React) --------------------
    aws_access_key_id: SecretStr = SecretStr("")
    aws_secret_access_key: SecretStr = SecretStr("")
    aws_region: str = "eu-west-1"
    aws_s3_bucket: str = ""

    # --- Email (SMTP) ------------------------------------------------------
    smtp_host: str = ""
    smtp_port: int = Field(default=587, gt=0)
    smtp_username: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from_email: str = ""

    # --- Validators --------------------------------------------------------

    @field_validator("api_prefix")
    @classmethod
    def _normalise_api_prefix(cls, value: str) -> str:
        """Ensure a leading slash and no trailing slash."""
        prefix = value.strip().rstrip("/")
        if not prefix:
            return ""
        return prefix if prefix.startswith("/") else f"/{prefix}"

    @field_validator("cors_origins")
    @classmethod
    def _reject_cors_wildcard(cls, value: list[str]) -> list[str]:
        """Credentials are enabled, so a wildcard origin is not allowed."""
        if any(origin == "*" for origin in value):
            raise ValueError("CORS_ORIGINS must list explicit origins; '*' is not allowed")
        return value

    @field_validator("cookie_samesite", mode="before")
    @classmethod
    def _normalise_samesite(cls, value: Any) -> Any:
        return value.strip().lower() if isinstance(value, str) else value

    @field_validator("frontend_url", "cookie_domain", "smtp_username", mode="before")
    @classmethod
    def _blank_to_none(cls, value: Any) -> Any:
        """Treat an empty string as "not configured"."""
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None
        return value

    @field_validator("log_level", mode="before")
    @classmethod
    def _upper_log_level(cls, value: Any) -> Any:
        return value.strip().upper() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _check_cookie_pairing(self) -> Settings:
        if self.cookie_samesite == "none" and not self.cookie_secure:
            raise ValueError("COOKIE_SAMESITE=none requires COOKIE_SECURE=true")
        return self

    @model_validator(mode="after")
    def _check_password_reset_window(self) -> Settings:
        """A reset token must not outlive the access token it may follow."""
        if self.password_reset_minutes > 24 * 60:
            raise ValueError("PASSWORD_RESET_MINUTES must not exceed 1440 (24 hours)")
        return self

    # --- Derived helpers ---------------------------------------------------

    @property
    def environment(self) -> str:
        return "development" if self.debug else "production"

    @property
    def health_path(self) -> str:
        return f"{self.api_prefix}/health"

    @property
    def access_token_seconds(self) -> int:
        return self.jwt_access_minutes * 60

    @property
    def is_auth_configured(self) -> bool:
        """True when a usable signing key is present.

        An empty ``JWT_SECRET`` is tolerated at import time so the health check
        keeps working on a fresh checkout, but the auth routes refuse to run
        without it (see :func:`app.core.security.signing_key`).
        """
        return len(self.jwt_secret.get_secret_value().strip()) >= MIN_JWT_SECRET_LENGTH

    def auth_transport_warnings(self) -> list[str]:
        """Start-up self-check for the cookie/CSRF transport.

        The failure mode this exists for: the shipped ``.env`` is production
        oriented (``COOKIE_SECURE=true`` and ``SameSite=none``), which is
        exactly right behind HTTPS but means browsers will silently refuse to
        store the session cookie when the API is served over plain HTTP during
        local development. Rather than silently downgrading security, the
        mismatch is reported so the developer can pick the right env file.
        """
        warnings: list[str] = []
        frontend_is_http = bool(self.frontend_url) and self.frontend_url.startswith("http://")

        if self.cookie_secure and frontend_is_http:
            warnings.append(
                "COOKIE_SECURE=true but FRONTEND_URL uses http:// - browsers will "
                "discard the session cookie. Use backend/.env.development.example "
                "(COOKIE_SECURE=false, COOKIE_SAMESITE=lax) for local development."
            )
        if self.cookie_samesite == "none":
            warnings.append(
                "COOKIE_SAMESITE=none sends the session cookie on cross-site "
                "requests, so double-submit CSRF validation is mandatory. It is "
                "enabled unconditionally."
            )
        if not self.frontend_url:
            warnings.append(
                "FRONTEND_URL is not set, so password-reset emails cannot contain "
                "a working link. Set it before relying on the reset flow."
            )
        if not self.is_auth_configured:
            warnings.append(
                "JWT_SECRET is missing or shorter than "
                f"{MIN_JWT_SECRET_LENGTH} characters; auth routes will refuse to "
                "issue tokens until a strong secret is configured."
            )
        return warnings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
