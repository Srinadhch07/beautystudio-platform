"""Admin testimonial moderation."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from app.api.deps import TestimonialServiceDependency
from app.core.parsing import parse_object_id
from app.models.testimonial import TestimonialStatus
from app.schemas.common import Page, PaginationDependency
from app.schemas.testimonials import (
    TestimonialAdmin,
    TestimonialAdminCreate,
    TestimonialModeration,
    TestimonialUpdate,
)
from app.services.base import page_to_response, to_response

router = APIRouter(prefix="/testimonials", tags=["admin: testimonials"])


def get_status_filter(
    status_filter: Annotated[
        TestimonialStatus | None,
        Query(alias="status", description="Filter by moderation status."),
    ] = None,
) -> TestimonialStatus | None:
    return status_filter


StatusFilter = Annotated[TestimonialStatus | None, Depends(get_status_filter)]


@router.get(
    "",
    response_model=Page[TestimonialAdmin],
    summary="List testimonials for moderation",
)
async def list_testimonials(
    params: PaginationDependency,
    service: TestimonialServiceDependency,
    status_filter: StatusFilter,
) -> Page[TestimonialAdmin]:
    page = await service.list_for_moderation(
        status=status_filter, skip=params.skip, limit=params.limit
    )
    return page_to_response(page, TestimonialAdmin)


@router.post(
    "",
    response_model=TestimonialAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Create a testimonial",
)
async def create_testimonial(
    payload: TestimonialAdminCreate,
    service: TestimonialServiceDependency,
) -> TestimonialAdmin:
    """Create a review with an explicit moderation state (e.g. taken in person)."""
    created = await service.create_with_moderation(payload)
    return to_response(created, TestimonialAdmin)


@router.get(
    "/{testimonial_id}",
    response_model=TestimonialAdmin,
    summary="Read any testimonial",
)
async def read_testimonial(
    testimonial_id: str,
    service: TestimonialServiceDependency,
) -> TestimonialAdmin:
    document = await service.get(parse_object_id(testimonial_id, field="testimonial_id"))
    return to_response(document, TestimonialAdmin)


@router.patch(
    "/{testimonial_id}/moderate",
    response_model=TestimonialAdmin,
    summary="Approve, reject or hide a testimonial",
)
async def moderate_testimonial(
    testimonial_id: str,
    payload: TestimonialModeration,
    service: TestimonialServiceDependency,
) -> TestimonialAdmin:
    document = await service.moderate(
        parse_object_id(testimonial_id, field="testimonial_id"), payload
    )
    return to_response(document, TestimonialAdmin)


@router.patch(
    "/{testimonial_id}",
    response_model=TestimonialAdmin,
    summary="Edit testimonial content",
)
async def update_testimonial(
    testimonial_id: str,
    payload: TestimonialUpdate,
    service: TestimonialServiceDependency,
) -> TestimonialAdmin:
    """Edit the wording or rating without touching the moderation state."""
    document = await service.update(
        parse_object_id(testimonial_id, field="testimonial_id"), payload
    )
    return to_response(document, TestimonialAdmin)


@router.delete(
    "/{testimonial_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a testimonial",
)
async def delete_testimonial(
    testimonial_id: str,
    service: TestimonialServiceDependency,
) -> Response:
    await service.delete(parse_object_id(testimonial_id, field="testimonial_id"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
