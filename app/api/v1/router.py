from fastapi import APIRouter

from app.api.v1.endpoints import (
    admin,
    auth,
    interests,
    matches,
    payments,
    preferences,
    profiles,
    verifications,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth")
router.include_router(profiles.router, prefix="/profiles")
router.include_router(interests.router, prefix="/interests")
router.include_router(matches.router, prefix="/matches")
router.include_router(verifications.router, prefix="/verifications")
router.include_router(payments.router, prefix="/payments")
router.include_router(preferences.router, prefix="/preferences")
router.include_router(admin.router, prefix="/admin")
