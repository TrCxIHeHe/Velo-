from functools import lru_cache
from pydantic import ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", env_file_encoding="utf-8")

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/scooter_db"

    JWT_SECRET: str = "dev_secret_change_before_deploy"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    FIREBASE_PROJECT_ID: str = "your-project-id"
    FIREBASE_SERVICE_ACCOUNT_PATH: str = "./firebase-service-account.json"

    ENVIRONMENT: str = "development"
    API_V1_PREFIX: str = "/api/v1"

    WALLET_DEFAULT_CURRENCY: str = "INR"
    WALLET_MIN_RIDE_BALANCE: int = 20

    REDIS_URL: str = "redis://localhost:6379/0"

    RIDE_TOKEN_SECRET: str = "dev_ride_secret_change_before_deploy"
    RIDE_TOKEN_ALGORITHM: str = "HS256"
    RIDE_TOKEN_TTL_SECONDS: int = 30
    VEHICLE_BATTERY_MIN_THRESHOLD: int = 20


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
