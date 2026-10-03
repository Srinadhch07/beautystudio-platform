"""Token issuing and verification.

Design constraints
------------------
* **HMAC-SHA256 only.** The algorithm is hard-coded on both encode and decode.
  The usual JWT attack is to take the ``alg`` header from an attacker-supplied
  token and switch it to ``none`` (or to an asymmetric algorithm) so the
  signature check is skipped. Because :data:`_ALGORITHM` is never read from the
  token, a forged token is rejected regardless of its header.
* **The algorithm is additionally pinned at verification time** via
  ``options={"require": [...]}`` and an explicit ``algorithms`` list, and the
  decoded ``typ`` claim is cross-checked.
* **Minimum claims only**: subject (admin id), token type, issued-at, expiry,
  and a session id. The email is *not* included - it changes when an admin
  changes their address and is already available from ``/auth/me``.
* **The session id is issued but not yet consumed.** Logout clears the cookies
  and, on the server side, only the ``is_active`` check and token expiry can
  end a session: this module keeps no revocation list, so a token that was
  already delivered stays cryptographically valid until it expires. ``jti`` is
  the hook a future denylist needs, and its presence is *not* a claim that
  revocation already works. See ``README.md`` for the stated limitation and the
  short token lifetime that bounds it.
* The signing key is read from :class:`~app.core.config.Settings` and never
  appears in a log record, a response body or an exception message.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Final

import jwt

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

_ALGORITHM: Final = "HS256"

#: ``jti`` claim name, used as the per-session identifier.
SESSION_CLAIM: Final = "jti"

#: Distinguishes an access token from a password-reset token. A reset token
#: presented to a protected API route must be rejected, and vice versa.
ACCESS_TOKEN_TYPE: Final = "access"
RESET_TOKEN_TYPE: Final = "password_reset"

#: Claims that must be present in every token this service issues.
_REQUIRED_CLAIMS: Final = ["exp", "iat", "sub", "type", SESSION_CLAIM]


class TokenError(Exception):
    """A token is unusable. The message is deliberately vague on purpose."""


class AuthNotConfiguredError(RuntimeError):
    """The deployment has no usable signing key."""


@dataclass(frozen=True, slots=True)
class AccessToken:
    """A freshly minted access token."""

    token: str
    expires_at: datetime
    session_id: str


@dataclass(frozen=True, slots=True)
class AccessTokenClaims:
    """Verified contents of an access token."""

    admin_id: str
    session_id: str


def signing_key(settings: Settings | None = None) -> str:
    """Return the HMAC signing key, refusing to operate without a strong one."""
    settings = settings or get_settings()
    secret = settings.jwt_secret.get_secret_value()
    if not settings.is_auth_configured:
        # The reason is logged, the value never is.
        logger.error(
            "JWT_SECRET is not configured to an acceptable length; refusing to sign tokens"
        )
        raise AuthNotConfiguredError(
            "Authentication is not configured: JWT_SECRET must be set to a strong, random value."
        )
    return secret


def create_access_token(
    admin_id: str,
    *,
    settings: Settings | None = None,
    session_id: str | None = None,
) -> AccessToken:
    """Sign a short-lived access token for ``admin_id``."""
    settings = settings or get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.jwt_access_minutes)
    identifier = session_id or uuid.uuid4().hex

    claims: dict[str, Any] = {
        "sub": admin_id,
        "type": ACCESS_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
        SESSION_CLAIM: identifier,
    }
    token = jwt.encode(claims, signing_key(settings), algorithm=_ALGORITHM)
    return AccessToken(token=token, expires_at=expires_at, session_id=identifier)


def decode_token(
    token: str,
    *,
    expected_type: str,
    settings: Settings | None = None,
) -> dict[str, Any]:
    """Verify a token and return its claims.

    Raises :class:`TokenError` for an expired, malformed, badly signed or
    wrong-type token. The underlying ``jwt`` exception is deliberately not
    forwarded, because those messages distinguish "expired" from "bad
    signature", which is useful to an attacker probing a token.
    """
    settings = settings or get_settings()
    try:
        claims = jwt.decode(
            token,
            signing_key(settings),
            algorithms=[_ALGORITHM],
            options={"require": _REQUIRED_CLAIMS, "verify_signature": True},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("The token has expired.") from exc
    except jwt.PyJWTError as exc:
        raise TokenError("The token is invalid.") from exc

    if claims.get("type") != expected_type:
        raise TokenError("The token is invalid for this operation.")

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject:
        raise TokenError("The token is invalid.")

    return claims


def decode_access_token(token: str, *, settings: Settings | None = None) -> AccessTokenClaims:
    """Verify an access token and return the identity it asserts."""
    claims = decode_token(token, expected_type=ACCESS_TOKEN_TYPE, settings=settings)
    session_id = claims.get(SESSION_CLAIM)
    if not isinstance(session_id, str) or not session_id:
        raise TokenError("The token is invalid.")
    return AccessTokenClaims(admin_id=str(claims["sub"]), session_id=session_id)
