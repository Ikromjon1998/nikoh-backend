from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interest import Interest
from app.models.match import Match
from app.schemas.interest import InterestCreate


async def create_interest(
    db: AsyncSession,
    from_user_id: UUID,
    data: InterestCreate,
) -> Interest:
    """Create a new interest."""
    interest = Interest(
        from_user_id=from_user_id,
        to_user_id=data.to_user_id,
        message=data.message,
        status="pending",
        expires_at=datetime.now(timezone.utc) + timedelta(days=14),
    )
    db.add(interest)
    await db.commit()
    await db.refresh(interest)
    return interest


async def get_interest_by_id(
    db: AsyncSession,
    interest_id: UUID,
) -> Interest | None:
    """Get interest by ID."""
    result = await db.execute(select(Interest).where(Interest.id == interest_id))
    return result.scalar_one_or_none()


async def get_pending_interest_between_users(
    db: AsyncSession,
    from_user_id: UUID,
    to_user_id: UUID,
) -> Interest | None:
    """Check if there's a pending interest from user A to user B."""
    result = await db.execute(
        select(Interest).where(
            and_(
                Interest.from_user_id == from_user_id,
                Interest.to_user_id == to_user_id,
                Interest.status == "pending",
            )
        )
    )
    return result.scalar_one_or_none()


async def respond_to_interest(
    db: AsyncSession,
    interest: Interest,
    action: str,
) -> tuple[Interest, Match | None]:
    """
    Respond to an interest (accept or decline).
    If accept, create a Match.
    Returns (updated_interest, match_if_created).
    """
    from app.services.match_service import create_match

    interest.status = "accepted" if action == "accept" else "declined"
    interest.responded_at = datetime.now(timezone.utc)

    match = None
    if action == "accept":
        match = await create_match(db, interest.from_user_id, interest.to_user_id)

    await db.commit()
    await db.refresh(interest)
    return interest, match


async def cancel_interest(
    db: AsyncSession,
    interest: Interest,
) -> None:
    """Cancel a pending interest."""
    interest.status = "cancelled"
    await db.commit()


async def delete_interest(
    db: AsyncSession,
    interest: Interest,
) -> None:
    """Delete an interest."""
    await db.delete(interest)
    await db.commit()


async def get_received_interests(
    db: AsyncSession,
    user_id: UUID,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Interest], int]:
    """Get interests received by user."""
    query = select(Interest).where(Interest.to_user_id == user_id)

    if status:
        query = query.where(Interest.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * per_page
    query = query.order_by(Interest.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    interests = list(result.scalars().all())

    return interests, total


async def get_sent_interests(
    db: AsyncSession,
    user_id: UUID,
    status: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> tuple[list[Interest], int]:
    """Get interests sent by user."""
    query = select(Interest).where(Interest.from_user_id == user_id)

    if status:
        query = query.where(Interest.status == status)

    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    # Apply pagination and ordering
    offset = (page - 1) * per_page
    query = query.order_by(Interest.created_at.desc()).offset(offset).limit(per_page)

    result = await db.execute(query)
    interests = list(result.scalars().all())

    return interests, total


async def expire_old_interests(db: AsyncSession) -> int:
    """
    Mark all pending interests past their expires_at as expired.
    Returns count of expired interests.
    """
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(Interest)
        .where(
            and_(
                Interest.status == "pending",
                Interest.expires_at < now,
            )
        )
        .values(status="expired")
    )
    await db.commit()
    return result.rowcount


async def check_already_matched(
    db: AsyncSession,
    user_a_id: UUID,
    user_b_id: UUID,
) -> bool:
    """Check if two users are already matched (active match)."""
    # Ensure correct ordering for the query
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
    return result.scalar_one_or_none() is not None
