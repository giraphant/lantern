"""
Configuration management for the backend.
"""
import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # App
    app_name: str = "Funding Rate Arbitrage Dashboard"
    debug: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/funding_bot.db"

    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:5173"]

    # Exchange credentials (from environment)
    # GRVT
    grvt_api_key: str | None = None
    grvt_private_key: str | None = None
    grvt_trading_account_id: str | None = None
    grvt_environment: str = "prod"

    # Lighter
    lighter_private_key: str | None = None
    lighter_account_index: int = 0
    lighter_api_key_index: int = 0

    # Binance
    binance_api_key: str | None = None
    binance_secret_key: str | None = None

    # Backpack
    backpack_public_key: str | None = None
    backpack_secret_key: str | None = None

    # Telegram
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None

    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
