"""Application configuration using pydantic-settings."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Instagram credentials
    instagram_username: str
    instagram_password: str

    # Scraping parameters
    min_followers: int = 3000
    max_depth: int = 3

    # Redis configuration
    redis_url: str = "redis://localhost:6379/0"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    """Get cached application settings."""
    return Settings()
