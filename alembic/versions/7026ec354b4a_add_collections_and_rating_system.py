"""add collections and rating system

Revision ID: 7026ec354b4a
Revises: 9f53850aeeaa
Create Date: 2025-07-21 15:34:00.039303

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "7026ec354b4a"
down_revision: Union[str, Sequence[str], None] = "9f53850aeeaa"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add rating column to photos table
    op.add_column("photos", sa.Column("user_rating", sa.Integer()))
    op.add_column("photos", sa.Column("rating_updated_at", sa.DateTime()))

    # Add check constraint for rating values (0-5, where 0=unrated)
    op.create_check_constraint(
        "ck_photos_user_rating_range", "photos", "user_rating >= 0 AND user_rating <= 5"
    )

    # Create collections table
    op.create_table(
        "collections",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime()),
        sa.Column("photo_count", sa.Integer(), server_default="0"),
        sa.Column("cover_photo_id", sa.String()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["cover_photo_id"], ["photos.id"]),
        sa.Index("ix_collections_name", "name"),
    )

    # Create collection_photos junction table
    op.create_table(
        "collection_photos",
        sa.Column("collection_id", sa.String(), nullable=False),
        sa.Column("photo_id", sa.String(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["collection_id"], ["collections.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["photo_id"], ["photos.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("collection_id", "photo_id"),
        sa.Index("ix_collection_photos_collection_id", "collection_id"),
        sa.Index("ix_collection_photos_photo_id", "photo_id"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop tables in reverse order
    op.drop_table("collection_photos")
    op.drop_table("collections")

    # Drop rating columns from photos
    op.drop_constraint("ck_photos_user_rating_range", "photos", type_="check")
    op.drop_column("photos", "rating_updated_at")
    op.drop_column("photos", "user_rating")
