"""Settings: env vars only, no secrets in code. Copy .env.example to .env."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: str = "dev-only-change-me"
    host: str = "127.0.0.1"
    port: int = 8000

    model_config = {"env_prefix": "PROJECT0_", "env_file": ".env"}


settings = Settings()
