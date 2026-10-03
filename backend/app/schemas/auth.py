"""Authentication request/response schemas.

Two boundaries are deliberate:

* :class:`AdminProfile` is the *only* admin representation that reaches a
  client. It has no ``password_hash``, no reset-token digest and no JWT
  material, so adding a field to :class:`~app.models.admin.AdminDocument` can
  never leak by accident.
* :class:`LoginRequest` / :class:`ResetPasswordRequest` accept a
  ``SecretStr`` password. That keeps it out of ``repr()``, so it cannot appear
  in a traceback, a validation dump or an accidental log line.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, SecretStr, field_validator

from app.core.passwords import validate_password_strength
from app.models.base import PyObjectId


class AdminProfile(BaseModel):
    """Safe projection of the authenticated admin."""

    model_config = ConfigDict(from_attributes=True)

    id: PyObjectId
    email: EmailStr
    name: str
    is_active: bool
    last_login_at: datetime | None = None


class LoginRequest(BaseModel):
    """Credentials for ``POST /api/v1/auth/login``."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr
    password: SecretStr

    def plain_password(self) -> str:
        """Unwrap the password for hashing.

        The only place the plaintext exists is inside a function call that
        immediately feeds Argon2; it is never assigned to a module-level or
        logged value.
        """
        return self.password.get_secret_value()


class LoginResponse(BaseModel):
    """Successful login result.

    Carries no token: the token is delivered in an ``HttpOnly`` cookie, so it
    is unreachable from JavaScript. ``csrf_token`` is returned once, in the
    body, so the SPA does not have to read the cookie before its first
    state-changing call; the CSRF cookie is set at the same time.
    """

    admin: AdminProfile
    expires_at: datetime
    csrf_token: str


class ForgotPasswordRequest(BaseModel):
    """Input for the account-recovery request."""

    model_config = ConfigDict(extra="ignore")

    email: EmailStr


class ForgotPasswordResponse(BaseModel):
    """Deliberately identical for known and unknown addresses."""

    message: str = "If the account exists, a password reset email has been sent."


class ResetPasswordRequest(BaseModel):
    """Input for ``POST /api/v1/auth/reset-password``."""

    model_config = ConfigDict(extra="ignore")

    token: SecretStr
    new_password: SecretStr

    def plain_token(self) -> str:
        return self.token.get_secret_value()

    def plain_new_password(self) -> str:
        return self.new_password.get_secret_value()

    @field_validator("new_password")
    @classmethod
    def _check_strength(cls, value: SecretStr) -> SecretStr:
        validate_password_strength(value.get_secret_value())
        return value


class ResetPasswordResponse(BaseModel):
    """Generic acknowledgement for a consumed reset token."""

    message: str = "Your password has been reset. You can now sign in."


class LogoutResponse(BaseModel):
    message: str = "Signed out."
