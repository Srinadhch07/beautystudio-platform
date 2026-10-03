"""Shared payload builders.

Keeping the payloads here means a schema change surfaces as one obvious edit
instead of dozens of test failures.
"""

from __future__ import annotations

from typing import Any


def service_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "name": "Hair Spa",
        "description": "Deep conditioning treatment.",
        "price": "49.99",
        "category": "Hair",
        "duration": 60,
        "is_active": True,
        "display_order": 0,
    }
    return {**payload, **overrides}


def gallery_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Bridal Makeup",
        "description": "Bridal trial look.",
        "image_url": "https://cdn.example.com/gallery/bridal.jpg",
        # Shaped like a real upload key: media/{category}/{32 hex}.{ext}. The
        # gallery schema rejects anything else, because this names a real object.
        "s3_key": f"media/gallery/{'a1b2c3d4e5f6a7b8' * 2}.jpg",
        "category": "Bridal",
        "is_active": True,
        "display_order": 0,
    }
    return {**payload, **overrides}


def review_payload(**overrides: Any) -> dict[str, Any]:
    """Testimonial submission body.

    Deliberately not named ``testimonial_*``: pytest would collect any imported
    callable whose name starts with ``test`` as a test case.
    """
    payload: dict[str, Any] = {
        "customer_name": "Priya",
        "content": "Wonderful service and very friendly staff.",
        "rating": 5,
    }
    return {**payload, **overrides}


def offer_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "title": "Bridal Package",
        "description": "Makeup, hair and draping.",
        "price": "499.00",
        "original_price": "650.00",
        "is_active": True,
        "display_order": 0,
    }
    return {**payload, **overrides}


def settings_payload(**overrides: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "business_name": "Glow Studio",
        "tagline": "Look and feel beautiful",
        "description": "A premium beauty parlour.",
        "logo": "https://cdn.example.com/logo.png",
        "favicon": "https://cdn.example.com/favicon.png",
        "phone": "+91 98765 43210",
        "whatsapp_number": "+91 98765 43210",
        "email": "hello@glowstudio.com",
        "address": {
            "line1": "12 Rose Street",
            "city": "Chennai",
            "state": "Tamil Nadu",
            "postal_code": "600001",
            "country": "India",
        },
        "opening_hours": [
            {"day": "monday", "is_closed": False, "open_time": "10:00", "close_time": "19:00"},
            {"day": "sunday", "is_closed": True},
        ],
        "social_links": {
            "facebook": "https://facebook.com/glowstudio",
            "instagram": "https://instagram.com/glowstudio",
        },
        "about_title": "About us",
        "about_content": "Ten years of beauty expertise.",
        "about_image": "https://cdn.example.com/about.jpg",
        "hero_title": "Welcome",
        "hero_description": "Book your appointment today.",
        "hero_image": "https://cdn.example.com/hero.jpg",
        "hero_cta_text": "Book now",
        "hero_cta_url": "https://beautyparlour.app/booking",
        "hero_cta_behaviour": "book",
        "active_theme": "rose-elegance",
        "active_font": "playfair-lora",
    }
    return {**payload, **overrides}
