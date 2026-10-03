"""Administrator account document.

Security notes
--------------
* ``password_hash`` holds an Argon2id digest produced by
  :mod:`app.core.passwords`. A plaintext password is never stored, logged or
  returned by any API.
* The model deliberately has **no** field that would leak a usable credential
  through a careless ``model_dump()``: the response schema for admins
  (:class:`app.schemas.auth.AdminProfile`) does not include ``password_hash`` or
  the reset-token material.
* ``password_reset_token_hash`` stores a SHA-256 digest, never the raw token.
  The raw value exists only in the emailed link.
"""

from __future__ import annotations

from pydantic import EmailStr, Field, field_validator

from app.models.base import BaseDocument, UtcDateTime

#: Argon2id encoded digests are ASCII and fit comfortably in this budget.
MAX_PASSWORD_HASH_LENGTH = 255

#: ``secrets.token_urlsafe`` output length; the digest is always 64 hex chars.
PASSWORD_RESET_HASH_LENGTH = 64


def normalise_email(email: str) -> str:
    """Canonicalise an address for lookup and storage.

    ``EmailStr`` has already validated the syntax, so this only strips
    surrounding whitespace and lower-cases the whole address.

    The domain part is case-insensitive by specification (RFC 5321), but the
    local part technically is not. Folding it anyway is a deliberate trade: in
    practice no mainstream provider treats the local part as case-sensitive,
    and lower-casing is what stops ``Admin@example.com`` and
    ``admin@example.com`` from becoming two accounts that each satisfy the
    unique index - a real support and security problem.

    The consequence is that two addresses differing only in local-part case
    *cannot* be distinct accounts here. That is intentional, not a bug.
    """
    return email.strip().lower()


class AdminDocument(BaseDocument):
    """A privileged user account."""

    email: EmailStr
    #: Display name shown in the admin UI. Not a credential.
    name: str = Field(min_length=1, max_length=120)
    #: Argon2id digest. ``None`` only for a not-yet-provisioned placeholder row,
    #: which :func:`app.services.auth.AdminService.authenticate` treats as
    #: "no valid credential" rather than as a match.
    password_hash: str | None = Field(default=None, max_length=MAX_PASSWORD_HASH_LENGTH)
    is_active: bool = True
    last_login_at: UtcDateTime | None = None

    # -- Password reset state ----------------------------------------------
    #: SHA-256 of the reset token. Cleared on successful use, which is what
    #: makes the token single-use.
    password_reset_token_hash: str | None = Field(
        default=None, max_length=PASSWORD_RESET_HASH_LENGTH
    )
    password_reset_expires_at: UtcDateTime | None = None

    @field_validator("email", mode="before")
    @classmethod
    def _normalise_email(cls, value: str) -> str:
        return normalise_email(value) if isinstance(value, str) else value

    @property
    def has_usable_password(self) -> bool:
        return bool(self.password_hash)
