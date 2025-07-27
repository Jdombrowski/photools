import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import and_, delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.infrastructure.database import get_db_session
from src.infrastructure.database.models import Collection, CollectionPhoto, Photo

router = APIRouter()
logger = logging.getLogger(__name__)


# Pydantic models for request/response
class CollectionCreate(BaseModel):
    name: str
    description: str | None = None


class CollectionUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    cover_photo_id: str | None = None


class CollectionResponse(BaseModel):
    id: str
    name: str
    description: str | None
    photo_count: int
    cover_photo_id: str | None
    created_at: datetime
    updated_at: datetime | None


class CollectionPhotosRequest(BaseModel):
    photo_ids: list[str]


@router.post("/collections", response_model=CollectionResponse)
async def create_collection(
    collection: CollectionCreate, db: AsyncSession = Depends(get_db_session)
):
    """Create a new collection."""
    new_collection = Collection(
        name=collection.name, description=collection.description
    )

    db.add(new_collection)
    await db.commit()
    await db.refresh(new_collection)

    return pack_collection(new_collection)


@router.get("/collections")
async def list_collections(
    limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db_session)
):
    """List all collections with pagination."""
    # Get total count
    count_stmt = select(func.count(Collection.id))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get collections with pagination
    stmt = (
        select(Collection)
        .order_by(Collection.updated_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    collections = result.scalars().all()

    collections_data = [
        {
            "id": collection.id,
            "name": collection.name,
            "description": collection.description,
            "photo_count": collection.photo_count,
            "cover_photo_id": collection.cover_photo_id,
            "created_at": collection.created_at,
            "updated_at": collection.updated_at,
        }
        for collection in collections
    ]

    return {
        "collections": collections_data,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }


@router.get("/collections/{collection_id}", response_model=CollectionResponse)
async def get_collection(
    collection_id: str, db: AsyncSession = Depends(get_db_session)
):
    """Get collection details by ID."""
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    return pack_collection(collection)


def pack_collection(collection):
    return CollectionResponse(
        id=collection["id"],
        name=collection["name"],
        description=collection["description"],
        photo_count=collection["photo_count"],
        cover_photo_id=collection["cover_photo_id"],
        created_at=collection["created_at"],
        updated_at=collection["updated_at"],
    )


@router.put("/collections/{collection_id}", response_model=CollectionResponse)
async def update_collection(
    collection_id: str,
    collection_update: CollectionUpdate,
    db: AsyncSession = Depends(get_db_session),
):
    """Update collection details."""
    # Check if collection exists
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Prepare update data
    update_data = {}
    if collection_update.name is not None:
        update_data["name"] = collection_update.name
    if collection_update.description is not None:
        update_data["description"] = collection_update.description
    if collection_update.cover_photo_id is not None:
        # Verify cover photo exists and is in the collection
        if collection_update.cover_photo_id:
            cover_photo_stmt = select(CollectionPhoto).where(
                and_(
                    CollectionPhoto.collection_id == collection_id,
                    CollectionPhoto.photo_id == collection_update.cover_photo_id,
                )
            )
            cover_result = await db.execute(cover_photo_stmt)
            if not cover_result.scalar_one_or_none():
                raise HTTPException(
                    status_code=400,
                    detail="Cover photo must be a member of this collection",
                )
        update_data["cover_photo_id"] = collection_update.cover_photo_id

    if update_data:
        update_data["updated_at"] = datetime.utcnow()
        update_stmt = (
            update(Collection)
            .where(Collection.id == collection_id)
            .values(**update_data)
        )
        await db.execute(update_stmt)
        await db.commit()
        await db.refresh(collection)

    return CollectionResponse(
        id=collection["id"],
        name=collection["name"],
        description=collection["description"],
        photo_count=collection["photo_count"],
        cover_photo_id=collection["cover_photo_id"],
        created_at=collection["created_at"],
        updated_at=collection["updated_at"],
    )


@router.delete("/collections/{collection_id}")
async def delete_collection(
    collection_id: str, db: AsyncSession = Depends(get_db_session)
):
    """Delete a collection."""
    # Check if collection exists
    stmt = select(Collection).where(Collection.id == collection_id)
    result = await db.execute(stmt)
    collection = result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Delete collection (cascade will handle collection_photos)
    delete_stmt = delete(Collection).where(Collection.id == collection_id)
    await db.execute(delete_stmt)
    await db.commit()

    return {"message": f"Collection '{collection.name}' deleted successfully"}


@router.post("/collections/{collection_id}/photos")
async def add_photos_to_collection(
    collection_id: str,
    request: CollectionPhotosRequest,
    db: AsyncSession = Depends(get_db_session),
):
    """Add photos to a collection."""
    # Verify collection exists
    collection_stmt = select(Collection).where(Collection.id == collection_id)
    collection_result = await db.execute(collection_stmt)
    collection = collection_result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Verify all photos exist
    photos_stmt = select(Photo.id).where(Photo.id.in_(request.photo_ids))
    photos_result = await db.execute(photos_stmt)
    existing_photo_ids = {row[0] for row in photos_result.fetchall()}

    invalid_photo_ids = set(request.photo_ids) - existing_photo_ids
    if invalid_photo_ids:
        raise HTTPException(
            status_code=400, detail=f"Photos not found: {', '.join(invalid_photo_ids)}"
        )

    # Get existing collection memberships to avoid duplicates
    existing_stmt = select(CollectionPhoto.photo_id).where(
        and_(
            CollectionPhoto.collection_id == collection_id,
            CollectionPhoto.photo_id.in_(request.photo_ids),
        )
    )
    existing_result = await db.execute(existing_stmt)
    existing_memberships = {row[0] for row in existing_result.fetchall()}

    # Add new memberships
    new_photo_ids = existing_photo_ids - existing_memberships
    added_count = 0

    for photo_id in new_photo_ids:
        collection_photo = CollectionPhoto(
            collection_id=collection_id, photo_id=photo_id
        )
        db.add(collection_photo)
        added_count += 1

    # Update collection photo count
    if added_count > 0:
        update_count_stmt = (
            update(Collection)
            .where(Collection.id == collection_id)
            .values(
                photo_count=Collection.photo_count + added_count,
                updated_at=datetime.utcnow(),
            )
        )
        await db.execute(update_count_stmt)

    await db.commit()

    return {
        "message": f"Added {added_count} photos to collection",
        "added_photos": added_count,
        "already_in_collection": len(existing_memberships),
        "total_requested": len(request.photo_ids),
    }


@router.delete("/collections/{collection_id}/photos/{photo_id}")
async def remove_photo_from_collection(
    collection_id: str, photo_id: str, db: AsyncSession = Depends(get_db_session)
):
    """Remove a photo from a collection."""
    # Check if membership exists
    stmt = select(CollectionPhoto).where(
        and_(
            CollectionPhoto.collection_id == collection_id,
            CollectionPhoto.photo_id == photo_id,
        )
    )
    result = await db.execute(stmt)
    membership = result.scalar_one_or_none()

    if not membership:
        raise HTTPException(
            status_code=404, detail="Photo not found in this collection"
        )

    # Remove membership
    delete_stmt = delete(CollectionPhoto).where(
        and_(
            CollectionPhoto.collection_id == collection_id,
            CollectionPhoto.photo_id == photo_id,
        )
    )
    await db.execute(delete_stmt)

    # Update collection photo count
    update_count_stmt = (
        update(Collection)
        .where(Collection.id == collection_id)
        .values(photo_count=Collection.photo_count - 1, updated_at=datetime.utcnow())
    )
    await db.execute(update_count_stmt)

    await db.commit()

    return {"message": "Photo removed from collection successfully"}


@router.get("/collections/{collection_id}/photos")
async def list_collection_photos(
    collection_id: str,
    limit: int = 50,
    offset: int = 0,
    db: AsyncSession = Depends(get_db_session),
):
    """List photos in a collection."""
    # Verify collection exists
    collection_stmt = select(Collection).where(Collection.id == collection_id)
    collection_result = await db.execute(collection_stmt)
    collection = collection_result.scalar_one_or_none()

    if not collection:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Get total count of photos in collection
    count_stmt = select(func.count(CollectionPhoto.photo_id)).where(
        CollectionPhoto.collection_id == collection_id
    )
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # Get photos with pagination
    stmt = (
        select(Photo, CollectionPhoto.added_at)
        .join(CollectionPhoto, Photo.id == CollectionPhoto.photo_id)
        .where(CollectionPhoto.collection_id == collection_id)
        .options(joinedload(Photo.photo_metadata))
        .order_by(CollectionPhoto.added_at.desc())
        .offset(offset)
        .limit(limit)
    )

    result = await db.execute(stmt)
    photo_rows = result.all()

    photos_data = []
    for photo, added_at in photo_rows:
        photo_data = {
            "id": photo.id,
            "filename": photo.filename,
            "file_size": photo.file_size,
            "mime_type": photo.mime_type,
            "width": photo.width,
            "height": photo.height,
            "processing_status": photo.processing_status,
            "user_rating": photo.user_rating,
            "created_at": photo.created_at,
            "updated_at": photo.updated_at,
            "added_to_collection_at": added_at,
        }

        # Add metadata if available
        if photo.photo_metadata:
            photo_data["metadata"] = {
                "camera_make": photo.photo_metadata.camera_make,
                "camera_model": photo.photo_metadata.camera_model,
                "lens_model": photo.photo_metadata.lens_model,
                "date_taken": photo.photo_metadata.date_taken,
                "gps_latitude": photo.photo_metadata.gps_latitude,
                "gps_longitude": photo.photo_metadata.gps_longitude,
                "focal_length": photo.photo_metadata.focal_length,
                "aperture": photo.photo_metadata.aperture,
                "iso": photo.photo_metadata.iso,
            }

        photos_data.append(photo_data)

    return {
        "collection_id": collection_id,
        "collection_name": collection.name,
        "photos": photos_data,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + limit < total,
    }
