from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    resend_api_key: str
    brave_api_key: str
    anthropic_api_key: str
    cron_secret: str
    paperclip_base_url: str = "http://localhost:3100"
    paperclip_internal_key: str  # Required — empty string rejected at startup

    @field_validator("paperclip_internal_key")
    @classmethod
    def _key_not_empty(cls, v: str) -> str:
        if not v:
            raise ValueError("PAPERCLIP_INTERNAL_KEY must not be empty")
        return v

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
