"""Matching service for compatibility scoring and suggestions."""

import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import and_, not_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.interest import Interest
from app.models.match import Match
from app.models.profile import Profile
from app.models.search_preference import SearchPreference
from app.models.user import User
from app.schemas.search_preference import (
    CompatibilityBreakdown,
    CompatibilityResponse,
    MatchSuggestion,
)


def calculate_age(birth_date: date | None) -> int | None:
    """Calculate age from birth date."""
    if not birth_date:
        return None
    today = date.today()
    age = today.year - birth_date.year
    if (today.month, today.day) < (birth_date.month, birth_date.day):
        age -= 1
    return age


def _check_list_match(preference_list: list | None, value: str | None) -> bool:
    """Check if value matches preference list. Empty/None list means any."""
    if not preference_list:
        return True  # No preference = any value acceptable
    if not value:
        return False  # Has preference but candidate has no value
    return value.lower() in [p.lower() for p in preference_list]


def _score_factor(
    match: bool,
    max_score: int,
    detail: str,
) -> CompatibilityBreakdown:
    """Create a compatibility breakdown for a factor."""
    return CompatibilityBreakdown(
        match=match,
        score=max_score if match else 0,
        max_score=max_score,
        detail=detail,
    )


async def calculate_compatibility(
    user_profile: Profile,
    user_preferences: SearchPreference | None,
    candidate_profile: Profile,
    candidate_preferences: SearchPreference | None = None,
) -> CompatibilityResponse:
    """
    Calculate compatibility score between user and candidate.

    Scoring (total 100 points):
    - Age match: 15 points
    - Location: 15 points
    - Ethnicity: 10 points
    - Religion: 15 points
    - Education: 5 points
    - Marital status: 10 points
    - Physical (height): 5 points
    - Lifestyle: 10 points
    - Verification: 10 points
    - Mutual interest: 5 points
    """
    breakdown: dict[str, CompatibilityBreakdown] = {}
    total_score = 0

    # Use default preferences if none set
    if not user_preferences:
        # Create a temporary preference object with defaults
        user_preferences = SearchPreference(
            min_age=18,
            max_age=99,
            must_be_verified=True,
            has_children_acceptable=True,
        )

    candidate_age = calculate_age(candidate_profile.verified_birth_date)

    # 1. Age match (15 points)
    age_match = True
    age_detail = "Age compatible"
    if candidate_age:
        if candidate_age < user_preferences.min_age:
            age_match = False
            age_detail = f"Too young ({candidate_age} < {user_preferences.min_age})"
        elif candidate_age > user_preferences.max_age:
            age_match = False
            age_detail = f"Too old ({candidate_age} > {user_preferences.max_age})"
        else:
            age_detail = f"Age {candidate_age} within range"
    else:
        age_detail = "Age not verified"
        age_match = False
    breakdown["age"] = _score_factor(age_match, 15, age_detail)
    if age_match:
        total_score += 15

    # 2. Location (15 points)
    location_match = True
    location_detail = "Location compatible"
    if user_preferences.preferred_countries:
        candidate_country = candidate_profile.verified_nationality or candidate_profile.verified_residence_country
        if not _check_list_match(user_preferences.preferred_countries, candidate_country):
            location_match = False
            location_detail = f"Country not in preferences"
        else:
            location_detail = f"Country matches preference"
    if location_match and user_preferences.preferred_cities:
        if not _check_list_match(user_preferences.preferred_cities, candidate_profile.current_city):
            location_match = False
            location_detail = "City not in preferences"
    breakdown["location"] = _score_factor(location_match, 15, location_detail)
    if location_match:
        total_score += 15

    # 3. Ethnicity (10 points)
    ethnicity_match = _check_list_match(
        user_preferences.preferred_ethnicities,
        candidate_profile.ethnicity,
    )
    ethnicity_detail = "Ethnicity compatible" if ethnicity_match else "Ethnicity not in preferences"
    breakdown["ethnicity"] = _score_factor(ethnicity_match, 10, ethnicity_detail)
    if ethnicity_match:
        total_score += 10

    # 4. Religion (15 points)
    religion_match = _check_list_match(
        user_preferences.preferred_religious_practices,
        candidate_profile.religious_practice,
    )
    religion_detail = "Religious practice compatible" if religion_match else "Religious practice not in preferences"
    breakdown["religion"] = _score_factor(religion_match, 15, religion_detail)
    if religion_match:
        total_score += 15

    # 5. Education (5 points)
    education_match = _check_list_match(
        user_preferences.preferred_education_levels,
        candidate_profile.verified_education_level,
    )
    education_detail = "Education compatible" if education_match else "Education level not in preferences"
    breakdown["education"] = _score_factor(education_match, 5, education_detail)
    if education_match:
        total_score += 5

    # 6. Marital status (10 points)
    marital_match = _check_list_match(
        user_preferences.preferred_marital_statuses,
        candidate_profile.verified_marital_status,
    )
    marital_detail = "Marital status compatible" if marital_match else "Marital status not in preferences"
    breakdown["marital_status"] = _score_factor(marital_match, 10, marital_detail)
    if marital_match:
        total_score += 10

    # 7. Physical - Height (5 points)
    height_match = True
    height_detail = "Height compatible"
    if candidate_profile.height_cm:
        if user_preferences.min_height_cm and candidate_profile.height_cm < user_preferences.min_height_cm:
            height_match = False
            height_detail = f"Too short ({candidate_profile.height_cm}cm)"
        elif user_preferences.max_height_cm and candidate_profile.height_cm > user_preferences.max_height_cm:
            height_match = False
            height_detail = f"Too tall ({candidate_profile.height_cm}cm)"
    else:
        height_detail = "Height not specified"
    breakdown["height"] = _score_factor(height_match, 5, height_detail)
    if height_match:
        total_score += 5

    # 8. Lifestyle (10 points) - smoking, alcohol, diet
    lifestyle_score = 0
    lifestyle_matches = 0
    lifestyle_total = 0

    if user_preferences.preferred_smoking:
        lifestyle_total += 1
        if _check_list_match(user_preferences.preferred_smoking, candidate_profile.smoking):
            lifestyle_matches += 1

    if user_preferences.preferred_alcohol:
        lifestyle_total += 1
        if _check_list_match(user_preferences.preferred_alcohol, candidate_profile.alcohol):
            lifestyle_matches += 1

    if user_preferences.preferred_diet:
        lifestyle_total += 1
        if _check_list_match(user_preferences.preferred_diet, candidate_profile.diet):
            lifestyle_matches += 1

    if lifestyle_total > 0:
        lifestyle_score = int((lifestyle_matches / lifestyle_total) * 10)
        lifestyle_match = lifestyle_matches == lifestyle_total
        lifestyle_detail = f"{lifestyle_matches}/{lifestyle_total} lifestyle preferences match"
    else:
        lifestyle_score = 10
        lifestyle_match = True
        lifestyle_detail = "No lifestyle preferences set"

    breakdown["lifestyle"] = CompatibilityBreakdown(
        match=lifestyle_match,
        score=lifestyle_score,
        max_score=10,
        detail=lifestyle_detail,
    )
    total_score += lifestyle_score

    # 9. Verification (10 points)
    is_verified = candidate_profile.user.verification_status == "verified"
    verification_match = is_verified or not user_preferences.must_be_verified
    verification_detail = "Verified profile" if is_verified else "Not verified"
    breakdown["verification"] = _score_factor(
        verification_match and is_verified, 10, verification_detail
    )
    if is_verified:
        total_score += 10

    # 10. Mutual interest (5 points)
    mutual = False
    mutual_score = None
    if candidate_preferences:
        # Check if user matches candidate's preferences
        user_age = calculate_age(user_profile.verified_birth_date)
        mutual_checks = []

        # Age check
        if user_age:
            mutual_checks.append(
                candidate_preferences.min_age <= user_age <= candidate_preferences.max_age
            )

        # Location check
        if candidate_preferences.preferred_countries:
            user_country = user_profile.verified_nationality or user_profile.verified_residence_country
            mutual_checks.append(
                _check_list_match(candidate_preferences.preferred_countries, user_country)
            )

        # If all checks pass (or no checks), consider it mutual
        if mutual_checks:
            mutual = all(mutual_checks)
        else:
            mutual = True

        if mutual:
            mutual_score = 5
            total_score += 5

    mutual_detail = "Mutual match potential" if mutual else "Not a mutual match"
    breakdown["mutual"] = _score_factor(mutual, 5, mutual_detail)

    return CompatibilityResponse(
        score=total_score,
        breakdown=breakdown,
        mutual=mutual,
        mutual_score=mutual_score,
    )


async def get_suggestions(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 10,
) -> tuple[list[MatchSuggestion], int]:
    """
    Get match suggestions for a user.

    1. Get user's profile and preferences
    2. Get candidate profiles (basic filters)
    3. Exclude: self, already matched, pending interests, declined
    4. Calculate compatibility for each
    5. Sort by score descending
    6. Return top N with scores
    """
    # Get user with profile and preferences
    user_result = await db.execute(
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.search_preferences),
        )
        .where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user or not user.profile:
        return [], 0

    user_profile = user.profile
    user_preferences = user.search_preferences

    # Get gender preference
    seeking_gender = user_profile.seeking_gender

    # Get users to exclude (already interacted)
    # 1. Users we've sent interest to
    sent_interests_result = await db.execute(
        select(Interest.to_user_id).where(Interest.from_user_id == user_id)
    )
    sent_to_ids = {row[0] for row in sent_interests_result.fetchall()}

    # 2. Users who sent us interest that we declined
    declined_interests_result = await db.execute(
        select(Interest.from_user_id).where(
            Interest.to_user_id == user_id,
            Interest.status == "declined",
        )
    )
    declined_ids = {row[0] for row in declined_interests_result.fetchall()}

    # 3. Users we're matched with
    matches_result = await db.execute(
        select(Match).where(
            or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
            Match.status == "active",
        )
    )
    matched_ids = set()
    for match in matches_result.scalars():
        other_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id
        matched_ids.add(other_id)

    exclude_ids = sent_to_ids | declined_ids | matched_ids | {user_id}

    # Get candidate profiles
    query = (
        select(Profile)
        .options(
            selectinload(Profile.user).selectinload(User.search_preferences),
        )
        .join(User)
        .where(
            Profile.user_id.not_in(exclude_ids) if exclude_ids else True,
            Profile.gender == seeking_gender if seeking_gender else True,
            Profile.is_visible == True,
            User.status == "active",
        )
    )

    result = await db.execute(query)
    candidates = list(result.scalars().all())

    # Calculate compatibility for each candidate
    suggestions_with_scores = []
    for candidate_profile in candidates:
        candidate_preferences = candidate_profile.user.search_preferences

        compatibility = await calculate_compatibility(
            user_profile,
            user_preferences,
            candidate_profile,
            candidate_preferences,
        )

        # Construct display name from verified fields
        display_name = None
        if candidate_profile.verified_first_name:
            display_name = candidate_profile.verified_first_name
            if candidate_profile.verified_last_initial:
                display_name += f" {candidate_profile.verified_last_initial}."

        suggestion = MatchSuggestion(
            profile_id=candidate_profile.id,
            user_id=candidate_profile.user_id,
            display_name=display_name,
            age=calculate_age(candidate_profile.verified_birth_date),
            city=candidate_profile.current_city,
            country=candidate_profile.verified_nationality or candidate_profile.verified_residence_country,
            compatibility_score=compatibility.score,
            is_mutual_match=compatibility.mutual,
            is_verified=candidate_profile.user.verification_status == "verified",
        )
        suggestions_with_scores.append((suggestion, compatibility.score))

    # Sort by score descending
    suggestions_with_scores.sort(key=lambda x: x[1], reverse=True)

    # Get total count before limiting
    total_available = len(suggestions_with_scores)

    # Return top N
    top_suggestions = [s[0] for s in suggestions_with_scores[:limit]]

    return top_suggestions, total_available


async def get_who_likes_me(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 20,
) -> tuple[list[MatchSuggestion], int]:
    """
    Find profiles where their preferences match current user.

    Returns users who:
    - Have search preferences set
    - Their preferences match the current user's profile
    - Haven't sent interest yet
    """
    # Get user's profile
    user_result = await db.execute(
        select(User)
        .options(selectinload(User.profile))
        .where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user or not user.profile:
        return [], 0

    user_profile = user.profile
    user_age = calculate_age(user_profile.verified_birth_date)
    user_country = user_profile.verified_nationality or user_profile.verified_residence_country

    # Get users who have preferences set and are seeking user's gender
    query = (
        select(SearchPreference)
        .options(
            selectinload(SearchPreference.user)
            .selectinload(User.profile),
        )
        .join(User)
        .join(Profile, User.id == Profile.user_id)
        .where(
            SearchPreference.user_id != user_id,
            Profile.seeking_gender == user_profile.gender,
            User.status == "active",
        )
    )

    result = await db.execute(query)
    preferences_list = list(result.scalars().all())

    # Filter to those whose preferences match user
    matching_profiles = []
    for pref in preferences_list:
        if not pref.user or not pref.user.profile:
            continue

        matches = True

        # Check age
        if user_age:
            if user_age < pref.min_age or user_age > pref.max_age:
                matches = False

        # Check country
        if matches and pref.preferred_countries:
            if not _check_list_match(pref.preferred_countries, user_country):
                matches = False

        # Check ethnicity
        if matches and pref.preferred_ethnicities:
            if not _check_list_match(pref.preferred_ethnicities, user_profile.ethnicity):
                matches = False

        if matches:
            candidate_profile = pref.user.profile
            # Construct display name from verified fields
            display_name = None
            if candidate_profile.verified_first_name:
                display_name = candidate_profile.verified_first_name
                if candidate_profile.verified_last_initial:
                    display_name += f" {candidate_profile.verified_last_initial}."

            suggestion = MatchSuggestion(
                profile_id=candidate_profile.id,
                user_id=candidate_profile.user_id,
                display_name=display_name,
                age=calculate_age(candidate_profile.verified_birth_date),
                city=candidate_profile.current_city,
                country=candidate_profile.verified_nationality or candidate_profile.verified_residence_country,
                compatibility_score=0,  # Will be calculated if needed
                is_mutual_match=True,  # They match us, that's why they're here
                is_verified=pref.user.verification_status == "verified",
            )
            matching_profiles.append(suggestion)

    total = len(matching_profiles)
    return matching_profiles[:limit], total


async def get_compatibility_with_profile(
    db: AsyncSession,
    user_id: uuid.UUID,
    target_profile_id: uuid.UUID,
) -> CompatibilityResponse | None:
    """Calculate compatibility between user and a specific profile."""
    # Get user with profile and preferences
    user_result = await db.execute(
        select(User)
        .options(
            selectinload(User.profile),
            selectinload(User.search_preferences),
        )
        .where(User.id == user_id)
    )
    user = user_result.scalar_one_or_none()

    if not user or not user.profile:
        return None

    # Get target profile with user and preferences
    target_result = await db.execute(
        select(Profile)
        .options(
            selectinload(Profile.user).selectinload(User.search_preferences),
        )
        .where(Profile.id == target_profile_id)
    )
    target_profile = target_result.scalar_one_or_none()

    if not target_profile:
        return None

    return await calculate_compatibility(
        user.profile,
        user.search_preferences,
        target_profile,
        target_profile.user.search_preferences,
    )
