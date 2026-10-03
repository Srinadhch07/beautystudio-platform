"""Admin repository.

Adds email lookup, ``last_login_at`` bookkeeping and the password-reset state
transitions on top of the shared CRUD helpers.
"""

from __future__ import annotations

from datetime import datetime

from bson import ObjectId

from app.models.admin import AdminDocument, normalise_email
from app.models.base import utcnow
from app.models.collections import ADMINS
from app.repositories.base import BaseRepository

#: Cleared on every successful password reset. Removing the digest is what makes
#: a reset token single-use: it no longer matches anything afterwards.
RESET_CLEARED_FIELDS = ("password_reset_token_hash", "password_reset_expires_at")


class AdminsRepository(BaseRepository[AdminDocument]):
    """CRUD plus the auth-specific queries."""

    collection_name = ADMINS
    document_type = AdminDocument

    async def find_by_email(self, email: str) -> AdminDocument | None:
        """Look an admin up by address, using the same normalisation as storage."""
        return await self.find_one({"email": normalise_email(email)})

    async def find_by_reset_token_hash(self, token_hash: str) -> AdminDocument | None:
        """Resolve the account holding a given reset-token digest."""
        return await self.find_one({"password_reset_token_hash": token_hash})

    async def record_login(self, admin_id: ObjectId) -> AdminDocument | None:
        """Stamp ``last_login_at``. Returns ``None`` when the id is unknown."""
        return await self.update(admin_id, {"last_login_at": utcnow()})

    async def set_password_hash(
        self, admin_id: ObjectId, password_hash: str
    ) -> AdminDocument | None:
        """Replace the stored digest and revoke any outstanding reset token."""
        changes: dict[str, object] = {"password_hash": password_hash}
        changes.update(dict.fromkeys(RESET_CLEARED_FIELDS, None))
        return await self.update(admin_id, changes)

    async def store_reset_token(
        self, admin_id: ObjectId, token_hash: str, expires_at: datetime
    ) -> AdminDocument | None:
        """Attach a reset-token digest and its expiry, replacing any previous one."""
        return await self.update(
            admin_id,
            {
                "password_reset_token_hash": token_hash,
                "password_reset_expires_at": expires_at,
            },
        )

    async def clear_reset_token(self, admin_id: ObjectId) -> AdminDocument | None:
        """Drop any reset token without touching ``password_hash``.

        Used when an expired token is presented, so the stored password is never
        rewritten as a side effect of rejecting a bad request.
        """
        return await self.update(admin_id, dict.fromkeys(RESET_CLEARED_FIELDS, None))

    async def set_active(self, admin_id: ObjectId, is_active: bool) -> AdminDocument | None:
        """Enable or disable an account. Takes effect on the next request."""
        return await self.update(admin_id, {"is_active": is_active})
