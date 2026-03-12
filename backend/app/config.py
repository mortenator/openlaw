from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_service_role_key: str
    resend_api_key: str
    brave_api_key: str

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
