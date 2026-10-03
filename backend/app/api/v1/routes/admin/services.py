"""Admin service management."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from app.api.deps import ServiceServiceDependency
from app.core.parsing import parse_object_id
from app.schemas.common import Page, PaginationDependency, ReorderRequest, ReorderResponse
from app.schemas.services import ServiceCreate, ServicePublic, ServiceUpdate
from app.services.base import page_to_response, to_response

router = APIRouter(prefix="/services", tags=["admin: services"])


@router.get("", response_model=Page[ServicePublic], summary="List every service")
async def list_services(
    params: PaginationDependency,
    service: ServiceServiceDependency,
) -> Page[ServicePublic]:
    page = await service.list_all(skip=params.skip, limit=params.limit)
    return page_to_response(page, ServicePublic)


# Declared before ``/{service_id}`` so the literal path always wins.
@router.put("/order", response_model=ReorderResponse, summary="Reorder services")
async def reorder_services(
    payload: ReorderRequest,
    service: ServiceServiceDependency,
) -> ReorderResponse:
    return ReorderResponse(updated=await service.reorder(payload))


@router.post(
    "",
    response_model=ServicePublic,
    status_code=status.HTTP_201_CREATED,
    summary="Create a service",
)
async def create_service(
    payload: ServiceCreate,
    service: ServiceServiceDependency,
) -> ServicePublic:
    document = await service.create(payload)
    return to_response(document, ServicePublic)


@router.get("/{service_id}", response_model=ServicePublic, summary="Read a service")
async def read_service(
    service_id: str,
    service: ServiceServiceDependency,
) -> ServicePublic:
    document = await service.get(parse_object_id(service_id, field="service_id"))
    return to_response(document, ServicePublic)


@router.patch("/{service_id}", response_model=ServicePublic, summary="Update a service")
async def update_service(
    service_id: str,
    payload: ServiceUpdate,
    service: ServiceServiceDependency,
) -> ServicePublic:
    document = await service.update(parse_object_id(service_id, field="service_id"), payload)
    return to_response(document, ServicePublic)


@router.patch(
    "/{service_id}/active",
    response_model=ServicePublic,
    summary="Activate or deactivate a service",
)
async def set_service_active(
    service_id: str,
    is_active: bool,
    service: ServiceServiceDependency,
) -> ServicePublic:
    document = await service.set_active(parse_object_id(service_id, field="service_id"), is_active)
    return to_response(document, ServicePublic)


@router.delete(
    "/{service_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a service",
)
async def delete_service(
    service_id: str,
    service: ServiceServiceDependency,
) -> Response:
    await service.delete(parse_object_id(service_id, field="service_id"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
