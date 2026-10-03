"""Router assembly for API v1.

Four routers are exposed separately so the public surface can never be confused
with the management surface:

* ``health_router``  -> ``/api/health``          (unauthenticated, liveness only)
* ``auth_router``    -> ``/api/v1/auth/...``    (login, logout, password reset)
* ``public_router``  -> ``/api/v1/public/...``  (read-only, unauthenticated)
* ``admin_router``   -> ``/api/v1/admin/...``   (CRUD, **authentication required**)

``admin_router`` is created with ``dependencies=[Depends(get_current_admin)]``
rather than repeating the dependency in every handler. That is what makes the
rule "every admin route requires a session" structural instead of something each
endpoint has to remember - and it means a new admin route is protected the
moment it is written, with no window in which it ships unauthenticated.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps_auth import get_current_admin
from app.api.v1.routes import auth as auth_routes
from app.api.v1.routes import health
from app.api.v1.routes.admin import (
    gallery as admin_gallery,
)
from app.api.v1.routes.admin import (
    media as admin_media,
)
from app.api.v1.routes.admin import (
    offers as admin_offers,
)
from app.api.v1.routes.admin import (
    services as admin_services,
)
from app.api.v1.routes.admin import (
    site_settings as admin_site_settings,
)
from app.api.v1.routes.admin import (
    testimonials as admin_testimonials,
)
from app.api.v1.routes.public import config as public_config
from app.api.v1.routes.public import gallery as public_gallery
from app.api.v1.routes.public import offers as public_offers
from app.api.v1.routes.public import services as public_services
from app.api.v1.routes.public import site_settings as public_site_settings
from app.api.v1.routes.public import testimonials as public_testimonials

health_router = APIRouter()
health_router.include_router(health.router)

public_router = APIRouter()
public_router.include_router(public_config.router)
public_router.include_router(public_site_settings.router)
public_router.include_router(public_services.router)
public_router.include_router(public_gallery.router)
public_router.include_router(public_testimonials.router)
public_router.include_router(public_offers.router)

#: Unauthenticated by design: the client needs it *before* it has a session.
auth_router = APIRouter()
auth_router.include_router(auth_routes.router)

#: Every route below inherits the dependency. State-changing requests additionally
#: pass the CSRF double-submit check performed inside ``get_current_admin``.
admin_router = APIRouter(dependencies=[Depends(get_current_admin)])
admin_router.include_router(admin_site_settings.router)
admin_router.include_router(admin_services.router)
admin_router.include_router(admin_gallery.router)
admin_router.include_router(admin_media.router)
admin_router.include_router(admin_testimonials.router)
admin_router.include_router(admin_offers.router)

#: The four routers above are mounted explicitly by ``app.main.create_app``.
#: There is deliberately no combined ``api_router`` alias: a single aggregate
#: would hide which prefixes carry the admin dependency, and aliasing one of them
#: (as ``api_router = health_router`` once did) would mount health and nothing
#: else without any error.
