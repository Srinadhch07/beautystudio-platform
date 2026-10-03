"""Admin CRUD endpoints.

Mounted under ``/api/v1/admin`` and strictly separate from ``/api/v1/public``.

**Every route here requires authentication.** The protection is attached once, in
:mod:`app.api.v1.router`, by creating ``admin_router`` with
``dependencies=[Depends(get_current_admin)]`` rather than by decorating each
handler. These modules therefore declare no auth code at all, and a newly added
endpoint cannot accidentally ship unauthenticated - it would be refused by the
router before its own handler ran.

State-changing requests additionally pass the CSRF double-submit check that
``get_current_admin`` performs when a session cookie is present.
"""

from app.api.v1.routes.admin import gallery, offers, services, site_settings, testimonials

__all__ = ["gallery", "offers", "services", "site_settings", "testimonials"]
