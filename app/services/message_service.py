"""Message service for chat functionality."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import Match
from app.models.message import Message
from app.models.profile import Profile
from app.schemas.message import ChatPreview


async def get_messages(
    db: AsyncSession,
    match_id: UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[Message]:
    """Get messages for a match, ordered by newest first."""
    result = await db.execute(
        select(Message)
        .where(Message.match_id == match_id)
        .order_by(Message.created_at.desc())
        .offset(skip)
        .limit(limit)
    )
    # Reverse to get chronological order for display
    messages = list(result.scalars().all())
    messages.reverse()
    return messages


async def create_message(
    db: AsyncSession,
    match_id: UUID,
    sender_id: UUID,
    content: str,
) -> Message:
    """Create a new message."""
    message = Message(
        match_id=match_id,
        sender_id=sender_id,
        content=content,
    )
    db.add(message)
    await db.commit()
    await db.refresh(message)
    return message


async def mark_message_as_read(
    db: AsyncSession,
    message: Message,
) -> Message:
    """Mark a message as read."""
    message.is_read = True
    message.read_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(message)
    return message


async def mark_all_messages_as_read(
    db: AsyncSession,
    match_id: UUID,
    reader_id: UUID,
) -> int:
    """Mark all unread messages in a match as read (for messages not sent by reader)."""
    result = await db.execute(
        select(Message).where(
            and_(
                Message.match_id == match_id,
                Message.sender_id != reader_id,
                Message.is_read == False,
            )
        )
    )
    messages = list(result.scalars().all())

    now = datetime.now(timezone.utc)
    for message in messages:
        message.is_read = True
        message.read_at = now

    await db.commit()
    return len(messages)


async def get_message_by_id(
    db: AsyncSession,
    message_id: UUID,
) -> Message | None:
    """Get a message by ID."""
    result = await db.execute(
        select(Message).where(Message.id == message_id)
    )
    return result.scalar_one_or_none()


async def get_unread_count(
    db: AsyncSession,
    user_id: UUID,
) -> int:
    """Get total unread messages count for a user."""
    # Get all matches for this user
    matches_result = await db.execute(
        select(Match.id).where(
            and_(
                or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
                Match.status == "active",
            )
        )
    )
    match_ids = [row[0] for row in matches_result.fetchall()]

    if not match_ids:
        return 0

    # Count unread messages not sent by this user
    count_result = await db.execute(
        select(func.count(Message.id)).where(
            and_(
                Message.match_id.in_(match_ids),
                Message.sender_id != user_id,
                Message.is_read == False,
            )
        )
    )
    return count_result.scalar() or 0


async def get_chat_previews(
    db: AsyncSession,
    user_id: UUID,
) -> list[ChatPreview]:
    """Get chat previews for all active matches."""
    # Get all active matches for this user
    matches_result = await db.execute(
        select(Match).where(
            and_(
                or_(Match.user_a_id == user_id, Match.user_b_id == user_id),
                Match.status == "active",
            )
        )
    )
    matches = list(matches_result.scalars().all())

    previews = []
    for match in matches:
        # Get partner's user ID
        partner_id = match.user_b_id if match.user_a_id == user_id else match.user_a_id

        # Get partner's profile for name
        profile_result = await db.execute(
            select(Profile).where(Profile.user_id == partner_id)
        )
        profile = profile_result.scalar_one_or_none()

        partner_name = "Unknown"
        if profile and profile.verified_first_name:
            partner_name = f"{profile.verified_first_name} {profile.verified_last_initial or ''}."

        # Get last message
        last_msg_result = await db.execute(
            select(Message)
            .where(Message.match_id == match.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_message = last_msg_result.scalar_one_or_none()

        # Count unread messages (not sent by current user)
        unread_result = await db.execute(
            select(func.count(Message.id)).where(
                and_(
                    Message.match_id == match.id,
                    Message.sender_id != user_id,
                    Message.is_read == False,
                )
            )
        )
        unread_count = unread_result.scalar() or 0

        previews.append(ChatPreview(
            match_id=match.id,
            partner_name=partner_name,
            last_message=last_message.content if last_message else None,
            last_message_at=last_message.created_at if last_message else None,
            unread_count=unread_count,
        ))

    # Sort by last message time (most recent first)
    previews.sort(key=lambda p: p.last_message_at or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

    return previews
