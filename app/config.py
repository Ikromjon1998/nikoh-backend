from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    APP_NAME: str = "Nikoh API"

    # Auto-verification settings
    ENABLE_AUTO_VERIFICATION: bool = True
    FACE_MATCH_AUTO_APPROVE_THRESHOLD: float = 0.65
    FACE_MATCH_AUTO_REJECT_THRESHOLD: float = 0.35
    FACE_MATCH_MANUAL_REVIEW_MIN: float = 0.35
    FACE_MATCH_MANUAL_REVIEW_MAX: float = 0.65

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
