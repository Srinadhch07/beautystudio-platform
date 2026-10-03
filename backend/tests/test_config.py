"""Configuration and secret-handling tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.services.mail import get_smtp_settings, is_email_configured
from app.storage.s3 import is_s3_configured


def test_env_file_discovery_points_at_repo_root() -> None:
    from app.core.config import BACKEND_DIR, REPO_ROOT

    assert BACKEND_DIR.name == "backend"
    assert BACKEND_DIR.parent == REPO_ROOT


def test_cors_origins_are_parsed_from_csv() -> None:
    settings = Settings(CORS_ORIGINS="http://localhost:5173, https://example.com/")

    assert settings.cors_origins == ["http://localhost:5173", "https://example.com"]


def test_cors_wildcard_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(CORS_ORIGINS="*")


def test_api_prefix_is_normalised() -> None:
    assert Settings(API_PREFIX="api/").api_prefix == "/api"
    assert Settings(API_PREFIX="").api_prefix == ""


def test_empty_optional_strings_become_none() -> None:
    settings = Settings(COOKIE_DOMAIN="  ", FRONTEND_URL="")

    assert settings.cookie_domain is None
    assert settings.frontend_url is None


def test_samesite_none_requires_secure_cookie() -> None:
    with pytest.raises(ValidationError):
        Settings(COOKIE_SAMESITE="none", COOKIE_SECURE="false")


def test_samesite_is_case_insensitive() -> None:
    assert Settings(COOKIE_SAMESITE="LAX", COOKIE_SECURE="false").cookie_samesite == "lax"


def test_secrets_are_masked_in_repr() -> None:
    settings = Settings(
        JWT_SECRET="super-secret-jwt",
        AWS_SECRET_ACCESS_KEY="super-secret-aws",
        MONGO_URI="mongodb://user:pass@host/db",
        SMTP_PASSWORD="super-secret-smtp",
    )
    rendered = repr(settings)

    assert "super-secret-jwt" not in rendered
    assert "super-secret-aws" not in rendered
    assert "user:pass" not in rendered
    assert "super-secret-smtp" not in rendered


def test_health_path_is_derived_from_api_prefix() -> None:
    assert Settings(API_PREFIX="/api").health_path == "/api/health"


def test_environment_label_follows_debug_flag() -> None:
    assert Settings(DEBUG="true").environment == "development"
    assert Settings(DEBUG="false").environment == "production"


def test_s3_and_email_configuration_probes() -> None:
    configured = Settings(
        AWS_ACCESS_KEY_ID="id",
        AWS_SECRET_ACCESS_KEY="secret",
        AWS_S3_BUCKET="bucket",
    )
    assert is_s3_configured(configured) is True
    assert is_s3_configured(Settings(AWS_S3_BUCKET="")) is False

    without_smtp = Settings(SMTP_HOST="", SMTP_FROM_EMAIL="")
    assert is_email_configured(without_smtp) is False

    smtp = get_smtp_settings(Settings(SMTP_HOST="localhost", SMTP_FROM_EMAIL="a@b.co"))
    assert smtp.host == "localhost"
    assert smtp.use_tls is False
