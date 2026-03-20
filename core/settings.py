from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "JARVIS"
    ENV: str = "development"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    LOG_LEVEL: str = "INFO"
    OPENAI_API_KEY: str = ""
    JARVIS_OWNER_NAME: str = "Juan Camilo Montenegro"
    VOICE_PROVIDER_DEFAULT: str = "elevenlabs"
    WHATSAPP_PROVIDER_DEFAULT: str = "twilio"

    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
