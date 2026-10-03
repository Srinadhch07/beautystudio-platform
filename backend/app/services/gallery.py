"""Gallery business logic."""

from __future__ import annotations

from app.models.gallery import GalleryDocument
from app.repositories.gallery import GalleryRepository
from app.schemas.gallery import GalleryCreate, GalleryUpdate
from app.services.base import CatalogService


class GalleryService(CatalogService[GalleryDocument, GalleryCreate, GalleryUpdate]):
    """Create, update, order, activate and delete gallery items.

    Image files are not handled yet: ``image_url`` and ``s3_key`` are plain
    references until the upload step lands.
    """

    resource_label = "Gallery item"
    document_type = GalleryDocument

    def __init__(self, repository: GalleryRepository) -> None:
        super().__init__(repository)
