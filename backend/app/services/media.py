"""Media upload, deletion and metadata maintenance.

This layer owns the ordering between the two stores involved in a media
operation, and that ordering is the whole design problem:

* An upload writes to **S3 first**, then to **MongoDB**. S3 cannot be rolled
  back, MongoDB can, so the store that must compensate is the one written last.
  If the insert fails, the uploaded object is deleted before the error is
  re-raised - a failed request never leaves an orphan object behind.
* A delete removes the **S3 object first**, then the **document**. The reverse
  order would drop the only record of the key while the object survived. When
  the S3 delete fails the request fails *and the document is kept*, so the
  failure is visible and retryable instead of becoming a silent orphan.

Both stores are therefore involved in every destructive operation, and neither
path reports success unless both halves succeeded.
"""

from __future__ import annotations

import logging
from uuid import uuid4

from bson import ObjectId

from app.core.config import Settings
from app.core.errors import (
    NotFoundError,
    StorageError,
    StorageNotConfiguredError,
)
from app.core.media import (
    build_object_key,
    is_safe_object_key,
    sanitise_original_filename,
    validate_image_bytes,
    validate_media_category,
)
from app.models.gallery import MAX_ORIGINAL_FILENAME_LENGTH, GalleryDocument
from app.repositories.gallery import GalleryRepository
from app.schemas.gallery import GalleryUpdate, MediaMetadataUpdate
from app.services.gallery import GalleryService
from app.storage.s3 import S3StorageService

logger = logging.getLogger(__name__)

#: Noun used in 404 messages for media operations.
MEDIA_LABEL = "Media item"


class MediaService:
    """Coordinate S3 and MongoDB for a single media record."""

    def __init__(
        self,
        repository: GalleryRepository,
        gallery: GalleryService,
        storage: S3StorageService,
        settings: Settings,
    ) -> None:
        self._repository = repository
        self._gallery = gallery
        self._storage = storage
        self._settings = settings

    # -- Guards --------------------------------------------------------------

    def _require_s3_mode(self) -> None:
        """Refuse to touch a bucket when storage is not in S3 mode.

        ``STORAGE_MODE=local`` means an operator has deliberately pointed the
        application away from the cloud bucket. Silently using S3 anyway would
        write to the production bucket from a development machine, so this fails
        loudly instead. A local backend is a later phase.
        """
        if self._settings.storage_mode != "s3":
            raise StorageNotConfiguredError(
                f"Media uploads require STORAGE_MODE=s3 (currently "
                f"'{self._settings.storage_mode}')."
            )

    @property
    def _max_bytes(self) -> int:
        return self._settings.product_image_max_bytes

    @property
    def max_upload_bytes(self) -> int:
        """Largest accepted upload, for the route's bounded read.

        Exposed so the size limit is applied while streaming, not after the
        whole body has been buffered.
        """
        return self._settings.product_image_max_bytes

    # -- Create --------------------------------------------------------------

    async def upload(
        self,
        *,
        data: bytes,
        filename: str | None,
        declared_content_type: str | None,
        title: str,
        description: str | None = None,
        category: str | None = None,
        is_active: bool = True,
        display_order: int = 0,
    ) -> GalleryDocument:
        """Validate, upload, then record. Undoes the upload if the record fails."""
        self._require_s3_mode()

        image = validate_image_bytes(
            data,
            declared_content_type=declared_content_type,
            max_bytes=self._max_bytes,
        )
        resolved_category = validate_media_category(category)
        # uuid4 hex: collision-safe, and reveals nothing about the upload.
        object_key = build_object_key(resolved_category, image.extension, token=uuid4().hex)

        public_url = await self._storage.upload(object_key, data, image.content_type)

        document = GalleryDocument(
            title=title,
            description=description,
            category=resolved_category,
            image_url=public_url,
            s3_key=object_key,
            content_type=image.content_type,
            file_size=image.size_bytes,
            original_filename=sanitise_original_filename(
                filename, max_length=MAX_ORIGINAL_FILENAME_LENGTH
            ),
            is_active=is_active,
            display_order=display_order,
        )

        try:
            return await self._repository.create(document)
        except Exception as db_error:
            # Compensating action: the object exists in S3 but nothing points at
            # it, so it would never be reachable or deletable through the API.
            logger.error(
                "Media record insert failed; removing uploaded object %r",
                object_key,
                exc_info=True,
            )
            try:
                await self._storage.delete(object_key)
            except Exception:
                # The cleanup is best effort and must not mask the real failure.
                # Re-raising this instead would tell the client the storage
                # misbehaved when the actual problem is the database write, and
                # would hide the stranded object. It is logged at ERROR so an
                # operator can reconcile it.
                logger.error(
                    "Could not remove orphaned object %r after a failed record insert; "
                    "it must be deleted manually",
                    object_key,
                    exc_info=True,
                )
            raise db_error

    # -- Update --------------------------------------------------------------

    async def update_metadata(
        self, media_id: ObjectId, payload: MediaMetadataUpdate
    ) -> GalleryDocument:
        """Apply descriptive changes without touching the stored file.

        The update is handed to :class:`GalleryService` so the merge, the
        cross-field revalidation and the 404 behaviour stay in one place rather
        than being re-implemented here. ``MediaMetadataUpdate`` has already
        rejected any attempt to edit the object key or the file's provenance.
        """
        changes = payload.model_dump(exclude_unset=True)
        if not changes:
            # Nothing to change is not an error, but it must still 404 on an
            # unknown id rather than reporting success for a record that is not
            # there.
            return await self._gallery.get(media_id)
        return await self._gallery.update(media_id, GalleryUpdate.model_validate(changes))

    # -- Delete --------------------------------------------------------------

    async def delete(self, media_id: ObjectId) -> None:
        """Remove the object, then the record.

        A failure in either store raises, and in the S3 case the record is left
        in place: the caller is told the deletion did not happen, and retrying is
        possible because the key is still on file.
        """
        self._require_s3_mode()

        document = await self._gallery.get(media_id)
        object_key = document.s3_key

        if object_key:
            if not is_safe_object_key(object_key):
                # Refuse to act on a key outside the media namespace rather than
                # deleting something the application did not create.
                logger.error(
                    "Refusing to delete media %s: object key %r is outside the media namespace",
                    media_id,
                    object_key,
                )
                raise StorageError("The stored object key is not recognised.")
            # Raises on failure, which leaves the document in place.
            await self._storage.delete(object_key)

        deleted = await self._repository.delete(media_id)
        if not deleted:
            # The object is gone but the row survived: a concurrent delete won
            # the race, or the collection write failed. Surfacing a 404 keeps
            # the API honest about the end state.
            raise NotFoundError(f"{MEDIA_LABEL} not found.")
