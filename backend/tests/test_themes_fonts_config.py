"""Themes, fonts and the aggregated public configuration.

Two properties are asserted throughout:

* **An administrator cannot inject presentation.** ``active_theme`` and
  ``active_font`` accept only ids from the curated tables, so no request can put
  a stylesheet URL, a ``font-family`` declaration or a ``url()`` into the site.
* **No credential can reach a public response.** The config endpoint is built
  from the settings document and the preset tables only; it never reads
  environment configuration, so there is no path from a secret to a response.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from unittest.mock import AsyncMock

import pytest
from fastapi import Response
from fastapi.testclient import TestClient

from app.core.fonts import DEFAULT_FONT, FONT_PRESETS, is_known_font
from app.core.themes import DEFAULT_THEME, THEME_PRESETS, is_known_theme
from tests.payloads import settings_payload

ADMIN_SETTINGS = "/api/v1/admin/site-settings"
PUBLIC_SETTINGS = "/api/v1/public/site-settings"
CONFIG = "/api/v1/public/config"
THEMES = "/api/v1/public/themes"
FONTS = "/api/v1/public/fonts"

#: Tokens every theme must define for the frontend to be able to style a page.
REQUIRED_TOKENS = {
    "primary",
    "secondary",
    "accent",
    "background",
    "surface",
    "text",
    "muted_text",
    "border",
    "button_bg",
    "button_text",
    "button_hover_bg",
    "button_radius",
}


# --- Themes -------------------------------------------------------------------


def test_there_are_five_theme_presets() -> None:
    """A curated shortlist, not a growing registry."""
    assert len(THEME_PRESETS) == 5


def test_theme_presets_are_well_formed() -> None:
    """Every preset is uniquely identified and fully tokenised."""
    ids = [preset.id for preset in THEME_PRESETS]
    assert len(set(ids)) == len(ids), "theme ids must be unique"

    for preset in THEME_PRESETS:
        assert preset.id and preset.name and preset.description
        assert set(preset.tokens) >= REQUIRED_TOKENS, f"{preset.id} is missing tokens"
        for name, value in preset.tokens.items():
            assert value.strip(), f"{preset.id}.{name} is blank"
            if name == "button_radius":
                assert value.endswith("px"), "radius is a CSS length"
            else:
                assert value.startswith("#") and len(value) in {4, 7}, (
                    f"{preset.id}.{name} is not a hex colour: {value}"
                )


def test_theme_tokens_expose_css_variables() -> None:
    preset = THEME_PRESETS[0]
    variables = preset.tokens.as_css_variables
    assert variables["--bp-primary"] == preset.tokens["primary"]
    assert "--bp-muted-text" in variables


def test_public_theme_catalogue_lists_every_preset(anonymous_client: TestClient) -> None:
    response = anonymous_client.get(THEMES)

    assert response.status_code == 200
    body = response.json()
    assert [entry["id"] for entry in body] == [preset.id for preset in THEME_PRESETS]
    for entry in body:
        assert set(entry["tokens"]) >= REQUIRED_TOKENS


def test_unknown_theme_is_rejected_on_upsert(auth_client: TestClient) -> None:
    response = auth_client.put(ADMIN_SETTINGS, json=settings_payload(active_theme="neon-hacker"))

    assert response.status_code == 422, response.text
    assert response.json()["error"]["code"] == "validation_error"


def test_unknown_theme_is_rejected_on_patch(auth_client: TestClient) -> None:
    assert_error(auth_client.patch(ADMIN_SETTINGS, json={"active_theme": "neon-hacker"}), 422)


def test_admin_can_select_a_theme(auth_client: TestClient, anonymous_client: TestClient) -> None:
    auth_client.put(ADMIN_SETTINGS, json=settings_payload(active_theme="botanical-calm"))

    assert auth_client.get(ADMIN_SETTINGS).json()["active_theme"] == "botanical-calm"
    assert anonymous_client.get(PUBLIC_SETTINGS).json()["active_theme"] == "botanical-calm"

    resolved = anonymous_client.get(CONFIG).json()["theme"]
    assert resolved["id"] == "botanical-calm"
    assert resolved["tokens"] == dict(THEME_PRESETS[3].tokens)


def test_theme_helpers_agree_with_the_table() -> None:
    assert is_known_theme(DEFAULT_THEME)
    assert not is_known_theme("neon-hacker")
    assert not is_known_theme("")


# --- Fonts --------------------------------------------------------------------


def test_there_are_exactly_five_font_presets() -> None:
    assert len(FONT_PRESETS) == 5


def test_font_presets_are_well_formed() -> None:
    ids = [preset.id for preset in FONT_PRESETS]
    assert len(set(ids)) == len(ids), "font ids must be unique"

    for preset in FONT_PRESETS:
        assert preset.id and preset.name and preset.description
        assert preset.heading_family and preset.body_family
        # The stacks must fall back to a generic family, so a blocked webfont
        # still renders legibly.
        assert "serif" in preset.heading_stack or "sans-serif" in preset.heading_stack
        assert "sans-serif" in preset.body_stack
        assert preset.href.startswith("https://fonts.googleapis.com/css2?")
        assert preset.heading_family in preset.href
        assert preset.body_family in preset.href


def test_public_font_catalogue_lists_every_preset(anonymous_client: TestClient) -> None:
    body = anonymous_client.get(FONTS).json()

    assert [entry["id"] for entry in body] == [preset.id for preset in FONT_PRESETS]
    for entry in body:
        assert entry["heading_stack"] and entry["body_stack"] and entry["href"]


def test_unknown_font_is_rejected(auth_client: TestClient) -> None:
    assert_error(
        auth_client.put(ADMIN_SETTINGS, json=settings_payload(active_font="comic-sans")), 422
    )
    assert_error(auth_client.patch(ADMIN_SETTINGS, json={"active_font": "comic-sans"}), 422)


def test_admins_cannot_supply_an_arbitrary_font_url(auth_client: TestClient) -> None:
    """There is no field through which a font URL could be stored."""
    for payload in (
        {"active_font": "https://evil.example.com/font.css"},
        {"font_url": "https://evil.example.com/font.css"},
        {"active_font": "evil', url(javascript:alert(1))"},
    ):
        assert_error(auth_client.patch(ADMIN_SETTINGS, json=payload), 422)


def test_admin_can_select_a_font(anonymous_client: TestClient, auth_client: TestClient) -> None:
    auth_client.put(ADMIN_SETTINGS, json=settings_payload(active_font="bodoni-inter"))

    resolved = anonymous_client.get(CONFIG).json()["font"]
    assert resolved["id"] == "bodoni-inter"
    assert resolved["heading_family"] == "Bodoni Moda"
    assert resolved["body_family"] == "Inter"
    assert "Bodoni Moda" in resolved["href"]


def test_font_helpers_agree_with_the_table() -> None:
    assert is_known_font(DEFAULT_FONT)
    assert not is_known_font("comic-sans")


# --- Public configuration -----------------------------------------------------


def test_public_config_exposes_the_active_theme_and_font(
    anonymous_client: TestClient, auth_client: TestClient
) -> None:
    auth_client.put(ADMIN_SETTINGS, json=settings_payload())

    body = anonymous_client.get(CONFIG).json()

    assert body["theme"]["id"] == "rose-elegance"
    assert body["font"]["id"] == "playfair-lora"
    assert body["theme"]["tokens"]["primary"].startswith("#")
    assert body["font"]["heading_stack"]


def test_public_config_carries_identity_contact_and_sections(
    anonymous_client: TestClient, auth_client: TestClient
) -> None:
    auth_client.put(ADMIN_SETTINGS, json=settings_payload())

    body = anonymous_client.get(CONFIG).json()

    assert body["identity"]["business_name"] == "Glow Studio"
    assert body["identity"]["tagline"]
    assert body["identity"]["logo"] == "https://cdn.example.com/logo.png"
    assert body["contact"]["phone"]
    assert body["contact"]["whatsapp_number"]
    assert body["social_links"]["instagram"]
    assert body["hero"]["title"] == "Welcome"
    assert body["hero"]["cta_text"] == "Book now"
    assert body["hero"]["cta_behaviour"] == "book"
    assert body["about"]["title"] == "About us"
    assert body["about"]["image"] == "https://cdn.example.com/about.jpg"


def test_public_config_is_available_without_any_settings(auth_client: TestClient) -> None:
    """A cold installation still returns a renderable configuration."""
    body = auth_client.get(CONFIG).json()

    assert body["identity"]["business_name"]
    assert body["theme"]["id"] == DEFAULT_THEME
    assert body["font"]["id"] == DEFAULT_FONT


@pytest.mark.parametrize(
    "secret",
    [
        "unit-test-secret-value-not-a-real-credential",
        "test-secret-access-key",
        "test-access-key-id",
        "mongodb://",
        "smtp",
    ],
)
def test_public_config_never_leaks_secrets(
    anonymous_client: TestClient, auth_client: TestClient, secret: str
) -> None:
    auth_client.put(ADMIN_SETTINGS, json=settings_payload())

    assert secret not in anonymous_client.get(CONFIG).text


def test_public_config_does_not_expose_internal_fields(anonymous_client: TestClient) -> None:
    body = anonymous_client.get(CONFIG).json()

    for internal in ("singleton_key", "password_hash", "created_at", "updated_at"):
        assert internal not in body


def test_unknown_stored_theme_falls_back_instead_of_erroring(
    anonymous_client: TestClient, auth_client: TestClient
) -> None:
    """A document written outside the API degrades to the default preset.

    Covers a record that predates the preset table, or one edited directly in the
    database: a styling regression beats a 500 on the public config endpoint.
    This is why the curated list is enforced on write, not on read.
    """
    auth_client.put(ADMIN_SETTINGS, json=settings_payload(active_theme="botanical-calm"))
    database = client_and_database(auth_client)[1]
    run(
        database["site_settings"].update_one(
            {"singleton_key": "site_settings"}, {"$set": {"active_theme": "legacy-theme"}}
        )
    )

    body = anonymous_client.get(CONFIG).json()
    assert body["theme"]["id"] == DEFAULT_THEME
    assert body["theme"]["tokens"] == dict(THEME_PRESETS[0].tokens)


# --- Custom colour overrides --------------------------------------------------


def test_admin_can_override_theme_colours(
    auth_client: TestClient, anonymous_client: TestClient
) -> None:
    auth_client.patch(
        ADMIN_SETTINGS,
        json={"theme_overrides": {"primary": "#123456", "button_bg": "#654321"}},
    )

    assert auth_client.get(ADMIN_SETTINGS).json()["theme_overrides"] == {
        "primary": "#123456",
        "button_bg": "#654321",
    }

    tokens = anonymous_client.get(CONFIG).json()["theme"]["tokens"]
    assert tokens["primary"] == "#123456"
    assert tokens["button_bg"] == "#654321"
    # Untouched tokens still resolve from the curated preset.
    assert tokens["text"] == THEME_PRESETS[0].tokens["text"]


def test_override_of_unknown_token_is_rejected(auth_client: TestClient) -> None:
    assert_error(
        auth_client.patch(ADMIN_SETTINGS, json={"theme_overrides": {"font_family": "#123456"}}),
        422,
    )


def test_override_of_non_hex_value_is_rejected(auth_client: TestClient) -> None:
    for value in ("red", "#12345", "#12345g", "url(https://evil.example/x)", "#fff;color:red"):
        assert_error(
            auth_client.patch(ADMIN_SETTINGS, json={"theme_overrides": {"primary": value}}),
            422,
        )


def test_admin_can_reset_overrides(
    auth_client: TestClient, anonymous_client: TestClient
) -> None:
    auth_client.patch(ADMIN_SETTINGS, json={"theme_overrides": {"primary": "#123456"}})
    auth_client.patch(ADMIN_SETTINGS, json={"theme_overrides": {}})

    assert auth_client.get(ADMIN_SETTINGS).json()["theme_overrides"] == {}
    assert anonymous_client.get(CONFIG).json()["theme"]["tokens"] == dict(THEME_PRESETS[0].tokens)


def test_invalid_stored_override_is_ignored_on_read(
    auth_client: TestClient, anonymous_client: TestClient
) -> None:
    """Defence in depth: the public endpoint filters what the write boundary rejects."""
    auth_client.put(ADMIN_SETTINGS, json=settings_payload())
    database = client_and_database(auth_client)[1]
    run(
        database["site_settings"].update_one(
            {"singleton_key": "site_settings"},
            {"$set": {"theme_overrides": {"primary": "not-a-colour", "nonsense": "#ffffff"}}},
        )
    )

    assert anonymous_client.get(CONFIG).json()["theme"]["tokens"] == dict(THEME_PRESETS[0].tokens)


# --- Contact and hero validation ----------------------------------------------


def test_phone_validation_rejects_markup(auth_client: TestClient) -> None:
    assert_error(
        auth_client.patch(ADMIN_SETTINGS, json={"phone": "<script>alert(1)</script>"}), 422
    )
    assert_error(
        auth_client.patch(ADMIN_SETTINGS, json={"whatsapp_number": "javascript:alert(1)"}), 422
    )


def test_phone_validation_accepts_real_formats(auth_client: TestClient) -> None:
    for value in ("+91 90000 00000", "(020) 7946-0958", "+1.555.123.4567"):
        assert auth_client.patch(ADMIN_SETTINGS, json={"phone": value}).status_code == 200, value


def test_media_references_must_be_absolute_urls(auth_client: TestClient) -> None:
    """A media field must point at something a browser can load."""
    for field in ("logo", "favicon", "about_image", "hero_image"):
        assert_error(auth_client.patch(ADMIN_SETTINGS, json={field: "/local/x.png"}), 422)
        assert_error(auth_client.patch(ADMIN_SETTINGS, json={field: "file:///etc/passwd"}), 422)


def test_hero_cta_behaviour_is_a_closed_set(auth_client: TestClient) -> None:
    assert (
        auth_client.patch(ADMIN_SETTINGS, json={"hero_cta_behaviour": "gallery"}).status_code == 200
    )
    assert_error(auth_client.patch(ADMIN_SETTINGS, json={"hero_cta_behaviour": "download"}), 422)


def test_unknown_write_fields_are_rejected(auth_client: TestClient) -> None:
    """``extra="forbid"`` stops a typo from being silently ignored."""
    assert_error(auth_client.patch(ADMIN_SETTINGS, json={"busines_name": "Typo"}), 422)


# --- Helpers ------------------------------------------------------------------


def assert_error(response: Response, status_code: int) -> None:
    assert response.status_code == status_code, response.text
    assert response.json()["error"]["code"] == "validation_error", response.text


def client_and_database(client: TestClient) -> tuple[TestClient, AsyncMock]:
    """The test's in-memory database, for bypassing API validation on purpose."""
    from app.api.deps import get_database
    from app.main import app

    return client, app.dependency_overrides[get_database]()


def run(awaitable: Awaitable[object]) -> object:
    """Drive one async operation to completion from a synchronous test."""
    return asyncio.run(_await(awaitable))  # type: ignore[arg-type]


async def _await(awaitable: Awaitable[object]) -> object:
    return await awaitable
