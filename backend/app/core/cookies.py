"""Session cookie and CSRF handling.

Why cookies rather than a token in ``localStorage``
---------------------------------------------------
The access token is delivered as an ``HttpOnly`` cookie, so page JavaScript
cannot read it. That closes the most common way a token is stolen: an XSS
payload calling ``localStorage.getItem('token')``. A token in ``localStorage``
would be readable by any script on the origin.

The cost of cookies is that the browser attaches them automatically, which is
what CSRF exploits. That is answered with the **double-submit** pattern:

1. the session token goes in an ``HttpOnly`` cookie (never script-readable);
2. a separate, script-readable CSRF cookie is issued alongside it;
3. every state-changing request must echo that value in the ``X-CSRF-Token``
   header;
4. the server compares the header against the cookie in constant time.

An attacker on another origin can cause the browser to *send* the cookies, but
cannot *read* them, so it cannot populate the header - which is exactly the
property CSRF protection needs. This is required rather than optional because
the production configuration uses ``SameSite=none``, and ``SameSite=none``
deliberately provides no CSRF protection of its own.

For ``SameSite=lax``/``strict`` deployments the same double-submit check is
still enforced, so a single cookie policy behaves identically in every
environment.
"""

from __future__ import annotations

import hmac
import secrets
from dataclasses import dataclass

from fastapi import Response

from app.core.config import Settings, get_settings

#: Request header carrying the CSRF token for state-changing requests.
CSRF_HEADER_NAME = "X-CSRF-Token"

#: Methods that do not change state and therefore need no CSRF token.
SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

#: Bytes of entropy in a CSRF token. CSRF tokens are compared, not brute
#: forced, so 32 bytes is ample and cheap.
CSRF_TOKEN_BYTES = 32

#: Session cookie path. Scoped to the API prefix so the browser does not send
#: it to unrelated static assets.
DEFAULT_COOKIE_PATH = "/api"


def generate_csrf_token() -> str:
    """Return a fresh, URL-safe CSRF token."""
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def csrf_tokens_match(cookie_value: str | None, header_value: str | None) -> bool:
    """Constant-time comparison of the CSRF cookie against the header."""
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)


def cookie_path(settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    prefix = settings.api_prefix or ""
    return f"{prefix}/v1" if prefix else "/api/v1"


@dataclass(frozen=True, slots=True)
class SessionCookie:
    """The pair of cookies that make up a browser session."""

    session_token: str
    csrf_token: str


def set_session_cookies(
    response: Response,
    *,
    session_token: str,
    csrf_token: str,
    max_age: int,
    settings: Settings | None = None,
) -> None:
    """Write the session and CSRF cookies.

    Both carry ``max_age`` so they expire with the token, and both use the
    configured ``COOKIE_SECURE`` / ``COOKIE_SAMESITE`` / ``COOKIE_DOMAIN``.
    """
    settings = settings or get_settings()
    path = cookie_path(settings)

    response.set_cookie(
        key=settings.cookie_name,
        value=session_token,
        max_age=max_age,
        path=path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    # Deliberately readable by script: the SPA must copy it into the header.
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        max_age=max_age,
        path=path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=False,
        samesite=settings.cookie_samesite,
    )


def clear_session_cookies(response: Response, *, settings: Settings | None = None) -> None:
    """Delete both cookies. The attributes must match the ones used to set them."""
    settings = settings or get_settings()
    path = cookie_path(settings)

    response.delete_cookie(
        key=settings.cookie_name,
        path=path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=True,
        samesite=settings.cookie_samesite,
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path=path,
        domain=settings.cookie_domain,
        secure=settings.cookie_secure,
        httponly=False,
        samesite=settings.cookie_samesite,
    )
