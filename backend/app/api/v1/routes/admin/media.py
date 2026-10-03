"""Admin media management (upload, metadata edits, deletion).

Every route here inherits ``Depends(get_current_admin)`` from ``admin_router``, so
a session is required and, for state-changing verbs, a valid CSRF header.

``POST /media`` is the file-aware counterpart to the metadata-only
``POST /gallery``: both write to the same collection, but only this one accepts
a binary upload and derives the object key and content type itself.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, File, Form, Response, UploadFile, status

from app.api.deps import MediaServiceDependency
from app.core.errors import HTTP_413
from app.core.media import DEFAULT_MEDIA_CATEGORY, read_upload_limited
from app.core.parsing import parse_object_id
from app.models.service import MAX_DISPLAY_ORDER
from app.schemas.gallery import GalleryAdmin, MediaMetadataUpdate
from app.services.base import to_response

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/media", tags=["admin: media"])


@router.post(
    "",
    response_model=GalleryAdmin,
    status_code=status.HTTP_201_CREATED,
    summary="Upload an image",
    responses={
        HTTP_413: {"description": "File too large"},
        status.HTTP_415_UNSUPPORTED_MEDIA_TYPE: {"description": "Unsupported file type"},
    },
)
async def upload_media(
    service: MediaServiceDependency,
    file: UploadFile = File(description="JPEG, PNG or WebP image"),
    title: str = Form(min_length=1, max_length=160),
    description: str | None = Form(default=None, max_length=1000),
    category: str = Form(default=DEFAULT_MEDIA_CATEGORY),
    is_active: bool = Form(default=True),
    display_order: int = Form(default=0, ge=0, le=MAX_DISPLAY_ORDER),
) -> GalleryAdmin:
    """Validate, store in S3, and record the metadata.

    The file is read with a hard ceiling of ``PRODUCT_IMAGE_MAX_BYTES`` before
    any validation happens, and the content type recorded in S3 comes from the
    file's own signature rather than from the request.
    """
    data = await read_upload_limited(file, service.max_upload_bytes)
    document = await service.upload(
        data=data,
        filename=file.filename,
        declared_content_type=file.content_type,
        title=title,
        description=description,
        category=category,
        is_active=is_active,
        display_order=display_order,
    )
    return to_response(document, GalleryAdmin)


@router.patch(
    "/{media_id}",
    response_model=GalleryAdmin,
    summary="Update media metadata",
)
async def update_media(
    media_id: str,
    payload: MediaMetadataUpdate,
    service: MediaServiceDependency,
) -> GalleryAdmin:
    """Change title, description, category, visibility or order.

    The image itself is untouched: ``s3_key``, ``image_url`` and the file's
    provenance are not part of this schema, so no re-upload is needed - and no
    request can repoint a record at a different object.
    """
    document = await service.update_metadata(parse_object_id(media_id, field="media_id"), payload)
    return to_response(document, GalleryAdmin)


@router.delete(
    "/{media_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete media and its stored file",
)
async def delete_media(media_id: str, service: MediaServiceDependency) -> Response:
    """Remove the S3 object and then the record.

    Returns 204 only when both succeeded. If the object could not be removed the
    request fails and the record is kept, so nothing is silently lost.
    """
    await service.delete(parse_object_id(media_id, field="media_id"))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
