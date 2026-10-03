"""Authentication dependencies.

:func:`get_current_admin` is the single place a session is resolved. Routes
depend on it rather than re-implementing token handling, so a mistake can be made
once instead of in twenty handlers.

Token transport is the ``HttpOnly`` session cookie. An ``Authorization: Bearer``
header is *also* accepted, for two reasons: it is the only way the Swagger UI
"Authorize" button can drive a cookie-based flow, and it lets a non-browser
client (scripts, CI) authenticate. The header is a fallback, not the primary
path.

The cookie name is read from settings at call time rather than baked into a
security scheme, so renaming ``COOKIE_NAME`` cannot desynchronise the scheme
from the code that reads it.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.api.deps import SettingsDependency, get_admins_repository
from app.core.config import Settings
from app.core.cookies import CSRF_HEADER_NAME, SAFE_METHODS, csrf_tokens_match
from app.core.errors import AppError
from app.core.parsing import parse_object_id
from app.core.security import TokenError, decode_access_token
from app.models.admin import AdminDocument
from app.repositories.admins import AdminsRepository
from app.services.auth import AuthService

logger = logging.getLogger(__name__)

#: Registered as a security scheme so /docs renders an Authorize control.
bearer_scheme = HTTPBearer(auto_error=False)


class NotAuthenticatedError(AppError):
    """No usable session was presented.

    The message never states *why* - missing, expired, badly signed or wrong
    type - because telling an attacker which part failed speeds up forgery.
    """

    status_code = 401
    code = "not_authenticated"
    message = "Authentication is required."


class CsrfError(AppError):
    """A state-changing request arrived without a matching CSRF token."""

    status_code = 403
    code = "csrf_failed"
    message = "CSRF validation failed. Reload the page and try again."


def extract_token(
    request: Request,
    settings: Settings,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    """Pull the access token from the session cookie, else the Bearer header.

    The cookie wins: it is the primary transport, and a request carrying both
    is far more likely to be a mis-set client than an attack.
    """
    cookie_value = request.cookies.get(settings.cookie_name)
    if cookie_value:
        return cookie_value
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    return None


def enforce_csrf(request: Request, settings: Settings) -> None:
    """Double-submit check for state-changing requests.

    Only applied when a session cookie is actually present. A pure
    ``Authorization: Bearer`` request is not a browser form post and cannot be
    forged cross-site, so requiring a CSRF header there would only add friction
    for scripts and CI.
    """
    if request.method.upper() in SAFE_METHODS:
        return
    if not request.cookies.get(settings.cookie_name):
        return

    cookie_token = request.cookies.get(settings.csrf_cookie_name)
    header_token = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_tokens_match(cookie_token, header_token):
        logger.warning("CSRF check failed for %s %s", request.method, request.url.path)
        raise CsrfError


async def get_current_admin(
    request: Request,
    settings: SettingsDependency,
    repository: Annotated[AdminsRepository, Depends(get_admins_repository)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)] = None,
) -> AdminDocument:
    """Resolve the authenticated, active admin.

    Order matters: validate the token, then load the account, then re-check
    ``is_active``. Deactivating an admin therefore revokes access immediately
    instead of waiting for their token to expire.
    """
    token = extract_token(request, settings, credentials)
    if not token:
        raise NotAuthenticatedError

    try:
        claims = decode_access_token(token, settings=settings)
    except TokenError as exc:
        logger.info("Rejected an access token: %s", exc)
        raise NotAuthenticatedError from exc

    try:
        admin_id = parse_object_id(claims.admin_id, field="subject")
    except AppError as exc:
        # A token whose subject is not an ObjectId is simply not a valid one.
        raise NotAuthenticatedError from exc

    admin = await repository.find_by_id(admin_id)
    if admin is None:
        # Well-formed token, but the account no longer exists.
        raise NotAuthenticatedError

    if not admin.is_active:
        logger.info("Rejected a session for the disabled account %s", admin.id)
        raise NotAuthenticatedError

    enforce_csrf(request, settings)
    return admin


CurrentAdmin = Annotated[AdminDocument, Depends(get_current_admin)]


def get_auth_service(
    repository: Annotated[AdminsRepository, Depends(get_admins_repository)],
    settings: SettingsDependency,
) -> AuthService:
    """Build the auth service for the request."""
    return AuthService(repository, settings)


AuthServiceDependency = Annotated[AuthService, Depends(get_auth_service)]
