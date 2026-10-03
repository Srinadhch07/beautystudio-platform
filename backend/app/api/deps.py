"""Shared FastAPI dependencies.

The dependency chain is deliberately linear::

    route -> service -> repository -> AsyncDatabase

Tests override :func:`get_database` once and every repository and service is
rebuilt against the in-memory database automatically.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from pymongo.asynchronous.database import AsyncDatabase

from app.core.config import Settings, get_settings
from app.db import mongo
from app.repositories.admins import AdminsRepository
from app.repositories.gallery import GalleryRepository
from app.repositories.offers import OffersRepository
from app.repositories.services import ServicesRepository
from app.repositories.site_settings import SiteSettingsRepository
from app.repositories.testimonials import TestimonialsRepository
from app.services.gallery import GalleryService
from app.services.media import MediaService
from app.services.offers import OfferService
from app.services.services import ServiceService
from app.services.site_settings import SiteSettingsService
from app.services.testimonials import TestimonialService
from app.storage.s3 import S3StorageService

Document = dict[str, object]


def get_settings_dependency() -> Settings:
    """Inject the settings singleton."""
    return get_settings()


SettingsDependency = Annotated[Settings, Depends(get_settings_dependency)]


def get_database() -> AsyncDatabase[Document]:
    """Return the application database handle."""
    return mongo.get_database(get_settings())


DatabaseDependency = Annotated[AsyncDatabase[Document], Depends(get_database)]


# -- Repositories ------------------------------------------------------------


def get_site_settings_repository(
    database: DatabaseDependency,
) -> SiteSettingsRepository:
    return SiteSettingsRepository(database)


def get_services_repository(database: DatabaseDependency) -> ServicesRepository:
    return ServicesRepository(database)


def get_gallery_repository(database: DatabaseDependency) -> GalleryRepository:
    return GalleryRepository(database)


def get_testimonials_repository(database: DatabaseDependency) -> TestimonialsRepository:
    return TestimonialsRepository(database)


def get_offers_repository(database: DatabaseDependency) -> OffersRepository:
    return OffersRepository(database)


def get_admins_repository(database: DatabaseDependency) -> AdminsRepository:
    return AdminsRepository(database)


# -- Services ----------------------------------------------------------------


def get_site_settings_service(
    repository: Annotated[SiteSettingsRepository, Depends(get_site_settings_repository)],
    settings: SettingsDependency,
) -> SiteSettingsService:
    return SiteSettingsService(repository, settings)


def get_service_service(
    repository: Annotated[ServicesRepository, Depends(get_services_repository)],
) -> ServiceService:
    return ServiceService(repository)


def get_gallery_service(
    repository: Annotated[GalleryRepository, Depends(get_gallery_repository)],
) -> GalleryService:
    return GalleryService(repository)


def get_s3_storage_service(settings: SettingsDependency) -> S3StorageService:
    """Inject the S3 storage service.

    The boto3 client is built lazily inside the service, so constructing this
    dependency performs no network or credential work. Tests override this
    dependency with an instance carrying a stand-in client, which is what keeps
    the suite from ever reaching a real bucket.
    """
    return S3StorageService(settings)


def get_media_service(
    repository: Annotated[GalleryRepository, Depends(get_gallery_repository)],
    gallery: Annotated[GalleryService, Depends(get_gallery_service)],
    storage: Annotated[S3StorageService, Depends(get_s3_storage_service)],
    settings: SettingsDependency,
) -> MediaService:
    return MediaService(repository, gallery, storage, settings)


def get_testimonial_service(
    repository: Annotated[TestimonialsRepository, Depends(get_testimonials_repository)],
) -> TestimonialService:
    return TestimonialService(repository)


def get_offer_service(
    repository: Annotated[OffersRepository, Depends(get_offers_repository)],
) -> OfferService:
    return OfferService(repository)


# -- Convenience aliases -----------------------------------------------------

SiteSettingsServiceDependency = Annotated[SiteSettingsService, Depends(get_site_settings_service)]
ServiceServiceDependency = Annotated[ServiceService, Depends(get_service_service)]
GalleryServiceDependency = Annotated[GalleryService, Depends(get_gallery_service)]
S3StorageServiceDependency = Annotated[S3StorageService, Depends(get_s3_storage_service)]
MediaServiceDependency = Annotated[MediaService, Depends(get_media_service)]
TestimonialServiceDependency = Annotated[TestimonialService, Depends(get_testimonial_service)]
OfferServiceDependency = Annotated[OfferService, Depends(get_offer_service)]
