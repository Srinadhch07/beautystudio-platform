"""Password hashing and strength rules.

Hashing uses **Argon2id** through :mod:`argon2`, the winner of the Password
Hashing Competition. It is memory-hard, which is what makes offline cracking
expensive, and it is a widely deployed, audited implementation - deliberately
*not* something hand-rolled here.

Hard rules enforced by this module:

* plaintext passwords are never persisted, logged or returned;
* verification is constant-time (delegated to ``argon2``);
* the parameters below are explicit so they can be raised later without a data
  migration - existing digests keep verifying because Argon2 records the
  parameters it was created with inside the digest string.
"""

from __future__ import annotations

import contextlib
import re

from argon2 import PasswordHasher, Type
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

#: Argon2id parameters. 64 MiB / 3 passes follows the OWASP Password Storage
#: Cheat Sheet baseline for a single-process CMS.
ARGON2_TIME_COST = 3
ARGON2_MEMORY_COST_KIB = 64 * 1024
ARGON2_PARALLELISM = 2
ARGON2_HASH_LENGTH = 32
ARGON2_SALT_LENGTH = 16

#: A dummy digest used to keep the *timing* of a login attempt similar whether
#: or not the account exists. Verifying against this constant costs the same as
#: a real check, so response time cannot be used to enumerate accounts.
#:
#: This is a genuine Argon2id digest produced by :func:`hash_password` with the
#: parameters above, and ``tests/test_auth.py`` asserts that it still matches them.
#: A hand-written lookalike would not do: the length fields would be inconsistent,
#: and a digest that failed to *parse* would raise before any memory-hard work was
#: done - making the burn instant and the timing protection useless.
#:
#: Its preimage is a fixed public string, which is safe: this value is only ever
#: used as a comparison target to consume CPU, and :func:`verify_password` ignores
#: the result entirely when no real hash exists.
_DUMMY_DIGEST = (
    "$argon2id$v=19$m=65536,t=3,p=2$YcC1q6K9yMW4lodnygpemg$"
    "zqLgs36WUSnXF2tb70agwGPG6WNYy5ZHT8IefdvYgYg"
)

#: Minimum accepted length. NIST SP 800-63B treats length as the primary
#: factor, so the composition rules below are deliberately modest.
MIN_PASSWORD_LENGTH = 12
MAX_PASSWORD_LENGTH = 256

_hasher = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST_KIB,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LENGTH,
    salt_len=ARGON2_SALT_LENGTH,
    type=Type.ID,
)


class WeakPasswordError(ValueError):
    """The supplied password does not meet the minimum strength rules."""


def hash_password(password: str) -> str:
    """Return an Argon2id digest for ``password``.

    The caller is responsible for having validated strength first; this
    function does not reject weak input because hashing is also used for
    verifying legacy rows.
    """
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    """Check ``password`` against a stored digest.

    Returns ``False`` - never raises - for an unknown account, a missing hash
    or a malformed digest. ``needs_rehash`` is intentionally not surfaced here;
    rehash-on-login can be added once an Argon2 parameter bump is needed.
    """
    if not password_hash:
        # Burn comparable time so a missing account is not distinguishable by
        # response latency from a wrong password.
        _dummy_verify(password)
        return False
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _dummy_verify(password: str) -> None:
    """Burn a full Argon2 verification against a constant digest.

    Used when no real hash is available, so that a request for a
    non-existent account costs the same as a request for a real one. The
    digest in ``_DUMMY_DIGEST`` is a genuine, well-formed Argon2id string, so
    this genuinely performs the memory-hard work rather than failing during
    parsing - that is what makes the timing actually comparable.
    """
    with contextlib.suppress(VerifyMismatchError, VerificationError, InvalidHashError):
        _hasher.verify(_DUMMY_DIGEST, password)


def needs_rehash(password_hash: str) -> bool:
    """True when a stored digest uses weaker parameters than the current ones."""
    try:
        return _hasher.check_needs_rehash(password_hash)
    except InvalidHashError:
        return False


def password_strength_problems(password: str) -> list[str]:
    """Return human-readable reasons the password is unacceptable.

    A list (rather than the first failure) lets the CLI and the API explain
    every problem in one pass.
    """
    problems: list[str] = []

    if len(password) < MIN_PASSWORD_LENGTH:
        problems.append(f"must be at least {MIN_PASSWORD_LENGTH} characters")
    if len(password) > MAX_PASSWORD_LENGTH:
        problems.append(f"must be at most {MAX_PASSWORD_LENGTH} characters")
    if password.strip() != password or not password.strip():
        problems.append("must not be only whitespace")
    if password.isdigit():
        problems.append("must not be entirely numeric")
    if re.fullmatch(r"(.)\1*", password):
        problems.append("must not be a single repeated character")
    if _is_common_password(password):
        problems.append("is too common")

    return problems


def validate_password_strength(password: str) -> None:
    """Raise :class:`WeakPasswordError` if the password is not acceptable."""
    problems = password_strength_problems(password)
    if problems:
        raise WeakPasswordError("Password " + "; ".join(problems) + ".")


#: A deliberately small denylist. The point is to reject the handful of
#: passwords that appear in every credential-stuffing wordlist, not to
#: reimplement a breach corpus. Password *managers* are the real mitigation.
_COMMON_PASSWORDS = frozenset(
    {
        "password",
        "password1",
        "password123",
        "passw0rd",
        "admin123",
        "administrator",
        "letmein",
        "welcome",
        "welcome1",
        "changeme",
        "qwerty",
        "qwerty123",
        "123456",
        "12345678",
        "123456789",
        "1234567890",
        "abc123",
        "iloveyou",
        "sunshine",
        "princess",
        "football",
        "monkey",
        "shadow",
        "master",
        "dragon",
        "login",
        "abc12345",
        "beautyparlour",
        "beauty123",
        "parlour123",
    }
)


def _is_common_password(password: str) -> bool:
    return password.strip().lower() in _COMMON_PASSWORDS
