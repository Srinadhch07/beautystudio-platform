"""Public service catalogue."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import ServiceServiceDependency
from app.core.parsing import parse_object_id
from app.schemas.common import Page, PaginationDependency
from app.schemas.services import ServicePublic
from app.services.base import page_to_response, to_response

router = APIRouter(tags=["public: services"])


@router.get(
    "/services",
    response_model=Page[ServicePublic],
    summary="List active services",
)
async def list_services(
    params: PaginationDependency,
    service: ServiceServiceDependency,
) -> Page[ServicePublic]:
    page = await service.list_active(skip=params.skip, limit=params.limit)
    return page_to_response(page, ServicePublic)


@router.get(
    "/services/{service_id}",
    response_model=ServicePublic,
    summary="Read a single active service",
)
async def read_service(
    service_id: str,
    service: ServiceServiceDependency,
) -> ServicePublic:
    document = await service.get_public(parse_object_id(service_id, field="service_id"))
    return to_response(document, ServicePublic)
