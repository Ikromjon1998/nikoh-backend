from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_DAYS: int = 7
    APP_NAME: str = "Nikoh API"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
