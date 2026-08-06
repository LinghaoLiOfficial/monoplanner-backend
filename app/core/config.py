from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Fullstack Context Orchestrator API", alias="APP_NAME")
    database_url: str = Field(
        default="postgresql+psycopg://llh@localhost:5432/context_orchestrator",
        alias="DATABASE_URL",
    )
    backend_cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="BACKEND_CORS_ORIGINS",
    )
    llm_provider: str = Field(default="openai_compatible", alias="LLM_PROVIDER")
    llm_base_url: str | None = Field(default=None, alias="LLM_BASE_URL")
    llm_api_key: str | None = Field(default=None, alias="LLM_API_KEY")
    llm_model: str | None = Field(default=None, alias="LLM_MODEL")
    llm_timeout_seconds: float = Field(default=60.0, alias="LLM_TIMEOUT_SECONDS")
    llm_stream_read_timeout_seconds: float = Field(
        default=300.0, alias="LLM_STREAM_READ_TIMEOUT_SECONDS"
    )
    llm_thinking: bool = Field(default=False, alias="LLM_THINKING")
    llm_use_response_format: bool = Field(default=True, alias="LLM_USE_RESPONSE_FORMAT")
    queue_worker_concurrency: int = Field(default=1, ge=1, alias="QUEUE_WORKER_CONCURRENCY")
    queue_poll_interval_seconds: float = Field(default=2.0, alias="QUEUE_POLL_INTERVAL_SECONDS")
    queue_stale_after_seconds: int = Field(default=900, alias="QUEUE_STALE_AFTER_SECONDS")
    queue_worker_heartbeat_timeout_seconds: int = Field(
        default=15, alias="QUEUE_WORKER_HEARTBEAT_TIMEOUT_SECONDS"
    )
    queue_max_attempts: int = Field(default=3, alias="QUEUE_MAX_ATTEMPTS")
    queue_worker_id: str | None = Field(default=None, alias="QUEUE_WORKER_ID")
    auth_secret_key: str | None = Field(default=None, alias="AUTH_SECRET_KEY")
    auth_token_expire_days: int = Field(default=7, alias="AUTH_TOKEN_EXPIRE_DAYS")
    auth_cookie_name: str = Field(default="access_token", alias="AUTH_COOKIE_NAME")
    auth_cookie_secure: bool = Field(default=False, alias="AUTH_COOKIE_SECURE")
    auth_cookie_samesite: str = Field(default="lax", alias="AUTH_COOKIE_SAMESITE")
    email_verification_expire_minutes: int = Field(
        default=10, alias="EMAIL_VERIFICATION_EXPIRE_MINUTES"
    )
    email_verification_resend_seconds: int = Field(
        default=60, alias="EMAIL_VERIFICATION_RESEND_SECONDS"
    )
    smtp_host: str | None = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=587, alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, alias="SMTP_USERNAME")
    smtp_code: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_CODE", "SMTP_PASSWORD"),
    )
    smtp_sender_email: str | None = Field(
        default=None,
        validation_alias=AliasChoices("SMTP_SENDER_EMAIL", "SMTP_FROM_EMAIL"),
    )
    smtp_use_tls: bool = Field(default=True, alias="SMTP_USE_TLS")
    bootstrap_admin_email: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_username: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_USERNAME")
    bootstrap_admin_password: str | None = Field(default=None, alias="BOOTSTRAP_ADMIN_PASSWORD")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    @property
    def smtp_configured(self) -> bool:
        return bool(self.smtp_host and self.smtp_sender_email)

    @property
    def smtp_login_username(self) -> str | None:
        return self.smtp_username or self.smtp_sender_email

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
