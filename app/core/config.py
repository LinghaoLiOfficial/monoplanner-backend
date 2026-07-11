from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = Field(default="Fullstack Context Orchestrator API", alias="APP_NAME")
    database_url: str = Field(
        default="postgresql+psycopg://orchestrator:orchestrator@localhost:5432/context_orchestrator",
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
    llm_timeout: float = Field(default=60.0, alias="LLM_TIMEOUT")
    llm_timeout_seconds: float = Field(default=60.0, alias="LLM_TIMEOUT_SECONDS")
    llm_thinking: bool = Field(default=False, alias="LLM_THINKING")
    llm_use_response_format: bool = Field(default=True, alias="LLM_USE_RESPONSE_FORMAT")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def llm_configured(self) -> bool:
        return bool(self.llm_base_url and self.llm_api_key and self.llm_model)

    def model_post_init(self, __context: object) -> None:
        if self.llm_timeout_seconds == 60.0 and self.llm_timeout != 60.0:
            self.llm_timeout_seconds = self.llm_timeout
        self.llm_timeout = self.llm_timeout_seconds

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
