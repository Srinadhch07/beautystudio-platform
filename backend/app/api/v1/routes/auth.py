"""Authentication endpoints.

Route-level security notes
--------------------------
* ``/login`` and ``/forgot-password`` are unauthenticated by necessity. Both are
  rate-limited, and ``/forgot-password`` answers identically for known and
  unknown addresses so it cannot be used to discover registered accounts.
* ``/me`` and ``/logout`` require a session. ``/logout`` is state-changing, so
  the CSRF double-submit check inside :func:`get_current_admin` applies to it.
* ``/reset-password`` is authorised by possession of the emailed token rather
  than by a session - which is the whole point, since the requester has lost
  their old password. It is therefore exempt from the session CSRF check, and is
  protected instead by the token's 256 bits of entropy and its short lifetime.
* The access token is never returned in a body; it is set as an ``HttpOnly``
  cookie. See :mod:`app.core.cookies` for why that is the safer transport.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response, status

from app.api.deps import SettingsDependency
from app.api.deps_auth import AuthServiceDependency, CurrentAdmin
from app.core.cookies import (
    clear_session_cookies,
    generate_csrf_token,
    set_session_cookies,
)
from app.core.rate_limit import (
    RateLimitVerdict,
    email_rate_key,
    get_login_rate_limiter,
    ip_rate_key,
)
from app.core.security import create_access_token
from app.models.admin import normalise_email
from app.schemas.auth import (
    AdminProfile,
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
)
from app.services.auth import RateLimitedError, to_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def client_ip(request: Request) -> str:
    """Best-effort client address for rate limiting.

    Only the socket peer is trusted. ``X-Forwarded-For`` is deliberately
    **ignored**: it is attacker-controlled unless a reverse proxy overwrites it,
    and honouring it would let anyone bypass the per-IP limit with a random
    header. A proxied deployment should pass the real address through a trusted
    mechanism and return it here.
    """
    return request.client.host if request.client else "unknown"


def _rate_keys(request: Request, email: str) -> tuple[str, str]:
    # normalise_email, so the limiter key and the stored/looked-up address are
    # folded identically. Using a different rule here would let casing variants
    # of one address dodge the per-address counter.
    return ip_rate_key(client_ip(request)), email_rate_key(normalise_email(email))


def _enforce_rate_limit(verdict: RateLimitVerdict) -> None:
    """Refuse the request when the window is exhausted.

    ``Retry-After`` is carried by the raised error rather than written to the
    route's ``Response``: the exception handler builds a new response, so a
    header set here would never reach the client.
    """
    if not verdict.allowed:
        raise RateLimitedError(retry_after=verdict.retry_after)


def _max_age_seconds(expires_at: datetime) -> int:
    """Cookie lifetime matching the token lifetime, so they expire together."""
    remaining = (expires_at - datetime.now(UTC)).total_seconds()
    return max(0, int(remaining))


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Sign in and receive session cookies",
    responses={
        401: {"description": "Incorrect email or password."},
        429: {"description": "Too many attempts."},
    },
)
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> LoginResponse:
    """Verify credentials and issue the session and CSRF cookies.

    The body returns the admin profile and the CSRF token, but never the access
    token, which stays inside the ``HttpOnly`` cookie.
    """
    keys = _rate_keys(request, payload.email)

    # Checked before any Argon2 work, so a blocked client costs nothing.
    _enforce_rate_limit(get_login_rate_limiter(settings).check(*keys))

    admin = await service.authenticate(payload.email, payload.plain_password(), client_ip(request))

    access = create_access_token(str(admin.id), settings=settings)
    csrf_token = generate_csrf_token()
    set_session_cookies(
        response,
        session_token=access.token,
        csrf_token=csrf_token,
        max_age=_max_age_seconds(access.expires_at),
        settings=settings,
    )
    return LoginResponse(
        admin=to_profile(admin),
        expires_at=access.expires_at,
        csrf_token=csrf_token,
    )


@router.get(
    "/me",
    response_model=AdminProfile,
    summary="Return the signed-in admin",
    responses={401: {"description": "Not signed in."}},
)
async def me(admin: CurrentAdmin) -> AdminProfile:
    """Echo the authenticated admin.

    ``AdminProfile`` is a hand-written projection, so this cannot return the
    password hash or reset-token material even as the document gains fields.
    """
    return to_profile(admin)


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Clear the session cookies",
    responses={401: {"description": "Not signed in."}},
)
async def logout(
    response: Response,
    _admin: CurrentAdmin,
    settings: SettingsDependency,
) -> LogoutResponse:
    """Clear both cookies.

    Honest scope: this ends the session **in this browser only**. The access
    token is stateless, so a copy captured beforehand remains valid until it
    expires. See the limitation section in ``README.md``.
    """
    clear_session_cookies(response, settings=settings)
    return LogoutResponse()


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Request a password reset email",
    responses={429: {"description": "Too many requests."}},
)
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    service: AuthServiceDependency,
    settings: SettingsDependency,
) -> ForgotPasswordResponse:
    """Always answer with the same 202 and the same body.

    Unknown address, disabled account, SMTP unconfigured and delivery failure all
    look identical to the client. Any variation would be an account-existence
    oracle, so delivery problems are logged server-side and swallowed here.
    """
    limiter = get_login_rate_limiter(settings)
    keys = _rate_keys(request, payload.email)

    # Checked first, so a throttled client triggers neither a database lookup nor
    # a mail. The counter has to be *recorded* as well, otherwise the window can
    # never fill and this endpoint would not actually be rate limited at all.
    _enforce_rate_limit(limiter.check(*keys))
    await service.request_password_reset(payload.email)
    # Every request is one attempt, whatever the outcome. That is what caps how
    # many reset mails a single client can trigger for one address.
    limiter.record_failure(*keys)
    return ForgotPasswordResponse()


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Set a new password using an emailed token",
    responses={400: {"description": "The reset link is invalid or has expired."}},
)
async def reset_password(
    payload: ResetPasswordRequest,
    service: AuthServiceDependency,
) -> ResetPasswordResponse:
    """Consume a single-use reset token.

    Unknown, malformed, expired and already-used tokens all produce the same 400
    with the same message. A rejected *weak password* is still reported
    precisely - that feedback is needed by the requester and reveals nothing
    about the account.
    """
    await service.reset_password(payload.plain_token(), payload.plain_new_password())
    return ResetPasswordResponse()
