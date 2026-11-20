"""Settings: env vars only, no secrets in code. Copy .env.example to .env."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    api_key: str = "dev-only-change-me"
    host: str = "127.0.0.1"
    port: int = 8000

    # --- first real model (Day 3, 2026-11-20) ---
    # Empty llm_api_key = keep the local heuristic (old behaviour).
    # Set it in .env, never in code. Base URL + model switch vendors
    # without touching code: OpenAI, DeepSeek, Qwen/Bailian all speak
    # the same chat-completions shape.
    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_timeout: float = 15.0

    model_config = {"env_prefix": "PROJECT0_", "env_file": ".env"}


settings = Settings()
