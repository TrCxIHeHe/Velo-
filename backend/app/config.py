from functools import lru_cache
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/scooter_db"

    # JWT
    JWT_SECRET: str = "dev_secret_change_before_deploy"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # Firebase
    FIREBASE_PROJECT_ID: str = "your-project-id"
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"

    # App
    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()