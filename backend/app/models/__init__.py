"""MongoDB document models.

Submodules are imported explicitly (never via ``from app.models import *``) so
that ``app.models.base`` keeps a single, obvious source of truth for the
``PyObjectId`` / ``Price`` primitives shared by every document:

* :mod:`app.models.base` - identifiers, money, BSON conversion, timestamps
* :mod:`app.models.collections` - collection names and index definitions
* :mod:`app.models.admin` - admin account document (no auth routes yet)
* :mod:`app.models.site_settings` - the single business-wide settings document
* :mod:`app.models.service` - catalogue item
* :mod:`app.models.gallery` - gallery image
* :mod:`app.models.testimonial` - customer review plus moderation state
* :mod:`app.models.offer` - promotional package
"""
