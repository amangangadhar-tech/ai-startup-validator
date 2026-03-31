"""Environment variable loading via pydantic-settings."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables / .env file."""

    nvidia_api_key: str  # required — crashes if missing

    redis_url: str = "redis://redis:6379"
    database_url: str = "postgresql+asyncpg://myapp:myapp@postgres:5432/myapp"
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# Singleton — import this everywhere
settings = Settings()
