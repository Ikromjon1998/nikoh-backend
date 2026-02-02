from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match


async def create_match(
    db: AsyncSession,
    user_a_id: UUID,
    user_b_id: UUID,
) -> Match:
    """
    Create a new match between two users.
    Ensures user_a_id < user_b_id for consistency.
    """
    # Ensure correct ordering
    if user_a_id > user_b_id:
        user_a_id, user_b_id = user_b_id, user_a_id

    match = Match(
        user_a_id=user_a_id,
        user_b_id=user_b_id,
        status="active",
    )
    db.add(match)
    await db.flush()
    await db.refresh(match)
    return match


async def get_match_by_id(
    db: AsyncSession,
    match_id: UUID,
) -> Match | None:
    """Get match by ID."""
    result = await db.execute(select(Match).where(Match.id == match_id))
    return result.scalar_one_or_none()


async def get_match_between_users(
    db: AsyncSession,
    user_a_id: UUID,
    user_b_id: UUID,
) -> Match | None:
    """Get active match between two users if exists."""
    # Ensure correct ordering
    if user_a_id > user_b_id:
        user_a_id, user_b_id = user_b_id, user_a_id

    result = await db.execute(
        select(Match).where(
            and_(
                Match.user_a_id == user_a_id,
                Match.user_b_id == user_b_id,
                Match.status == "active",
            )
        )
    )
    return result.scalar_one_or_none()


async def get_user_matches(
    db: AsyncSession,
    user_id: UUID,
    status: str = "active",
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Match], int]:
    """Get all matches for a user."""
    query = select(Match).where(
        and_(
            or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
            Match.status == status,
        )
    )

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * per_page
    query = query.order_by(Match.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    matches = list(result.scalars().all())

    return matches, total


async def unmatch(
    db: AsyncSession,
    match: Match,
    user_id: UUID,
) -> Match:
    """Unmatch - set status to 'unmatched', record who did it."""
    match.status = "unmatched"
    match.unmatched_by = user_id
    match.unmatched_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(match)
    return match
