"""Curated font presets.

Like themes, fonts are selected **by id** from a fixed table. An administrator
cannot supply a font URL, family name or stylesheet link, which closes the
obvious injection path: a curated entry is a static string in this file, so
there is no request-time input that ends up in a ``<link>``.

Each preset pairs a display face for headings with a text face for body copy.
Both are widely available on Google Fonts, and :attr:`FontPreset.href` is built
from the curated family names only.
"""

from __future__ import annotations

from typing import Final, Literal

#: The default pairing for a brand new installation.
DEFAULT_FONT: Final[str] = "playfair-lora"

FontId = Literal[
    "playfair-lora",
    "montserrat-jost",
    "cormorant-karla",
    "bodoni-inter",
    "lora-source",
]

#: Origin for the curated webfont stylesheets. Fixed by the application, never by
#: an administrator.
GOOGLE_FONTS_ORIGIN: Final[str] = "https://fonts.googleapis.com/css2"


class FontPreset:
    """One selectable font pairing."""

    def __init__(
        self,
        id: str,  # noqa: A002 - the field really is called "id" in the API
        name: str,
        description: str,
        heading_family: str,
        body_family: str,
        heading_weights: tuple[int, ...] = (400, 500, 600, 700),
        body_weights: tuple[int, ...] = (300, 400, 500, 600),
    ) -> None:
        self.id = id
        self.name = name
        self.description = description
        self.heading_family = heading_family
        self.body_family = body_family
        self.heading_weights = heading_weights
        self.body_weights = body_weights

    @property
    def heading_stack(self) -> str:
        """CSS ``font-family`` stack for headings."""
        return f"'{self.heading_family}', Georgia, 'Times New Roman', serif"

    @property
    def body_stack(self) -> str:
        """CSS ``font-family`` stack for body copy."""
        return (
            f"'{self.body_family}', -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
        )

    @property
    def href(self) -> str:
        """Stylesheet URL built from the curated family names.

        Assembled here rather than stored, so the URL can never drift from the
        families the rest of the preset reports.
        """
        families = [
            f"{self.heading_family}:wght@{';'.join(str(w) for w in self.heading_weights)}",
            f"{self.body_family}:wght@{';'.join(str(w) for w in self.body_weights)}",
        ]
        return f"{GOOGLE_FONTS_ORIGIN}?family={'+'.join(families)}&display=swap"

    def as_dict(self) -> dict[str, object]:
        """Public, credential-free representation."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "heading_family": self.heading_family,
            "body_family": self.body_family,
            "heading_stack": self.heading_stack,
            "body_stack": self.body_stack,
            "href": self.href,
        }


#: Exactly five pairings. The count is asserted in the test suite: this is a
#: curated shortlist, not a growing registry.
FONT_PRESETS: Final[tuple[FontPreset, ...]] = (
    FontPreset(
        id="playfair-lora",
        name="Playfair & Lora",
        description="High-contrast serif headings with a warm, readable serif body.",
        heading_family="Playfair Display",
        body_family="Lora",
    ),
    FontPreset(
        id="montserrat-jost",
        name="Montserrat & Jost",
        description="Clean geometric sans throughout. Modern and minimal.",
        heading_family="Montserrat",
        body_family="Jost",
    ),
    FontPreset(
        id="cormorant-karla",
        name="Cormorant & Karla",
        description="Delicate display serif with a light grotesque body. Very luxe.",
        heading_family="Cormorant Garamond",
        body_family="Karla",
    ),
    FontPreset(
        id="bodoni-inter",
        name="Bodoni & Inter",
        description="Sharp didone headings with a neutral UI sans. Editorial and bold.",
        heading_family="Bodoni Moda",
        body_family="Inter",
    ),
    FontPreset(
        id="lora-source",
        name="Lora & Source Sans",
        description="Classic literary serif headings with an accessible sans body.",
        heading_family="Lora",
        body_family="Source Sans 3",
    ),
)

FONTS_BY_ID: Final[dict[str, FontPreset]] = {preset.id: preset for preset in FONT_PRESETS}

FONT_CATALOGUE: Final[tuple[dict[str, object], ...]] = tuple(
    preset.as_dict() for preset in FONT_PRESETS
)


def is_known_font(value: str) -> bool:
    """``True`` when ``value`` names a curated preset."""
    return value in FONTS_BY_ID


def get_font(value: str) -> FontPreset:
    """Return a preset by id.

    Raises :class:`KeyError` if the id is unknown; callers at an API boundary
    should validate first so the failure is a 422 rather than a 500.
    """
    return FONTS_BY_ID[value]


def available_font_ids() -> tuple[str, ...]:
    """Sorted ids, for schema error messages."""
    return tuple(sorted(FONTS_BY_ID))
