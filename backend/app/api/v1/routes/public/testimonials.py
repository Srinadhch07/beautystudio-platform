"""Public testimonial endpoints.

``GET /testimonials`` can only ever return approved **and** visible items: the
filter lives in ``app.models.testimonial.PUBLIC_FILTER`` and is applied by
``TestimonialsRepository.list_public``. Moderation fields are omitted from the
response schema.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import TestimonialServiceDependency
from app.core.parsing import parse_object_id
from app.schemas.common import Page, PaginationDependency
from app.schemas.testimonials import TestimonialCreate, TestimonialPublic
from app.services.base import page_to_response, to_response

router = APIRouter(tags=["public: testimonials"])


@router.get(
    "/testimonials",
    response_model=Page[TestimonialPublic],
    summary="List approved, visible testimonials",
)
async def list_testimonials(
    params: PaginationDependency,
    service: TestimonialServiceDependency,
) -> Page[TestimonialPublic]:
    page = await service.list_public(skip=params.skip, limit=params.limit)
    return page_to_response(page, TestimonialPublic)


@router.get(
    "/testimonials/{testimonial_id}",
    response_model=TestimonialPublic,
    summary="Read a single approved, visible testimonial",
)
async def read_testimonial(
    testimonial_id: str,
    service: TestimonialServiceDependency,
) -> TestimonialPublic:
    """Return one public testimonial, or 404 when it is not public."""
    document = await service.get_public(parse_object_id(testimonial_id, field="testimonial_id"))
    return to_response(document, TestimonialPublic)


@router.post(
    "/testimonials",
    response_model=TestimonialPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a testimonial",
    description=(
        "New submissions are always stored as pending and invisible; they only "
        "appear publicly after an administrator approves them."
    ),
)
async def submit_testimonial(
    payload: TestimonialCreate,
    service: TestimonialServiceDependency,
) -> TestimonialPublic:
    document = await service.submit(payload)
    return to_response(document, TestimonialPublic)
