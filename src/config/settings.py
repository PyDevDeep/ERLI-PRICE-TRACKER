from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    SERPER_API_KEY: str = Field(default="")
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_CHAT_ID: str = Field(default="")

    # Database
    DATABASE_URL: str = Field(default="")

    # Presentation
    ALERT_LANGUAGE: str = "uk"

    # Business Logic
    SCRAPE_INTERVAL_HOURS: int = 12
    PRICE_CHANGE_THRESHOLD_PERCENT: float = 5.0

    # AI Router - Primary (OpenAI)
    OPENAI_API_KEY: str = Field(default="")
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_TIMEOUT_SECONDS: int = 30

    # AI Router - Fallback (Anthropic)
    ANTHROPIC_API_KEY: str = Field(default="")
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    ANTHROPIC_TIMEOUT_SECONDS: int = 45

    # AI Router - Circuit Breaker
    AI_ROUTER_MAX_RETRIES: int = 2
    AI_ROUTER_CIRCUIT_BREAKER_THRESHOLD: int = 3
    AI_ROUTER_CIRCUIT_BREAKER_RESET_SECONDS: int = 60

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


settings = Settings()
