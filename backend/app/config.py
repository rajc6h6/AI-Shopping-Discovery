from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    serpapi_api_key: str = ""
    featherless_api_key: str = ""
    cache_db_path: str = "cache/serpapi_cache.db"
    default_market: str = "in"  # "in" or "us"
    max_calls_per_session: int = 50
    max_calls_per_item: int = 2
    max_calls_per_compare: int = 4
    demo_mode: bool = False
    offline_mode: bool = True
    max_calls_per_offline: int = 5
    frontend_url: str = "http://localhost:3000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"
