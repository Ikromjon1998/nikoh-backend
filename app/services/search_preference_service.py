"""Search preference service for managing user partner preferences."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.search_preference import SearchPreference
from app.schemas.search_preference import SearchPreferenceCreate


async def get_preferences_by_user_id(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> SearchPreference | None:
    """Get search preferences for a user."""
    result = await db.execute(
        select(SearchPreference).where(SearchPreference.user_id == user_id)
    )
    return result.scalar_one_or_none()


async def create_or_update_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
    data: SearchPreferenceCreate,
) -> SearchPreference:
    """Create or update search preferences (upsert)."""
    existing = await get_preferences_by_user_id(db, user_id)

    if existing:
        # Update existing preferences
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(existing, field, value)
        await db.commit()
        await db.refresh(existing)
        return existing
    else:
        # Create new preferences
        preferences = SearchPreference(
            user_id=user_id,
            **data.model_dump(),
        )
        db.add(preferences)
        await db.commit()
        await db.refresh(preferences)
        return preferences


async def delete_preferences(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> bool:
    """Delete user's search preferences (reset to defaults)."""
    preferences = await get_preferences_by_user_id(db, user_id)
    if preferences:
        await db.delete(preferences)
        await db.commit()
        return True
    return False


def get_default_preferences() -> dict:
    """Get default preference values."""
    return {
        "min_age": 18,
        "max_age": 99,
        "preferred_countries": None,
        "preferred_cities": None,
        "willing_to_relocate": False,
        "relocation_countries": None,
        "preferred_ethnicities": None,
        "preferred_marital_statuses": None,
        "preferred_education_levels": None,
        "preferred_religious_practices": None,
        "min_height_cm": None,
        "max_height_cm": None,
        "preferred_smoking": None,
        "preferred_alcohol": None,
        "preferred_diet": None,
        "must_be_verified": True,
        "has_children_acceptable": True,
        "children_preference": "no_preference",
    }
