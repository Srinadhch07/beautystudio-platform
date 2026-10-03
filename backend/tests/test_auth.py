"""Admin authentication, session transport, CSRF, throttling and password reset.

Several tests here exist specifically to pin down behaviour that could otherwise
drift silently:

* **The limiter is a process-wide singleton.** A leaking test would make
  unrelated tests fail with 429, so ``conftest.py`` resets it around every test.
* **Enumeration resistance is asserted by comparing whole payloads**, not just
  status codes. Status equality alone would pass even if the messages differed.
  Four separate bugs were found this way and are pinned by tests here: a dropped
  ``Retry-After`` header, a throttled ``forgot-password`` that never recorded
  attempts, a ``FRONTEND_URL`` gap that answered 503 for real accounts and 202 for
  unknown ones, and a delivery failure that was allowed to change the response.
* **The CSRF/cookie interaction is easy to get wrong** in a way that quietly
  stops testing anything, so both the refused and the accepted path are covered.

Timing is deliberately *not* asserted numerically. The equaliser is instead
verified structurally - the dummy digest must be a real Argon2id digest using the
same parameters as the live hasher, so the memory-hard work genuinely runs.
"""

from __future__ import annotations

import base64
import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from typing import Any
from urllib.parse import parse_qs

import jwt
import pytest
from argon2 import Type, extract_parameters
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi.testclient import TestClient

from app.api.deps_auth import get_auth_service
from app.core.config import Settings, get_settings
from app.core.cookies import CSRF_HEADER_NAME
from app.core.errors import BadRequestError
from app.core.passwords import (
    _DUMMY_DIGEST,
    ARGON2_HASH_LENGTH,
    ARGON2_MEMORY_COST_KIB,
    ARGON2_PARALLELISM,
    ARGON2_SALT_LENGTH,
    ARGON2_TIME_COST,
    WeakPasswordError,
    _dummy_verify,
    _hasher,
    hash_password,
    needs_rehash,
    password_strength_problems,
    validate_password_strength,
    verify_password,
)
from app.core.security import (
    ACCESS_TOKEN_TYPE,
    TokenError,
    create_access_token,
    decode_access_token,
)
from app.models.admin import AdminDocument
from app.repositories.admins import AdminsRepository
from app.schemas.auth import ForgotPasswordResponse
from app.services.auth import (
    GENERIC_LOGIN_FAILURE,
    GENERIC_RESET_FAILURE,
    AuthService,
    hash_reset_token,
)
from app.services.mail import EmailDeliveryError, EmailService
from tests.conftest import (
    ADMIN_EMAIL,
    ADMIN_NAME,
    ADMIN_PASSWORD,
    LOGIN_PATH,
    ME_PATH,
    run,
)
from tests.payloads import settings_payload

AUTH = "/api/v1/auth"
ADMIN_SETTINGS = "/api/v1/admin/site-settings"
UNKNOWN_EMAIL = "nobody@beautyparlour.app"
#: Satisfies the strength rules (>=12 chars, not common, not one repeated char).
NEW_PASSWORD = "an-entirely-different-passphrase-42"

MakeAdmin = Callable[..., AdminDocument]


# --- Helpers ------------------------------------------------------------------


def login(client: TestClient, email: str = ADMIN_EMAIL, password: str = ADMIN_PASSWORD) -> Any:
    return client.post(LOGIN_PATH, json={"email": email, "password": password})


def sign_in(client: TestClient) -> Any:
    """Log in and install the CSRF header, exactly as ``auth_client`` does."""
    response = login(client)
    assert response.status_code == 200, response.text
    client.headers[CSRF_HEADER_NAME] = response.json()["csrf_token"]
    return response


def build_bearer(admin: AdminDocument) -> str:
    return create_access_token(str(admin.id), settings=get_settings()).token


def repo_for(memory_database: Any) -> AdminsRepository:
    return AdminsRepository(memory_database)


def message_body(message: EmailMessage) -> str:
    return message.get_body(preferencelist=("plain",)).get_content()  # type: ignore[union-attr]


def extract_reset_url(message: EmailMessage) -> str:
    """Recover the full reset link from the email body."""
    for line in message_body(message).splitlines():
        if "reset-password?" in line:
            return line.strip()
    raise AssertionError("no reset link found in the message")


def extract_reset_token(message: EmailMessage) -> str:
    """Recover the raw token from the emailed link."""
    query = extract_reset_url(message).split("?", 1)[1]
    params = parse_qs(query)
    assert "reset_token" in params, f"expected a reset_token parameter, got {sorted(params)}"
    return params["reset_token"][0]


def minutes_ago(minutes: int) -> datetime:
    return datetime.now(UTC) - timedelta(minutes=minutes)


def spec() -> dict[str, Any]:
    from app.main import app as fastapi_app

    return fastapi_app.openapi()


def operations() -> list[tuple[str, str]]:
    """Every documented operation as ``(METHOD, path)``, computed once."""
    found: list[tuple[str, str]] = []
    for path, methods in spec()["paths"].items():
        for verb in methods:
            if verb in {"get", "post", "put", "patch", "delete"}:
                found.append((verb.upper(), path))
    return sorted(found)


def admin_operations() -> list[tuple[str, str]]:
    return [op for op in operations() if op[1].startswith("/api/v1/admin")]


@pytest.fixture()
def captured_reset(make_admin: MakeAdmin, monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """Capture outgoing mail instead of opening an SMTP connection.

    The suite must never talk to a mail server. Asserting on the captured message
    is also what proves the raw token appears *only* in the email and nowhere the
    database can reveal it.
    """
    sent: list[EmailMessage] = []

    def _capture(self: EmailService, message: EmailMessage) -> None:
        sent.append(message)

    monkeypatch.setattr(EmailService, "send", _capture)
    make_admin()
    return sent


def request_reset(client: TestClient, email: str = ADMIN_EMAIL) -> Any:
    return client.post(f"{AUTH}/forgot-password", json={"email": email})


def use_auth_service(client: TestClient, memory_database: Any, **overrides: Any) -> None:
    """Swap in an ``AuthService`` built with modified settings.

    Used to exercise the real HTTP path under misconfiguration, which is where the
    enumeration bugs lived.
    """
    settings = Settings(**overrides)
    client.app.dependency_overrides[get_auth_service] = lambda: AuthService(  # type: ignore[arg-type]
        repo_for(memory_database), settings
    )


# --- Password hashing ---------------------------------------------------------


def test_password_hash_round_trips() -> None:
    digest = hash_password("a-perfectly-fine-passphrase")

    assert verify_password("a-perfectly-fine-passphrase", digest) is True
    assert verify_password("a-perfectly-fine-passphras", digest) is False


def test_password_hash_is_argon2id_and_never_the_plaintext() -> None:
    digest = hash_password("a-perfectly-fine-passphrase")

    assert digest.startswith("$argon2id$")
    assert "a-perfectly-fine-passphrase" not in digest


def test_the_same_password_hashes_differently_each_time() -> None:
    """Distinct salts, so two admins sharing a password do not share a digest."""
    assert hash_password("a-perfectly-fine-passphrase") != hash_password(
        "a-perfectly-fine-passphrase"
    )


def test_a_freshly_made_hash_does_not_need_rehashing() -> None:
    assert needs_rehash(hash_password("a-perfectly-fine-passphrase")) is False


def test_missing_or_malformed_digests_fail_closed() -> None:
    """No digest, or garbage in the column, must never authenticate anybody."""
    assert verify_password("anything-at-all", None) is False
    assert verify_password("anything-at-all", "") is False
    assert verify_password("anything-at-all", "not-a-real-digest") is False
    assert verify_password("anything-at-all", "$argon2id$v=19$m=1,t=1,p=1$x$y") is False


def test_the_dummy_digest_matches_the_live_argon2_parameters() -> None:
    """The equaliser only equalises if it does the *same work*.

    ``_DUMMY_DIGEST`` is a constant compared against on every unknown-account
    login. If its parameters drifted below the live hasher's, the burn would
    quietly get cheaper and response latency would start leaking account
    existence again. Asserting the encoded parameters keeps them locked together.
    """
    parameters = extract_parameters(_DUMMY_DIGEST)

    assert parameters.type == Type.ID
    assert parameters.time_cost == ARGON2_TIME_COST
    assert parameters.memory_cost == ARGON2_MEMORY_COST_KIB
    assert parameters.parallelism == ARGON2_PARALLELISM
    assert parameters.hash_len == ARGON2_HASH_LENGTH
    assert parameters.salt_len == ARGON2_SALT_LENGTH


def test_the_dummy_digest_is_genuinely_verified_not_merely_parsed() -> None:
    """It must reach the hashing stage, not fail during parsing.

    A malformed digest raises ``InvalidHashError`` *before* any memory-hard work
    is done, so the "burn" would be instant and a request for a non-existent
    account would answer far faster than a real one. ``VerifyMismatchError`` is
    proof the verification actually ran. This is a structural check, not a flaky
    timing measurement.
    """
    with pytest.raises((VerifyMismatchError, VerificationError)) as caught:
        _hasher.verify(_DUMMY_DIGEST, "some-candidate-password")

    assert not isinstance(caught.value, InvalidHashError)


def test_the_dummy_burn_swallows_the_mismatch() -> None:
    assert _dummy_verify("some-candidate-password") is None


def test_weak_passwords_are_rejected_with_a_reason() -> None:
    assert password_strength_problems("short") == ["must be at least 12 characters"]
    assert "must not be entirely numeric" in password_strength_problems("1" * 20)
    assert "must not be a single repeated character" in password_strength_problems("a" * 20)
    assert "is too common" in password_strength_problems("password123")
    assert password_strength_problems(ADMIN_PASSWORD) == []


def test_an_over_long_password_is_rejected() -> None:
    problems = password_strength_problems("ab1!" + "x" * 300)

    assert any("at most" in problem for problem in problems)


def test_validate_password_strength_raises_for_weak_input() -> None:
    with pytest.raises(WeakPasswordError):
        validate_password_strength("password123")


# --- Login --------------------------------------------------------------------


def test_login_succeeds_and_sets_both_cookies(client: TestClient, make_admin: MakeAdmin) -> None:
    make_admin()
    settings = get_settings()

    response = login(client)

    assert response.status_code == 200, response.text
    assert client.cookies.get(settings.cookie_name)
    assert client.cookies.get(settings.csrf_cookie_name)


def test_login_returns_no_access_token_in_the_body(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    """The token belongs in an HttpOnly cookie, where script cannot read it."""
    make_admin()

    body = login(client).json()

    assert set(body) == {"admin", "expires_at", "csrf_token"}
    assert "token" not in body
    assert "password_hash" not in body["admin"]
    assert "password_reset_token_hash" not in body["admin"]


def test_login_stamps_last_login_at(
    client: TestClient, make_admin: MakeAdmin, memory_database: Any
) -> None:
    admin = make_admin()
    assert admin.last_login_at is None

    assert login(client).status_code == 200

    stored = run(repo_for(memory_database).find_by_id(admin.id))
    assert stored is not None
    assert stored.last_login_at is not None


def test_login_folds_the_letter_case_of_an_address(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    """Addresses are stored lower-cased, so the lookup has to fold case too."""
    make_admin()

    assert login(client, email=ADMIN_EMAIL.upper()).status_code == 200


# --- Enumeration resistance ---------------------------------------------------


def test_wrong_password_and_unknown_address_are_indistinguishable(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    make_admin()

    wrong_password = login(client, password="not-the-right-passphrase-1")
    unknown = login(client, email=UNKNOWN_EMAIL)

    assert wrong_password.status_code == unknown.status_code == 401
    assert wrong_password.json() == unknown.json()
    assert wrong_password.json()["error"]["message"] == GENERIC_LOGIN_FAILURE


def test_a_disabled_account_is_indistinguishable_from_a_wrong_password(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    make_admin(email="disabled@beautyparlour.app", is_active=False)

    disabled = login(client, email="disabled@beautyparlour.app")
    unknown = login(client, email=UNKNOWN_EMAIL)

    assert disabled.status_code == unknown.status_code == 401
    assert disabled.json() == unknown.json()


def test_an_account_with_no_usable_digest_cannot_sign_in(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    """A row with no digest must be treated as 'no credential', not as a match."""
    make_admin(email="nohash@beautyparlour.app", password=None, password_hash=None)

    response = login(client, email="nohash@beautyparlour.app")

    assert response.status_code == 401
    assert response.json()["error"]["message"] == GENERIC_LOGIN_FAILURE


def test_login_requires_both_fields(client: TestClient, make_admin: MakeAdmin) -> None:
    make_admin()

    assert client.post(LOGIN_PATH, json={"email": ADMIN_EMAIL}).status_code == 422
    assert client.post(LOGIN_PATH, json={"password": ADMIN_PASSWORD}).status_code == 422


def test_login_rejects_a_malformed_address(client: TestClient) -> None:
    assert client.post(LOGIN_PATH, json={"email": "nope", "password": "x"}).status_code == 422


# --- Token verification -------------------------------------------------------


def test_a_token_signed_with_another_key_is_rejected() -> None:
    other = Settings(JWT_SECRET="a-completely-different-signing-secret-value")

    with pytest.raises(TokenError):
        decode_access_token(
            create_access_token("6" * 24, settings=other).token, settings=get_settings()
        )


def test_an_expired_token_is_rejected() -> None:
    settings = get_settings()
    forged = jwt.encode(
        {
            "sub": "6" * 24,
            "type": ACCESS_TOKEN_TYPE,
            "iat": int(time.time()) - 7200,
            "exp": int(time.time()) - 3600,
            "jti": "expired-session",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(TokenError):
        decode_access_token(forged, settings=settings)


def test_a_token_of_the_wrong_type_is_rejected() -> None:
    """A password-reset-shaped token must not open a protected route."""
    settings = get_settings()
    wrong_type = jwt.encode(
        {
            "sub": "6" * 24,
            "type": "password_reset",
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "jti": "x",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(TokenError):
        decode_access_token(wrong_type, settings=settings)


def test_a_token_missing_required_claims_is_rejected() -> None:
    settings = get_settings()
    incomplete = jwt.encode(
        {"sub": "6" * 24, "type": ACCESS_TOKEN_TYPE},
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )

    with pytest.raises(TokenError):
        decode_access_token(incomplete, settings=settings)


def test_the_alg_none_forgery_is_rejected() -> None:
    """The classic JWT attack: strip the signature and claim ``alg=none``.

    The algorithm is pinned in code rather than read from the header, so this must
    fail even though the payload is well formed and unexpired.
    """

    def segment(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload).encode()
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    header = segment({"alg": "none", "typ": "JWT"})
    payload = segment(
        {
            "sub": "6" * 24,
            "type": ACCESS_TOKEN_TYPE,
            "iat": int(time.time()),
            "exp": int(time.time()) + 600,
            "jti": "forged",
        }
    )

    with pytest.raises(TokenError):
        decode_access_token(f"{header}.{payload}.", settings=get_settings())


def test_garbage_credentials_answer_401_rather_than_500(client: TestClient) -> None:
    assert client.get(ME_PATH, headers={"Authorization": "Bearer not-a-token"}).status_code == 401
    client.cookies.set(get_settings().cookie_name, "junk")
    assert client.get(ME_PATH).status_code == 401


# --- /me and logout -----------------------------------------------------------


def test_me_requires_a_session(anonymous_client: TestClient, make_admin: MakeAdmin) -> None:
    make_admin()

    response = anonymous_client.get(ME_PATH)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "not_authenticated"


def test_me_returns_the_profile_without_credentials(auth_client: TestClient) -> None:
    body = auth_client.get(ME_PATH).json()

    assert body["email"] == ADMIN_EMAIL
    assert body["name"] == ADMIN_NAME
    assert body["is_active"] is True
    assert "password_hash" not in body
    assert "password_reset_token_hash" not in body


def test_me_accepts_a_bearer_token(client: TestClient, make_admin: MakeAdmin) -> None:
    """Scripts and CI cannot use cookies, so the header is a supported path."""
    admin = make_admin()

    response = client.get(ME_PATH, headers={"Authorization": f"Bearer {build_bearer(admin)}"})

    assert response.status_code == 200, response.text
    assert response.json()["email"] == ADMIN_EMAIL


def test_deactivating_an_admin_revokes_access_immediately(
    client: TestClient, make_admin: MakeAdmin, memory_database: Any
) -> None:
    admin = make_admin()
    headers = {"Authorization": f"Bearer {build_bearer(admin)}"}
    assert client.get(ME_PATH, headers=headers).status_code == 200

    run(repo_for(memory_database).set_active(admin.id, False))

    assert client.get(ME_PATH, headers=headers).status_code == 401


def test_logout_clears_both_cookies(client: TestClient, make_admin: MakeAdmin) -> None:
    make_admin()
    sign_in(client)

    response = client.post(f"{AUTH}/logout")

    assert response.status_code == 200, response.text
    assert not client.cookies.get(get_settings().cookie_name)
    assert client.get(ME_PATH).status_code == 401


def test_logout_requires_a_session(anonymous_client: TestClient) -> None:
    assert anonymous_client.post(f"{AUTH}/logout").status_code == 401


# --- Protection of the admin surface ------------------------------------------


def test_every_admin_route_requires_authentication(anonymous_client: TestClient) -> None:
    """The regression guard for the whole admin surface.

    Walking the real route table beats trusting that each handler remembered its
    dependency, and it fails loudly if an admin route is ever added unprotected.
    The body sent is deliberately invalid: a dependency raising must short-circuit
    before request validation, so ``401`` - not ``422`` - is the correct answer and
    a ``422`` would mean authentication was skipped.
    """
    found = admin_operations()
    # 33 = 30 pre-media admin operations + POST/PATCH/DELETE /admin/media.
    # Updated deliberately when the media surface was added: the walk below is
    # what protects the surface, and this number only asserts that the walk saw
    # every route rather than silently covering a subset.
    assert len(found) == 33, f"expected the full admin surface, found {len(found)}"

    for method, path in found:
        response = anonymous_client.request(method, path, json={})
        assert response.status_code == 401, (
            f"{method} {path} answered {response.status_code} with no session"
        )
        assert response.json()["error"]["code"] == "not_authenticated"


def test_admin_routes_declare_a_security_requirement_in_openapi() -> None:
    document = spec()

    for method, path in admin_operations():
        operation = document["paths"][path][method.lower()]
        assert operation.get("security"), f"{method} {path} declares no security requirement"


def test_public_and_health_routes_stay_open(anonymous_client: TestClient) -> None:
    assert anonymous_client.get("/api/health").status_code == 200
    for path in (
        "/api/v1/public/site-settings",
        "/api/v1/public/services",
        "/api/v1/public/gallery",
        "/api/v1/public/testimonials",
        "/api/v1/public/offers",
    ):
        assert anonymous_client.get(path).status_code == 200, path


def test_login_and_reset_stay_reachable_without_a_session(anonymous_client: TestClient) -> None:
    """A client has to be able to obtain a session, and to recover a lost one."""
    assert anonymous_client.get(ME_PATH).status_code == 401
    assert anonymous_client.post(f"{AUTH}/logout").status_code == 401
    assert request_reset(anonymous_client, UNKNOWN_EMAIL).status_code == 202
    assert (
        anonymous_client.post(
            f"{AUTH}/reset-password", json={"token": "x", "new_password": NEW_PASSWORD}
        ).status_code
        == 400
    )


# --- CSRF ---------------------------------------------------------------------


def test_a_cookie_session_without_a_csrf_header_is_refused(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    make_admin()
    sign_in(client)
    del client.headers[CSRF_HEADER_NAME]

    # The body is valid, so the only possible reason for a refusal is the CSRF check.
    response = client.put(ADMIN_SETTINGS, json=settings_payload())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_a_mismatched_csrf_header_is_refused(client: TestClient, make_admin: MakeAdmin) -> None:
    make_admin()
    sign_in(client)

    response = client.put(
        ADMIN_SETTINGS,
        json=settings_payload(),
        headers={CSRF_HEADER_NAME: "not-the-real-token"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_failed"


def test_reads_need_no_csrf_header(client: TestClient, make_admin: MakeAdmin) -> None:
    make_admin()
    sign_in(client)
    del client.headers[CSRF_HEADER_NAME]

    assert client.get("/api/v1/admin/gallery").status_code == 200


def test_a_bearer_request_need_not_send_a_csrf_header(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    """Documented behaviour: only cookie-borne sessions are CSRF-checked.

    A pure ``Authorization`` request is not a browser form post and cannot be
    forged cross-site, so requiring a CSRF header would only hinder scripts.
    """
    admin = make_admin()

    response = client.put(
        ADMIN_SETTINGS,
        json=settings_payload(),
        headers={"Authorization": f"Bearer {build_bearer(admin)}"},
    )

    assert response.status_code == 200, response.text


def test_a_matching_csrf_header_is_accepted(auth_client: TestClient) -> None:
    response = auth_client.put(ADMIN_SETTINGS, json=settings_payload())

    assert response.status_code == 200, response.text


# --- Login throttling ---------------------------------------------------------


def test_repeated_failures_are_throttled(client: TestClient, make_admin: MakeAdmin) -> None:
    make_admin()
    limit = get_settings().login_rate_limit_max

    for _ in range(limit):
        assert login(client, password="wrong-passphrase-attempt-99").status_code == 401

    blocked = login(client, password="wrong-passphrase-attempt-99")

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"


def test_a_throttled_response_carries_retry_after(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    """The header has to survive the exception handler.

    ``Retry-After`` is set on the raised error rather than on the route's
    ``Response``, because the handler constructs a fresh response. It is an RFC 6585
    requirement, and a client cannot back off politely without it.
    """
    make_admin()
    for _ in range(get_settings().login_rate_limit_max):
        login(client, password="wrong-passphrase-attempt-99")

    blocked = login(client)

    assert blocked.status_code == 429
    assert int(blocked.headers["Retry-After"]) > 0


def test_throttling_refuses_even_a_correct_password(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    """Honest scope: the window locks the pair out, it is not a "try the real one" hint."""
    make_admin()
    for _ in range(get_settings().login_rate_limit_max):
        login(client, password="wrong-passphrase-attempt-99")

    assert login(client).status_code == 429


def test_a_successful_login_clears_the_failure_counter(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    """A user who fumbles twice must not be penalised for the rest of the window."""
    make_admin()
    limit = get_settings().login_rate_limit_max
    for _ in range(limit - 1):
        login(client, password="wrong-passphrase-attempt-99")

    assert login(client).status_code == 200

    # Were the counter not cleared, the second of these would already be a 429.
    for _ in range(limit):
        assert login(client, password="wrong-passphrase-attempt-99").status_code == 401


def test_a_throttled_response_does_not_confirm_the_account(
    client: TestClient, make_admin: MakeAdmin
) -> None:
    """The per-IP counter is shared, so both addresses are refused identically."""
    make_admin()
    for _ in range(get_settings().login_rate_limit_max):
        login(client, password="wrong-passphrase-attempt-99")

    known = login(client)
    unknown = login(client, email=UNKNOWN_EMAIL)

    assert known.status_code == unknown.status_code == 429
    assert known.json() == unknown.json()


def test_forgot_password_is_throttled(client: TestClient, captured_reset: list[Any]) -> None:
    """Recording only *checked* the limiter, so the window never filled."""
    limit = get_settings().login_rate_limit_max

    for _ in range(limit):
        assert request_reset(client).status_code == 202

    blocked = request_reset(client)

    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"
    assert int(blocked.headers["Retry-After"]) > 0


# --- Password reset -----------------------------------------------------------


def test_forgot_password_answers_the_same_for_known_and_unknown(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    known = request_reset(client, ADMIN_EMAIL)
    unknown = request_reset(client, UNKNOWN_EMAIL)

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()
    assert known.json() == ForgotPasswordResponse().model_dump()


def test_forgot_password_sends_exactly_one_mail_for_a_known_account(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    request_reset(client, ADMIN_EMAIL)

    assert len(captured_reset) == 1
    assert captured_reset[0]["To"] == ADMIN_EMAIL


def test_forgot_password_sends_nothing_for_an_unknown_address(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    request_reset(client, UNKNOWN_EMAIL)

    assert captured_reset == []


def test_forgot_password_sends_nothing_for_a_disabled_account(
    client: TestClient, captured_reset: list[EmailMessage], make_admin: MakeAdmin
) -> None:
    make_admin(email="disabled@beautyparlour.app", is_active=False)

    request_reset(client, "disabled@beautyparlour.app")

    assert captured_reset == []


def test_the_emailed_link_uses_the_configured_frontend_url(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    request_reset(client, ADMIN_EMAIL)
    body = message_body(captured_reset[0])

    assert get_settings().frontend_url in body
    # The message must not carry credential material beyond the link itself.
    assert ADMIN_PASSWORD not in body


def test_the_emailed_link_is_a_hash_route(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    """The SPA routes on ``location.hash``, so the link must carry ``#/``.

    A path-style ``/admin/reset-password`` link cannot open the reset page: on
    the static host it is a missing file, and behind a catch-all rewrite it
    renders the public home page and silently loses the token.
    """
    request_reset(client, ADMIN_EMAIL)
    body = message_body(captured_reset[0])
    frontend_url = (get_settings().frontend_url or "").rstrip("/")

    assert f"{frontend_url}/#/admin/reset-password?" in body
    # The path-style form must be gone; only the hash form may appear.
    assert f"{frontend_url}/admin/reset-password?" not in body


def test_the_emailed_link_names_the_parameter_reset_token(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    """The client reads ``reset_token``; a ``token`` parameter would be ignored."""
    request_reset(client, ADMIN_EMAIL)
    link = extract_reset_url(captured_reset[0])
    query = link.split("?", 1)[1]
    params = parse_qs(query)

    assert set(params) == {"reset_token"}
    assert params["reset_token"][0]
    # A bare ``token`` parameter would be ignored by the client. Note that
    # ``"token" in query`` is meaningless here - ``reset_token`` contains it -
    # so the absence is asserted on the parsed keys and on the query prefix.
    assert query.startswith("reset_token=")
    assert "&token=" not in query


def test_the_reset_url_helper_matches_the_emailed_link(
    client: TestClient,
    captured_reset: list[EmailMessage],
    memory_database: Any,
    settings: Settings,
) -> None:
    """The mailed link is exactly what ``build_reset_url`` produces."""
    request_reset(client, ADMIN_EMAIL)
    raw_token = extract_reset_token(captured_reset[0])

    service = AuthService(repo_for(memory_database), settings)
    assert service.build_reset_url(raw_token) == extract_reset_url(captured_reset[0])


def test_only_the_token_digest_is_persisted(
    client: TestClient, captured_reset: list[EmailMessage], memory_database: Any
) -> None:
    """A database leak must not hand an attacker a usable reset token."""
    request_reset(client, ADMIN_EMAIL)
    raw_token = extract_reset_token(captured_reset[0])

    stored = run(repo_for(memory_database).find_by_email(ADMIN_EMAIL))

    assert stored is not None
    assert stored.password_reset_token_hash == hash_reset_token(raw_token)
    assert raw_token not in (stored.password_reset_token_hash or "")
    assert stored.password_reset_expires_at is not None


def test_reset_lets_the_admin_sign_in_with_the_new_password(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    request_reset(client, ADMIN_EMAIL)
    raw_token = extract_reset_token(captured_reset[0])

    response = client.post(
        f"{AUTH}/reset-password", json={"token": raw_token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 200, response.text
    assert login(client, password=ADMIN_PASSWORD).status_code == 401
    assert login(client, password=NEW_PASSWORD).status_code == 200


def test_a_reset_token_cannot_be_used_twice(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    request_reset(client, ADMIN_EMAIL)
    raw_token = extract_reset_token(captured_reset[0])
    assert (
        client.post(
            f"{AUTH}/reset-password",
            json={"token": raw_token, "new_password": NEW_PASSWORD},
        ).status_code
        == 200
    )

    replay = client.post(
        f"{AUTH}/reset-password",
        json={"token": raw_token, "new_password": "yet-another-passphrase-77"},
    )

    assert replay.status_code == 400
    assert replay.json()["error"]["code"] == "invalid_reset_token"
    # The replayed password must not have taken effect.
    assert login(client, password=NEW_PASSWORD).status_code == 200
    assert login(client, password="yet-another-passphrase-77").status_code == 401


def test_an_expired_token_is_refused_and_cleared(
    client: TestClient, captured_reset: list[EmailMessage], memory_database: Any
) -> None:
    request_reset(client, ADMIN_EMAIL)
    raw_token = extract_reset_token(captured_reset[0])
    stored = run(repo_for(memory_database).find_by_email(ADMIN_EMAIL))
    assert stored is not None
    run(repo_for(memory_database).update(stored.id, {"password_reset_expires_at": minutes_ago(1)}))

    response = client.post(
        f"{AUTH}/reset-password", json={"token": raw_token, "new_password": NEW_PASSWORD}
    )

    assert response.status_code == 400
    assert response.json()["error"]["message"] == GENERIC_RESET_FAILURE
    after = run(repo_for(memory_database).find_by_id(stored.id))
    assert after is not None
    assert after.password_reset_token_hash is None
    # Rejecting a token must not lock the owner out.
    assert login(client).status_code == 200


def test_rejecting_an_expired_token_does_not_rewrite_the_password(
    client: TestClient, captured_reset: list[EmailMessage], memory_database: Any
) -> None:
    request_reset(client, ADMIN_EMAIL)
    raw_token = extract_reset_token(captured_reset[0])
    stored = run(repo_for(memory_database).find_by_email(ADMIN_EMAIL))
    assert stored is not None
    original_hash = stored.password_hash
    run(repo_for(memory_database).update(stored.id, {"password_reset_expires_at": minutes_ago(1)}))

    client.post(f"{AUTH}/reset-password", json={"token": raw_token, "new_password": NEW_PASSWORD})

    after = run(repo_for(memory_database).find_by_id(stored.id))
    assert after is not None
    assert after.password_hash == original_hash


def test_unknown_malformed_and_empty_tokens_fail_identically(client: TestClient) -> None:
    def attempt(token: str) -> Any:
        return client.post(
            f"{AUTH}/reset-password", json={"token": token, "new_password": NEW_PASSWORD}
        )

    responses = [attempt("totally-made-up-token"), attempt("!!!"), attempt("")]

    assert {r.status_code for r in responses} == {400}
    assert responses[0].json() == responses[1].json() == responses[2].json()


def test_a_weak_new_password_is_rejected_but_the_token_survives(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    """Feedback about the submitted password is safe; feedback about the account is not."""
    request_reset(client, ADMIN_EMAIL)
    raw_token = extract_reset_token(captured_reset[0])

    rejected = client.post(
        f"{AUTH}/reset-password", json={"token": raw_token, "new_password": "password123"}
    )

    assert rejected.status_code == 422
    retry = client.post(
        f"{AUTH}/reset-password", json={"token": raw_token, "new_password": NEW_PASSWORD}
    )
    assert retry.status_code == 200, retry.text


def test_a_second_reset_request_invalidates_the_first(
    client: TestClient, captured_reset: list[EmailMessage]
) -> None:
    request_reset(client, ADMIN_EMAIL)
    first = extract_reset_token(captured_reset[0])
    request_reset(client, ADMIN_EMAIL)
    second = extract_reset_token(captured_reset[1])
    assert first != second

    assert (
        client.post(
            f"{AUTH}/reset-password", json={"token": first, "new_password": NEW_PASSWORD}
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"{AUTH}/reset-password", json={"token": second, "new_password": NEW_PASSWORD}
        ).status_code
        == 200
    )


def test_forgot_password_answers_normally_when_delivery_fails(
    client: TestClient, make_admin: MakeAdmin, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A mail failure must not change the response - that would leak existence."""

    def _explode(self: EmailService, message: EmailMessage) -> None:
        raise EmailDeliveryError("smtp is down")

    monkeypatch.setattr(EmailService, "send", _explode)
    make_admin()

    response = request_reset(client, ADMIN_EMAIL)

    assert response.status_code == 202
    assert response.json() == ForgotPasswordResponse().model_dump()


def test_forgot_password_does_not_leak_existence_when_smtp_is_unconfigured(
    client: TestClient, make_admin: MakeAdmin, memory_database: Any
) -> None:
    make_admin()
    use_auth_service(client, memory_database, smtp_host="", smtp_from_email="")

    known = request_reset(client, ADMIN_EMAIL)
    unknown = request_reset(client, UNKNOWN_EMAIL)

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_forgot_password_does_not_leak_existence_when_frontend_url_is_missing(
    client: TestClient, make_admin: MakeAdmin, memory_database: Any
) -> None:
    """Regression: this used to answer 503 for a real account and 202 for an unknown one.

    The shipped ``.env`` leaves ``FRONTEND_URL`` empty, and ``build_reset_url``
    raises when it is, so "does this address exist?" had a working answer.
    """
    make_admin()
    use_auth_service(client, memory_database, frontend_url="")

    known = request_reset(client, ADMIN_EMAIL)
    unknown = request_reset(client, UNKNOWN_EMAIL)

    assert known.status_code == unknown.status_code == 202
    assert known.json() == unknown.json()


def test_no_token_is_stored_when_the_link_cannot_be_built(
    client: TestClient, make_admin: MakeAdmin, memory_database: Any
) -> None:
    """A token nobody can receive is stored for no reason, and shortens nothing."""
    make_admin()
    use_auth_service(client, memory_database, frontend_url="")

    request_reset(client, ADMIN_EMAIL)

    stored = run(repo_for(memory_database).find_by_email(ADMIN_EMAIL))
    assert stored is not None
    assert stored.password_reset_token_hash is None


def test_reset_token_hash_is_a_plain_sha256_of_the_token() -> None:
    raw = "a-raw-reset-token"

    digest = hash_reset_token(raw)

    assert digest == hashlib.sha256(raw.encode()).hexdigest()
    assert raw not in digest


# --- Provisioning -------------------------------------------------------------


def test_create_admin_stores_only_a_digest(make_admin: MakeAdmin) -> None:
    admin = make_admin(email="new-owner@beautyparlour.app", password="a-fresh-passphrase-88")

    assert admin.password_hash is not None
    assert verify_password("a-fresh-passphrase-88", admin.password_hash) is True
    assert "a-fresh-passphrase-88" not in admin.password_hash


def test_create_admin_refuses_a_duplicate_address(memory_database: Any, settings: Settings) -> None:
    service = AuthService(repo_for(memory_database), settings)
    run(service.create_admin(email=ADMIN_EMAIL, name=ADMIN_NAME, password=ADMIN_PASSWORD))

    with pytest.raises(BadRequestError):
        run(service.create_admin(email=ADMIN_EMAIL, name=ADMIN_NAME, password=ADMIN_PASSWORD))


def test_create_admin_refuses_a_weak_password(memory_database: Any, settings: Settings) -> None:
    service = AuthService(repo_for(memory_database), settings)

    with pytest.raises(WeakPasswordError):
        run(
            service.create_admin(
                email="weak@beautyparlour.app", name="Weak", password="password123"
            )
        )


def test_create_admin_normalises_the_address(memory_database: Any, settings: Settings) -> None:
    service = AuthService(repo_for(memory_database), settings)

    admin = run(
        service.create_admin(email=ADMIN_EMAIL.upper(), name=ADMIN_NAME, password=ADMIN_PASSWORD)
    )

    assert admin.email == ADMIN_EMAIL
