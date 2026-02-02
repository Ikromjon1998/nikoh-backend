from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class MatchResponse(BaseModel):
    """Match details returned by API"""

    id: UUID
    user_a_id: UUID
    user_b_id: UUID
    status: str
    created_at: datetime

    # Profile of the other person in the match
    other_user_profile: dict | None = None

    model_config = ConfigDict(from_attributes=True)


class MatchListResponse(BaseModel):
    """Paginated list of matches"""

    matches: list[MatchResponse]
    total: int
    page: int
    per_page: int


class UnmatchRequest(BaseModel):
    """Request to unmatch"""

    pass
