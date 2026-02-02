from fastapi import APIRouter

from app.api.v1.endpoints import auth, profiles

router = APIRouter()

router.include_router(auth.router, prefix="/auth")
router.include_router(profiles.router, prefix="/profiles")
