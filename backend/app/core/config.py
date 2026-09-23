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

    # --- WhatsApp / SMS / USSD providers (Section 6) ------------------------
    # "mock" (default) needs no credentials. Set to "twilio" (WhatsApp/SMS) or
    # "africastalking" (USSD) once real credentials are configured below —
    # the Screening Gateway never changes; only the provider class swaps.
    whatsapp_provider: str = Field(default="mock", alias="WHATSAPP_PROVIDER")
    sms_provider: str = Field(default="mock", alias="SMS_PROVIDER")
    ussd_provider: str = Field(default="mock", alias="USSD_PROVIDER")

    # The exact public HTTPS base URL this API is reachable at (e.g.
    # "https://kuza-identify-api.vercel.app"), no trailing slash. Required to
    # verify Twilio's X-Twilio-Signature, which is computed over the exact
    # URL Twilio was configured to call — a request's own Host header can't
    # be trusted behind a proxy/serverless edge.
    public_base_url: str | None = Field(default=None, alias="PUBLIC_BASE_URL")

    # Twilio (WhatsApp + SMS). See console.twilio.com for the Account SID and
    # Auth Token; the WhatsApp sender is a Twilio WhatsApp-enabled number in
    # "whatsapp:+1415..." form (the sandbox number while testing), the SMS
    # sender is a plain Twilio phone number in "+1415..." form.
    twilio_account_sid: str | None = Field(default=None, alias="TWILIO_ACCOUNT_SID")
    twilio_auth_token: str | None = Field(default=None, alias="TWILIO_AUTH_TOKEN")
    twilio_whatsapp_from: str | None = Field(default=None, alias="TWILIO_WHATSAPP_FROM")
    twilio_sms_from: str | None = Field(default=None, alias="TWILIO_SMS_FROM")

    # Africa's Talking (USSD). They do not cryptographically sign webhooks, so
    # USSD_WEBHOOK_SECRET is a shared secret WE choose and append as a query
    # string on the callback URL registered in the AT dashboard
    # (".../webhook/ussd?key=...") — checked on every inbound callback.
    africastalking_username: str | None = Field(default=None, alias="AFRICASTALKING_USERNAME")
    africastalking_api_key: str | None = Field(default=None, alias="AFRICASTALKING_API_KEY")
    ussd_webhook_secret: str | None = Field(default=None, alias="USSD_WEBHOOK_SECRET")

    # --- Dashboard chatbot ---------------------------------------------------
    # Reuses ANTHROPIC_API_KEY above; no separate credential. Same cost-driven
    # model default as scoring, override independently if needed.
    chatbot_model: str = Field(default="claude-haiku-4-5", alias="CHATBOT_MODEL")

    # --- Voice-note transcription (Section 6 style: interface only) --------
    # "none" (default) => NotConfiguredTranscriptionProvider, fails loudly.
    # No provider is implemented yet; this exists so the setting is real once
    # one is added, without silently calling an unconfigured third party.
    transcription_provider: str = Field(default="none", alias="TRANSCRIPTION_PROVIDER")

    # --- App ----------------------------------------------------------------
    app_env: str = Field(default="local", alias="APP_ENV")
    cors_origins: str = Field(default="*", alias="CORS_ORIGINS")
    # True on serverless hosts (Vercel) so the DB engine uses NullPool.
    serverless: bool = Field(default=False, alias="SERVERLESS")
    # Guards the one-shot /admin/init bootstrap endpoint (schema + seed).
    admin_token: str | None = Field(default=None, alias="ADMIN_TOKEN")

    @property
    def llm_enabled(self) -> bool:
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
