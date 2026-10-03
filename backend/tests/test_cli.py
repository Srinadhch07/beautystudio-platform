"""The ``create-admin`` CLI.

This is the *only* way an administrator account can be created, so it needs
tests of its own - particularly the failure paths, because those are what stop
an operator from provisioning a weak account or accidentally resetting somebody
else's password by re-running the command.

Nothing here touches the real database. ``conftest.py`` points ``MONGO_URI`` at
an unreachable port, and the database layer is additionally replaced with the
in-memory one, so even a missed patch fails fast instead of writing to Atlas.
"""

from __future__ import annotations

import builtins
import getpass
from collections.abc import Iterator
from typing import Any

import pytest

from app.cli import create_admin as cli
from app.core.passwords import verify_password
from app.repositories.admins import AdminsRepository
from tests.conftest import run

EMAIL = "owner@beautyparlour.app"
NAME = "Test Owner"
PASSWORD = "correct-horse-battery-staple-9"
ALT_PASSWORD = "a-completely-different-passphrase-5"


@pytest.fixture()
def cli_db(memory_database: Any, monkeypatch: pytest.MonkeyPatch) -> Iterator[Any]:
    """Point the CLI at the in-memory database.

    All four database entry points are replaced, because ``create_admin`` reaches
    for the module-level names rather than taking a connection argument.
    """

    async def _ok(_settings: Any = None) -> bool:
        return True

    async def _noop(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(cli, "init_database", _ok)
    monkeypatch.setattr(cli, "get_database", lambda: memory_database)
    monkeypatch.setattr(cli, "ensure_indexes", _noop)
    monkeypatch.setattr(cli, "close_database", _noop)
    yield memory_database


def run_cli(
    monkeypatch: pytest.MonkeyPatch,
    *args: str,
    email: str = EMAIL,
    name: str = NAME,
    password: str = PASSWORD,
) -> int:
    """Drive ``main`` with the password supplied non-interactively."""
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", password)
    return cli.main(["--email", email, "--name", name, "--password-stdin", *args])


# --- Happy path ---------------------------------------------------------------


def test_creates_an_admin_and_exits_zero(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(monkeypatch)

    assert code == cli.EXIT_OK
    stored = run(AdminsRepository(cli_db).find_by_email(EMAIL))
    assert stored is not None
    assert stored.name == NAME
    assert stored.is_active is True


def test_the_password_is_hashed_and_never_echoed(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    run_cli(monkeypatch)

    stored = run(AdminsRepository(cli_db).find_by_email(EMAIL))
    assert stored is not None and stored.password_hash is not None
    assert verify_password(PASSWORD, stored.password_hash) is True
    assert PASSWORD not in stored.password_hash

    output = capsys.readouterr()
    assert PASSWORD not in output.out
    assert PASSWORD not in output.err
    assert stored.password_hash not in output.out


def test_the_address_is_normalised(cli_db: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    run_cli(monkeypatch, email="Owner@BeautyParlour.App")

    assert run(AdminsRepository(cli_db).find_by_email(EMAIL)) is not None


# --- Refusals -----------------------------------------------------------------


def test_a_duplicate_address_exits_three_and_changes_nothing(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Re-running the command must never quietly reset somebody's password."""
    assert run_cli(monkeypatch) == cli.EXIT_OK
    before = run(AdminsRepository(cli_db).find_by_email(EMAIL))
    assert before is not None

    code = run_cli(monkeypatch, password=ALT_PASSWORD)

    assert code == cli.EXIT_DUPLICATE
    after = run(AdminsRepository(cli_db).find_by_email(EMAIL))
    assert after is not None
    assert after.password_hash == before.password_hash
    assert verify_password(ALT_PASSWORD, after.password_hash) is False


def test_a_weak_password_is_refused_before_any_write(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(monkeypatch, password="password123")

    assert code == cli.EXIT_INVALID_INPUT
    assert run(AdminsRepository(cli_db).find_by_email(EMAIL)) is None
    assert "12 characters" in capsys.readouterr().err


def test_a_short_password_is_refused(cli_db: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    assert run_cli(monkeypatch, password="short") == cli.EXIT_INVALID_INPUT
    assert run(AdminsRepository(cli_db).find_by_email(EMAIL)) is None


def test_an_empty_password_is_refused(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(monkeypatch, password="")

    assert code == cli.EXIT_INVALID_INPUT
    assert "password is required" in capsys.readouterr().err


def test_a_malformed_address_is_refused(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    code = run_cli(monkeypatch, email="not-an-address")

    assert code == cli.EXIT_INVALID_INPUT
    assert "Error" in capsys.readouterr().err
    assert run(AdminsRepository(cli_db).find_by_email(EMAIL)) is None


def test_an_unreachable_database_exits_four(
    memory_database: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The operator is told plainly that nothing was created."""

    async def _unreachable(_settings: Any = None) -> bool:
        return False

    monkeypatch.setattr(cli, "init_database", _unreachable)
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", PASSWORD)

    code = cli.main(["--email", EMAIL, "--name", NAME, "--password-stdin"])

    assert code == cli.EXIT_UNAVAILABLE
    assert "no account was created" in capsys.readouterr().err.lower()


def test_a_missing_jwt_secret_blocks_provisioning(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """An account that cannot sign in is worse than no account."""
    from app.core.config import Settings, get_settings

    weak = Settings(JWT_SECRET="too-short")
    monkeypatch.setattr(cli, "get_settings", lambda: weak)
    monkeypatch.setenv("ADMIN_INITIAL_PASSWORD", PASSWORD)

    code = cli.main(["--email", EMAIL, "--name", NAME, "--password-stdin"])

    assert code == cli.EXIT_INVALID_INPUT
    assert "JWT_SECRET" in capsys.readouterr().err
    assert get_settings().is_auth_configured  # the real one is fine
    assert run(AdminsRepository(cli_db).find_by_email(EMAIL)) is None


# --- Interactive prompts ------------------------------------------------------


def test_the_prompted_password_must_be_typed_twice(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    answers = iter([PASSWORD, ALT_PASSWORD])
    monkeypatch.setattr(getpass, "getpass", lambda _prompt="": next(answers))

    code = cli.main(["--email", EMAIL, "--name", NAME])

    assert code == cli.EXIT_INVALID_INPUT
    assert "did not match" in capsys.readouterr().err
    assert run(AdminsRepository(cli_db).find_by_email(EMAIL)) is None


def test_a_matching_prompted_password_creates_the_admin(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    answers = iter([PASSWORD, PASSWORD])
    monkeypatch.setattr(getpass, "getpass", lambda _prompt="": next(answers))

    assert cli.main(["--email", EMAIL, "--name", NAME]) == cli.EXIT_OK
    assert run(AdminsRepository(cli_db).find_by_email(EMAIL)) is not None


def test_missing_interactive_fields_are_refused(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")

    assert cli.main([]) == cli.EXIT_INVALID_INPUT


def test_email_and_name_are_prompted_when_omitted(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = iter([EMAIL, NAME])

    def _input(_prompt: str = "") -> str:
        return next(prompts)

    monkeypatch.setattr(builtins, "input", _input)
    answers = iter([PASSWORD, PASSWORD])
    monkeypatch.setattr(getpass, "getpass", lambda _prompt="": next(answers))

    assert cli.main([]) == cli.EXIT_OK
    assert run(AdminsRepository(cli_db).find_by_email(EMAIL)) is not None


# --- Password transport -------------------------------------------------------


def test_a_password_can_be_taken_from_a_named_variable(
    cli_db: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("ADMIN_INITIAL_PASSWORD", raising=False)
    monkeypatch.setenv("MY_CLI_PASSWORD", PASSWORD)

    code = cli.main(
        ["--email", EMAIL, "--name", NAME, "--password-stdin", "--password-env", "MY_CLI_PASSWORD"]
    )

    assert code == cli.EXIT_OK
    stored = run(AdminsRepository(cli_db).find_by_email(EMAIL))
    assert stored is not None
    assert verify_password(PASSWORD, stored.password_hash) is True


def test_the_password_is_never_accepted_as_an_argument() -> None:
    """An argument would land in shell history and be visible in ``ps``.

    Deliberately absent, and asserted so a future convenience does not quietly
    reintroduce the leak.
    """
    with pytest.raises(SystemExit) as caught:
        cli.main(["--email", EMAIL, "--name", NAME, "--password", PASSWORD])

    assert caught.value.code == 2


def test_the_help_explains_why_a_password_argument_is_refused() -> None:
    """This is where an operator looks before deciding to pass one, so say why."""
    text = "\n".join(_help_lines()).lower()

    assert "admin_initial_password" in text
    assert "shell history" in text
    assert "process list" in text


def test_the_help_advertises_the_safe_password_options() -> None:
    text = "\n".join(_help_lines())

    assert "--password-stdin" in text
    assert "--password-env" in text


def _help_lines() -> list[str]:
    import contextlib
    import io

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), pytest.raises(SystemExit):
        cli.main(["--help"])
    return buffer.getvalue().splitlines()
