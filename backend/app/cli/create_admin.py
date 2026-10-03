"""Create the first administrator account.

Run it explicitly, on a machine you control::

    python -m app.cli.create_admin

Why a CLI rather than a default account or a seed script
-------------------------------------------------------
An initial admin must be a *decision by a human*, with a password that human
chose. Shipping a default ``admin@`` / ``admin123`` account - even one that
prompts for a change on first login - reliably ends up deployed unchanged, and
that is the single most common way admin panels are taken over. So there is no
seeding path, no default credential, and nothing that runs automatically at
start-up.

The password is read with :func:`getpass.getpass`, so it is never echoed to the
terminal, never accepted as a command-line argument (which would land in shell
history and in the process list), and never written to a file.

The command is safe to re-run: an existing address is reported and nothing is
changed, so it cannot be used to silently reset somebody's password.
"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import logging
import sys

from pydantic import ValidationError

from app.core.config import MIN_JWT_SECRET_LENGTH, get_settings
from app.core.errors import BadRequestError
from app.core.logging import configure_logging
from app.core.passwords import WeakPasswordError, password_strength_problems
from app.db.indexes import ensure_indexes
from app.db.mongo import close_database, get_database, init_database
from app.repositories.admins import AdminsRepository
from app.services.auth import AuthService

logger = logging.getLogger("app.cli.create_admin")

EXIT_OK = 0
EXIT_INVALID_INPUT = 2
EXIT_DUPLICATE = 3
EXIT_UNAVAILABLE = 4


def _prompt(prompt: str) -> str:
    return input(prompt).strip()


def _prompt_password(prompt: str) -> str | None:
    """Ask twice, and require a match. Returns ``None`` if they differ."""
    first = getpass.getpass(prompt)
    if not first:
        print("Error: the password must not be empty.", file=sys.stderr)
        return None
    again = getpass.getpass("Confirm password: ")
    if first != again:
        print("Error: the passwords did not match.", file=sys.stderr)
        return None
    return first


def _resolve_password(source: str, env_var: str) -> str | None:
    """Obtain the password, then make sure it is not the argument-list kind of leak.

    ``--password-env`` names an environment variable rather than taking the
    value on the command line, because an argument would be visible in shell
    history and in ``ps`` output to every other user on the machine.
    """
    if source == "env":
        import os

        return os.environ.get(env_var) or None
    return _prompt_password(f"Password for the new admin [{env_var}]: ")


async def create_admin(email: str, name: str, password: str) -> int:
    """Create one admin. Returns a process exit code."""
    settings = get_settings()

    if not await init_database(settings):
        print(
            "Error: MongoDB is not reachable, so no account was created.",
            file=sys.stderr,
        )
        return EXIT_UNAVAILABLE
    await ensure_indexes(get_database())

    repository = AdminsRepository(get_database())
    service = AuthService(repository, settings)

    try:
        admin = await service.create_admin(email=email, name=name, password=password)
    except ValidationError as exc:
        # Invalid address syntax. Print the field-level reason only.
        for error in exc.errors():
            print(f"Error: {error['loc'][-1]}: {error['msg']}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except WeakPasswordError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return EXIT_INVALID_INPUT
    except BadRequestError as exc:
        # The address is already taken. Reported rather than "fixed", so that
        # re-running the command can never quietly reset somebody's password.
        print(f"Error: {exc.message}", file=sys.stderr)
        return EXIT_DUPLICATE

    # Deliberately not printing the password, and not the hash either.
    print(f"Created admin {admin.email} (id={admin.id}).")
    return EXIT_OK


async def _main_async(args: argparse.Namespace) -> int:
    settings = get_settings()

    if not settings.is_auth_configured:
        print(
            "Error: JWT_SECRET is missing or shorter than "
            f"{MIN_JWT_SECRET_LENGTH} characters. Set it before "
            "provisioning an admin, otherwise the account cannot sign in.",
            file=sys.stderr,
        )
        return EXIT_INVALID_INPUT

    email = args.email or _prompt("Admin email: ")
    if not email:
        print("Error: an email address is required.", file=sys.stderr)
        return EXIT_INVALID_INPUT

    name = args.name or _prompt("Display name: ")
    if not name:
        print("Error: a display name is required.", file=sys.stderr)
        return EXIT_INVALID_INPUT

    password = _resolve_password(args.password_source, args.password_env)
    if not password:
        print("Error: a password is required.", file=sys.stderr)
        return EXIT_INVALID_INPUT

    problems = password_strength_problems(password)
    if problems:
        print(
            "Error: password " + "; ".join(problems) + ".",
            file=sys.stderr,
        )
        return EXIT_INVALID_INPUT

    try:
        return await create_admin(email, name, password)
    finally:
        await close_database()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli.create_admin",
        description="Create an administrator account.",
        epilog=(
            "There is deliberately no option for passing the password on the command "
            "line. An argument is recorded in shell history and is visible to every "
            "other user on the machine in the process list, so use --password-stdin "
            "(or simply run the command and type it at the prompt)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--email", help="Admin email address. Prompted if omitted.")
    parser.add_argument("--name", help="Display name. Prompted if omitted.")
    parser.add_argument(
        "--password-stdin",
        dest="password_source",
        action="store_const",
        const="env",
        default="prompt",
        help=(
            "Read the password from the ADMIN_INITIAL_PASSWORD environment "
            "variable instead of prompting. Preferred for automation."
        ),
    )
    parser.add_argument(
        "--password-env",
        default="ADMIN_INITIAL_PASSWORD",
        help="Name of the environment variable holding the password.",
    )
    args = parser.parse_args(argv)

    configure_logging(get_settings().log_level)

    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        print("\nCancelled. No account was created.", file=sys.stderr)
        return EXIT_INVALID_INPUT


if __name__ == "__main__":
    raise SystemExit(main())
