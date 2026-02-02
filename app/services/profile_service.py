from datetime import date, timedelta
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import Profile
from app.schemas.profile import ProfileCreate, ProfileSearch, ProfileUpdate


async def create_profile(
    db: AsyncSession, user_id: UUID, data: ProfileCreate
) -> Profile:
    """Create new profile for user."""
    profile_data = data.model_dump()

    # Convert languages to list of dicts for JSON storage
    if profile_data.get("languages"):
        profile_data["languages"] = [
            lang.model_dump() if hasattr(lang, "model_dump") else lang
            for lang in profile_data["languages"]
        ]

    # Convert enums to values
    for key, value in profile_data.items():
        if hasattr(value, "value"):
            profile_data[key] = value.value

    profile = Profile(user_id=user_id, **profile_data)
    profile.profile_score = calculate_profile_score(profile)
    profile.is_complete = profile.profile_score >= 70

    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


async def get_profile_by_user_id(db: AsyncSession, user_id: UUID) -> Profile | None:
    """Get profile by user ID."""
    result = await db.execute(select(Profile).where(Profile.user_id == user_id))
    return result.scalar_one_or_none()


async def get_profile_by_id(db: AsyncSession, profile_id: UUID) -> Profile | None:
    """Get profile by profile ID."""
    result = await db.execute(select(Profile).where(Profile.id == profile_id))
    return result.scalar_one_or_none()


async def update_profile(
    db: AsyncSession, profile: Profile, data: ProfileUpdate
) -> Profile:
    """Update profile fields. Only update fields that are provided."""
    update_data = data.model_dump(exclude_unset=True)

    # Convert languages to list of dicts for JSON storage
    if "languages" in update_data and update_data["languages"] is not None:
        update_data["languages"] = [
            lang.model_dump() if hasattr(lang, "model_dump") else lang
            for lang in update_data["languages"]
        ]

    # Convert enums to values
    for key, value in update_data.items():
        if hasattr(value, "value"):
            update_data[key] = value.value

    for field, value in update_data.items():
        setattr(profile, field, value)

    profile.profile_score = calculate_profile_score(profile)
    profile.is_complete = profile.profile_score >= 70

    await db.commit()
    await db.refresh(profile)
    return profile


async def search_profiles(
    db: AsyncSession,
    filters: ProfileSearch,
    current_user_id: UUID,
) -> tuple[list[Profile], int]:
    """
    Search profiles with filters.
    Returns (profiles, total_count) for pagination.
    """
    query = select(Profile).where(
        and_(
            Profile.user_id != current_user_id,
            Profile.is_visible == True,
        )
    )

    # Apply filters
    if filters.seeking_gender:
        query = query.where(Profile.gender == filters.seeking_gender.value)

    if filters.ethnicities:
        ethnicity_values = [e.value for e in filters.ethnicities]
        query = query.where(Profile.ethnicity.in_(ethnicity_values))

    if filters.residence_countries:
        query = query.where(
            Profile.verified_residence_country.in_(filters.residence_countries)
        )

    if filters.religious_practices:
        practice_values = [p.value for p in filters.religious_practices]
        query = query.where(Profile.religious_practice.in_(practice_values))

    if filters.min_height_cm:
        query = query.where(Profile.height_cm >= filters.min_height_cm)

    if filters.max_height_cm:
        query = query.where(Profile.height_cm <= filters.max_height_cm)

    # Age filters based on verified_birth_date
    today = date.today()
    if filters.min_age:
        max_birth_date = today - timedelta(days=filters.min_age * 365)
        query = query.where(Profile.verified_birth_date <= max_birth_date)

    if filters.max_age:
        min_birth_date = today - timedelta(days=(filters.max_age + 1) * 365)
        query = query.where(Profile.verified_birth_date > min_birth_date)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination
    offset = (filters.page - 1) * filters.per_page
    query = query.offset(offset).limit(filters.per_page)

    # Order by profile score (most complete first)
    query = query.order_by(Profile.profile_score.desc())

    result = await db.execute(query)
    profiles = list(result.scalars().all())

    return profiles, total


def calculate_profile_score(profile: Profile) -> int:
    """
    Calculate profile completeness score (0-100).
    - Required fields filled: 30 points
    - Physical info filled: 10 points
    - Background info filled: 20 points
    - Essays filled: 40 points
    """
    score = 0

    # Required fields (30 points)
    if profile.gender:
        score += 15
    if profile.seeking_gender:
        score += 15

    # Physical info (10 points)
    physical_fields = [profile.height_cm, profile.weight_kg, profile.build]
    physical_filled = sum(1 for f in physical_fields if f is not None)
    score += int((physical_filled / 3) * 10)

    # Background info (20 points)
    background_fields = [
        profile.ethnicity,
        profile.languages and len(profile.languages) > 0,
        profile.original_region,
        profile.current_city,
        profile.living_situation,
        profile.religious_practice,
        profile.smoking,
        profile.alcohol,
        profile.diet,
        profile.profession,
    ]
    background_filled = sum(1 for f in background_fields if f)
    score += int((background_filled / 10) * 20)

    # Essays (40 points)
    # about_me and ideal_partner are primary (10 points each)
    # family_meaning, goals_dreams, message_to_family are secondary (6-7 points each)
    if profile.about_me and len(profile.about_me) >= 50:
        score += 10
    if profile.ideal_partner and len(profile.ideal_partner) >= 50:
        score += 10
    if profile.family_meaning and len(profile.family_meaning) >= 30:
        score += 7
    if profile.goals_dreams and len(profile.goals_dreams) >= 30:
        score += 7
    if profile.message_to_family and len(profile.message_to_family) >= 30:
        score += 6

    return min(score, 100)


async def update_profile_score(db: AsyncSession, profile: Profile) -> Profile:
    """Recalculate and save profile score."""
    profile.profile_score = calculate_profile_score(profile)
    profile.is_complete = profile.profile_score >= 70
    await db.commit()
    await db.refresh(profile)
    return profile
