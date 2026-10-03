"""Service (catalog item) business logic."""

from __future__ import annotations

from app.models.service import ServiceDocument
from app.repositories.services import ServicesRepository
from app.schemas.services import ServiceCreate, ServiceUpdate
from app.services.base import CatalogService


class ServiceService(CatalogService[ServiceDocument, ServiceCreate, ServiceUpdate]):
    """Create, update, order, activate and delete parlour services."""

    resource_label = "Service"
    document_type = ServiceDocument

    def __init__(self, repository: ServicesRepository) -> None:
        super().__init__(repository)
        self._services = repository
