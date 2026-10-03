"""Authentication business logic.

Security invariants enforced here
----------------------------------
* **No account enumeration.** :meth:`AdminService.authenticate` returns the same
  generic failure for an unknown address, a wrong password and a disabled
  account, and performs a dummy Argon2 verification for unknown accounts so the
  three cases also take comparable time.
* **Reset tokens are single-use and short-lived.** Only a SHA-256 digest is
  stored; the raw value exists solely inside the emailed link. A successful
  reset clears the digest.
* **Reset failures are indistinguishable.** A missing, expired, already-used or
  malformed token all produce the same error.
* **No secret reaches a log or a response.** Passwords, hashes and raw tokens
  are never logged, and only :class:`~app.schemas.auth.AdminProfile` is ever
  serialised to a client.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import UTC, datetime, timedelta

from bson import ObjectId

from app.core.config import Settings
from app.core.errors import (
    AppError,
    BadRequestError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.core.passwords import (
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from app.core.rate_limit import (
    RateLimitVerdict,
    email_rate_key,
    get_login_rate_limiter,
    ip_rate_key,
)
from app.models.admin import AdminDocument, normalise_email
from app.repositories.admins import AdminsRepository
from app.schemas.auth import AdminProfile
from app.services.mail import EmailService

logger = logging.getLogger(__name__)

#: Bytes of entropy in a password-reset token.
RESET_TOKEN_BYTES = 32

#: One message for every reason a credential can be rejected. Distinguishing
#: them would let an attacker confirm which addresses are registered or which
#: accounts are disabled.
GENERIC_LOGIN_FAILURE = "Incorrect email or password."

#: One message for every reason a reset can fail.
GENERIC_RESET_FAILURE = "The reset link is invalid or has expired."


def hash_reset_token(raw_token: str) -> str:
    """Return the digest stored for a raw reset token.

    SHA-256 (not Argon2) is the right tool here: the token is 256 bits of
    cryptographically random data, so there is no password-style guessing to
    slow down, and lookups must stay a single cheap index hit.
    """
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def to_profile(admin: AdminDocument) -> AdminProfile:
    """Project an admin onto the only schema a client ever sees.

    A module-level function rather than a method, so routes can build a profile
    without holding a service instance.
    """
    return AdminProfile.model_validate(admin, from_attributes=True)


class RateLimitedError(AppError):
    """Too many login attempts from this client.

    ``code`` matches the framework-level ``rate_limited`` code so clients see
    one vocabulary for 429s regardless of which layer produced it.

    The ``Retry-After`` hint rides on the exception rather than on the route's
    ``Response``: an exception handler constructs a fresh response, so a header
    set before raising would be lost.
    """

    status_code = 429
    code = "rate_limited"
    message = "Too many attempts. Please try again later."

    def __init__(self, retry_after: int | None = None) -> None:
        super().__init__(headers={"Retry-After": str(retry_after)} if retry_after else None)


class InvalidCredentialsError(AppError):
    """Login refused, for any reason."""

    status_code = 401
    code = "invalid_credentials"
    message = GENERIC_LOGIN_FAILURE


class InvalidResetTokenError(AppError):
    """A reset token was missing, malformed, expired or already used."""

    status_code = 400
    code = "invalid_reset_token"
    message = GENERIC_RESET_FAILURE


class AuthService:
    """Login, logout bookkeeping, and the password-reset flow."""

    def __init__(
        self,
        repository: AdminsRepository,
        settings: Settings,
        email_service: EmailService | None = None,
    ) -> None:
        self._repository = repository
        self._settings = settings
        self._email = email_service or EmailService(settings)

    # -- Reads --------------------------------------------------------------

    async def get_active_by_id(self, admin_id: ObjectId) -> AdminDocument | None:
        return await self._repository.find_by_id(admin_id)

    # -- Login --------------------------------------------------------------

    def check_rate_limit(self, client_ip: str, email: str) -> RateLimitVerdict:
        """Pre-flight the limiter so a blocked client costs no Argon2 work."""
        return get_login_rate_limiter(self._settings).check(
            ip_rate_key(client_ip), email_rate_key(normalise_email(email))
        )

    async def authenticate(self, email: str, password: str, client_ip: str) -> AdminDocument:
        """Verify credentials and stamp ``last_login_at``.

        Raises :class:`RateLimitedError` once the window is exhausted, and
        :class:`InvalidCredentialsError` for every other failure.
        """
        limiter = get_login_rate_limiter(self._settings)
        ip_key = ip_rate_key(client_ip)
        email_key = email_rate_key(normalise_email(email))

        verdict = limiter.check(ip_key, email_key)
        if not verdict.allowed:
            # The address is intentionally not echoed back.
            raise RateLimitedError(retry_after=verdict.retry_after)

        admin = await self._repository.find_by_email(email)

        # One code path decides success, so "unknown", "wrong password" and
        # "inactive" cannot be distinguished by the response.
        if admin is None:
            # Dummy verification keeps the timing comparable.
            verify_password(password, None)
            limiter.record_failure(ip_key, email_key)
            logger.info("Login refused for an unknown address from %s", client_ip)
            raise InvalidCredentialsError

        if not verify_password(password, admin.password_hash):
            limiter.record_failure(ip_key, email_key)
            logger.info("Login refused for a known address from %s", client_ip)
            raise InvalidCredentialsError

        if not admin.is_active:
            # Counted as a failure so probing cannot be done for free.
            limiter.record_failure(ip_key, email_key)
            logger.info("Login refused for a disabled account from %s", client_ip)
            raise InvalidCredentialsError

        limiter.reset(ip_key, email_key)

        # Transparently upgrade an old/weak digest now that we hold the password.
        if admin.password_hash and needs_rehash(admin.password_hash):
            await self._repository.set_password_hash(admin.id, hash_password(password))

        updated = await self._repository.record_login(admin.id)
        return updated or admin

    # -- Password reset -----------------------------------------------------

    def build_reset_url(self, raw_token: str) -> str:
        """Absolute reset link, built from ``FRONTEND_URL``.

        The link is a *hash* route carrying the token in the query string of the
        hash. Two things follow from how the SPA is built, and both are load
        bearing:

        * ``/#/admin/reset-password`` and not ``/admin/reset-password`` - the app
          routes on ``location.hash``, so a path-style link is either a 404 on the
          static host or, under a catch-all rewrite, silently renders the public
          home page and drops the token. A hash link works on any host with no
          rewrite rule.
        * ``reset_token`` and not ``token`` - the client reads the parameter with
          that exact name from ``location.search``.

        The raw token still appears only here, in the emailed link, and is still
        stored solely as a digest.

        Raises when ``FRONTEND_URL`` is unset so a broken link is never mailed.
        """
        frontend_url = (self._settings.frontend_url or "").rstrip("/")
        if not frontend_url:
            raise ServiceUnavailableError(
                "FRONTEND_URL is not configured, so password reset links cannot be built."
            )
        return f"{frontend_url}/#/admin/reset-password?reset_token={raw_token}"

    async def issue_reset_token(self, admin: AdminDocument) -> str:
        """Create a token, store only its digest, and return the raw value.

        The returned value is for the email link only.
        """
        raw_token = secrets.token_urlsafe(RESET_TOKEN_BYTES)
        expires_at = datetime.now(UTC) + timedelta(minutes=self._settings.password_reset_minutes)
        await self._repository.store_reset_token(admin.id, hash_reset_token(raw_token), expires_at)
        return raw_token

    async def request_password_reset(self, email: str) -> bool:
        """Handle a forgot-password request.

        Returns ``True`` when a mail was attempted, ``False`` when there was
        nothing to do. The caller must respond identically either way, which is
        what keeps this endpoint from confirming whether an account exists.

        Both delivery preconditions are checked *before* a token is stored, for
        two reasons:

        * a misconfigured deployment must never persist a token the user cannot
          receive;
        * more importantly, raising here would break the invariant this endpoint
          exists to protect. ``build_reset_url`` raises when ``FRONTEND_URL`` is
          unset, and the shipped ``.env`` leaves it empty - which would have made
          a *known* address answer 503 while an *unknown* one answered 202,
          turning "forgot password" into a way to test whether an address is
          registered.
        """
        admin = await self._repository.find_by_email(email)
        if admin is None or not admin.is_active:
            # Same amount of work as the happy path, minus the mail.
            return False

        if not self._email.is_configured:
            # Not raised to the client: the response must not vary.
            logger.error(
                "Password reset requested but SMTP is not configured; "
                "set SMTP_HOST and SMTP_FROM_EMAIL"
            )
            return False

        if not (self._settings.frontend_url or "").strip():
            logger.error(
                "Password reset requested but FRONTEND_URL is not configured; "
                "reset links cannot be built"
            )
            return False

        raw_token = await self.issue_reset_token(admin)
        reset_url = self.build_reset_url(raw_token)

        try:
            self._email.send_password_reset(
                to_email=str(admin.email),
                admin_name=admin.name,
                reset_url=reset_url,
                expires_in_minutes=self._settings.password_reset_minutes,
            )
        except Exception as exc:  # noqa: BLE001 - delivery must not change the response
            # Type only: a driver message can contain the SMTP username/host.
            logger.error("Password reset email failed (%s)", type(exc).__name__)
            return False

        # Never the token itself.
        logger.info("Password reset email sent for admin %s", admin.id)
        return True

    async def reset_password(self, raw_token: str, new_password: str) -> AdminDocument:
        """Consume a reset token and set a new password.

        Raises :class:`InvalidResetTokenError` - with one shared message - for
        a token that is unknown, expired, already used or malformed.
        """
        if not raw_token:
            raise InvalidResetTokenError

        token_hash = hash_reset_token(raw_token)
        admin = await self._repository.find_by_reset_token_hash(token_hash)
        if admin is None or not admin.password_reset_token_hash:
            raise InvalidResetTokenError

        now = datetime.now(UTC)
        expires_at = admin.password_reset_expires_at
        if expires_at is None or expires_at <= now:
            # Clear the stale digest so it cannot be retried, without touching
            # the stored password.
            await self._repository.clear_reset_token(admin.id)
            raise InvalidResetTokenError

        validate_password_strength(new_password)
        new_hash = hash_password(new_password)

        # set_password_hash also clears the digest, making the token single-use.
        updated = await self._repository.set_password_hash(admin.id, new_hash)
        if updated is None:
            raise NotFoundError("Admin not found.")

        logger.info("Password reset completed for admin %s", admin.id)
        return updated

    # -- Provisioning -------------------------------------------------------

    async def create_admin(self, *, email: str, name: str, password: str) -> AdminDocument:
        """Create an admin account, rejecting a duplicate address.

        Used by the ``create-admin`` CLI. There is deliberately no code path
        that provisions an account automatically at start-up: an initial admin
        must be created deliberately, by a human, with a password they chose.
        """
        validate_password_strength(password)
        normalised = normalise_email(email)

        if await self._repository.find_by_email(normalised) is not None:
            raise BadRequestError("An admin with that email address already exists.")

        admin = AdminDocument(
            email=normalised,
            name=name.strip(),
            password_hash=hash_password(password),
        )
        return await self._repository.create(admin)

    async def set_password(self, admin_id: ObjectId, password: str) -> AdminDocument:
        """Set a new password, clearing any outstanding reset token."""
        validate_password_strength(password)
        updated = await self._repository.set_password_hash(admin_id, hash_password(password))
        if updated is None:
            raise NotFoundError("Admin not found.")
        return updated
