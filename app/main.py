import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import router as v1_router
from app.config import settings
from app.database import check_db_connection
from app.core.exceptions import AppException
from app.core.exception_handlers import (
    app_exception_handler,
    validation_exception_handler,
    http_exception_handler,
    generic_exception_handler,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database tables are managed by Alembic migrations
    # Run: alembic upgrade head
    if await check_db_connection():
        logger.info("Database connection successful")
    else:
        logger.warning("Database connection failed - ensure database is running")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
)

# Register exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(StarletteHTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Parse CORS origins from settings
cors_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(v1_router, prefix="/api/v1")

# Serve uploaded files (verifications, selfies)
uploads_dir = Path("./uploads")
uploads_dir.mkdir(exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
