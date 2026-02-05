import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, decode_access_token
from app.database import get_db
from app.schemas.user import Token, UserCreate, UserResponse
from app.services import user_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["auth"])

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    try:
        user_id = UUID(payload.sub)
    except ValueError:
        raise credentials_exception

    user = await user_service.get_user_by_id(db, user_id)
    if user is None:
        raise credentials_exception

    return UserResponse.model_validate(user)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    try:
        existing_user = await user_service.get_user_by_email(db, user_data.email)
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered",
            )

        if user_data.phone:
            existing_phone = await user_service.get_user_by_phone(db, user_data.phone)
            if existing_phone:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Phone number already registered",
                )

        user = await user_service.create_user(db, user_data)
        return UserResponse.model_validate(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Registration failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}. Make sure database migrations have been run.",
        )


@router.post("/login", response_model=Token)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Token:
    try:
        user = await user_service.authenticate_user(db, form_data.username, form_data.password)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )

        access_token = create_access_token(str(user.id))
        return Token(access_token=access_token)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Login failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}. Make sure database migrations have been run.",
        )


@router.get("/me", response_model=UserResponse)
async def get_me(
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> UserResponse:
    return current_user
