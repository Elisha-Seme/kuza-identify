"""Application configuration, loaded from environment variables.

Nothing secret is hard-coded. See .env.example at the repo root for the full
set of variables and docker-compose.yml for how they are wired locally.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Database -----------------------------------------------------------
    database_url: str = Field(
        default="postgresql+psycopg://kuza:kuza@localhost:5432/kuza",
        alias="DATABASE_URL",
    )

    # --- LLM Scoring Service (Section 3.3 / Section 6) ----------------------
    # When ANTHROPIC_API_KEY is unset the scoring service falls back to a
    # deterministic local scorer so the project runs without credentials.
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    # Haiku 4.5 chosen deliberately: Section 3.3 makes per-child cost the driver
    # of model choice for screening thousands of learners. Override with SCORING_MODEL.
    scoring_model: str = Field(default="claude-haiku-4-5", alias="SCORING_MODEL")
    # Bumped whenever the prompt or model changes; stored on every DomainScore.
    scoring_prompt_version: str = Field(
        default="kuza-scoring-v1", alias="SCORING_PROMPT_VERSION"
    )

    # --- WhatsApp provider (Section 6) --------------------------------------
    # "mock" is the only implementation wired for Phase 0. The interface is
    # clean so africastalking / twilio can be dropped in without touching the
    # Screening Gateway.
    whatsapp_provider: str = Field(default="mock", alias="WHATSAPP_PROVIDER")

    # --- App ----------------------------------------------------------------
    app_env: str = Field(default="local", alias="APP_ENV")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
