"""Curated theme presets.

An administrator picks a theme **by id**. They never type CSS and the backend
never stores arbitrary style text, which is what keeps a compromised admin
session from being able to inject a stylesheet (or a script through a
``url()``) into the public site. A theme is a reference into this fixed table.

The table is the single source of truth: the API exposes it, the site settings
document validates against it, and the frontend renders it. Adding a theme means
adding one entry here and nothing else.

Colour values are curated, not generated, and each palette is checked for
legible text/background pairings rather than being left to chance.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Final, Literal, get_args

#: The default theme for a brand new installation.
DEFAULT_THEME: Final[str] = "rose-elegance"

ThemeId = Literal[
    "rose-elegance",
    "champagne-luxe",
    "warm-nude",
    "botanical-calm",
    "classic-noir",
]


class ThemeTokens(dict[str, str]):
    """A theme's design tokens, as plain strings.

    Values are strings rather than typed colour objects because they are handed
    straight to CSS custom properties by the frontend. ``dict`` keeps the
    document BSON-friendly and JSON-serialisable without conversion.
    """

    def __init__(self, **tokens: str) -> None:
        super().__init__(tokens)

    @property
    def as_css_variables(self) -> dict[str, str]:
        """Tokens keyed as ``--bp-<name>`` for direct use in a stylesheet."""
        return {f"--bp-{name.replace('_', '-')}": value for name, value in self.items()}


class ThemePreset:
    """One selectable theme."""

    def __init__(
        self,
        id: str,  # noqa: A002 - the field really is called "id" in the API
        name: str,
        description: str,
        tokens: ThemeTokens,
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.tokens = tokens

    def as_dict(self) -> dict[str, object]:
        """Public, credential-free representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "tokens": dict(self.tokens),
        }


#: Every available preset, in the order the admin UI should present them.
THEME_PRESETS: Final[tuple[ThemePreset, ...]] = (
    ThemePreset(
        id="rose-elegance",
        name="Rose Elegance",
        description="Soft dusty rose with antique gold. Feminine and classic.",
        tokens=ThemeTokens(
            primary="#B76E79",
            secondary="#E8C4C4",
            accent="#C9A227",
            background="#FDF8F5",
            surface="#FFFFFF",
            text="#2E2426",
            muted_text="#7A6A6D",
            border="#EADCD8",
            button_bg="#B76E79",
            button_text="#FFFFFF",
            button_hover_bg="#9E5B66",
            button_radius="999px",
        ),
    ),
    ThemePreset(
        id="champagne-luxe",
        name="Champagne Luxe",
        description="Cream and champagne gold. Understated, premium, editorial.",
        tokens=ThemeTokens(
            primary="#B08D57",
            secondary="#F3E9DA",
            accent="#8C6D3F",
            background="#FBF7F1",
            surface="#FFFFFF",
            text="#2B2622",
            muted_text="#776C60",
            border="#E8DCC8",
            button_bg="#2B2622",
            button_text="#FDF9F3",
            button_hover_bg="#443B34",
            button_radius="2px",
        ),
    ),
    ThemePreset(
        id="warm-nude",
        name="Warm Nude",
        description="Modern minimal palette in warm beige tones.",
        tokens=ThemeTokens(
            primary="#C89F84",
            secondary="#F0E2D6",
            accent="#7A5C4E",
            background="#FAF5F0",
            surface="#FFFFFF",
            text="#3A2E27",
            muted_text="#857366",
            border="#E7D8CB",
            button_bg="#C89F84",
            button_text="#2B1F19",
            button_hover_bg="#B98F73",
            button_radius="8px",
        ),
    ),
    ThemePreset(
        id="botanical-calm",
        name="Botanical Calm",
        description="Muted sage green. Spa-like, natural and calming.",
        tokens=ThemeTokens(
            primary="#6E8B74",
            secondary="#DCE5DC",
            accent="#A3B18A",
            background="#F6F8F4",
            surface="#FFFFFF",
            text="#26302A",
            muted_text="#6A756D",
            border="#DDE5DB",
            button_bg="#6E8B74",
            button_text="#FFFFFF",
            button_hover_bg="#5B7560",
            button_radius="4px",
        ),
    ),
    ThemePreset(
        id="classic-noir",
        name="Classic Noir",
        description="Charcoal and white. High-contrast, modern, editorial.",
        tokens=ThemeTokens(
            primary="#1C1C1C",
            secondary="#EDEDED",
            accent="#A78B6A",
            background="#FAFAFA",
            surface="#FFFFFF",
            text="#141414",
            muted_text="#6B6B6B",
            border="#E2E2E2",
            button_bg="#1C1C1C",
            button_text="#FFFFFF",
            button_hover_bg="#333333",
            button_radius="0px",
        ),
    ),
)

THEMES_BY_ID: Final[dict[str, ThemePreset]] = {preset.id: preset for preset in THEME_PRESETS}

#: Public listing payload, in presentation order.
THEME_CATALOGUE: Final[tuple[dict[str, object], ...]] = tuple(
    preset.as_dict() for preset in THEME_PRESETS
)

#: Token names an administrator may override with a custom colour. Shape and
#: type are deliberately out of scope: this is a colour picker, so
#: ``button_radius`` and the font stacks stay owned by the curated preset.
OVERRIDABLE_TOKENS: Final[tuple[str, ...]] = (
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
)

#: A standard 3- or 6-digit hex colour. Fully anchored, so a value cannot carry
#: a trailing declaration, a ``url(...)`` or any other CSS text into the
#: custom property the frontend writes.
HEX_COLOR_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6})$"
)


def is_hex_color(value: str) -> bool:
    """``True`` when ``value`` is a standalone 3- or 6-digit hex colour."""
    return isinstance(value, str) and bool(HEX_COLOR_PATTERN.match(value))


def sanitize_overrides(overrides: Mapping[str, str] | None) -> dict[str, str]:
    """Keep only known colour tokens carrying a valid hex value.

    Called on read as well as on write. A document written before this table
    existed, or edited directly in the database, therefore degrades to the
    theme's own colour instead of pushing an arbitrary string into a CSS custom
    property.
    """
    if not overrides:
        return {}
    cleaned: dict[str, str] = {}
    for name, value in overrides.items():
        if name in OVERRIDABLE_TOKENS and is_hex_color(value):
            cleaned[name] = value
    return cleaned


def resolve_theme_tokens(
    preset: ThemePreset, overrides: Mapping[str, str] | None
) -> dict[str, str]:
    """A preset's tokens with an administrator's colour overrides merged on top."""
    tokens = dict(preset.tokens)
    tokens.update(sanitize_overrides(overrides))
    return tokens


def is_known_theme(value: str) -> bool:
    """``True`` when ``value`` names a curated preset."""
    return value in THEMES_BY_ID


def get_theme(value: str) -> ThemePreset:
    """Return a preset by id.

    Raises :class:`KeyError` if the id is unknown; callers at an API boundary
    should validate first so the failure is a 422 rather than a 500.
    """
    return THEMES_BY_ID[value]


def available_theme_ids() -> tuple[str, ...]:
    """Sorted ids, for schema error messages."""
    return tuple(sorted(THEMES_BY_ID))


def theme_id_choices() -> tuple[str, ...]:
    """Ids in presentation order."""
    return tuple(preset.id for preset in THEME_PRESETS)


def known_theme_literals() -> tuple[str, ...]:
    """Literal members of :data:`ThemeId`, kept in step with the table."""
    return get_args(ThemeId)
