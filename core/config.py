from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    environment: str = Field("development", alias="ENVIRONMENT")
    port: int = Field(8000, alias="PORT")

    base_url: Optional[str] = Field(None, alias="BASE_URL")
    
    database_url: str = Field(..., alias="DATABASE_URL")
    
    jira_base: Optional[str] = Field(None, alias="JIRA_BASE")
    jira_email: Optional[str] = Field(None, alias="JIRA_EMAIL")
    jira_token: Optional[str] = Field(None, alias="JIRA_TOKEN")
    jira_service_desk_id: Optional[int] = Field(None, alias="JIRA_SERVICE_DESK_ID")
    
    smtp_host: Optional[str] = Field(None, alias="SMTP_HOST")
    smtp_port: Optional[int] = Field(None, alias="SMTP_PORT")
    smtp_username: Optional[str] = Field(None, alias="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(None, alias="SMTP_PASSWORD")
    smtp_from_email: Optional[str] = Field(None, alias="SMTP_FROM_EMAIL")
    smtp_use_tls: bool = Field(True, alias="SMTP_USE_TLS")
    
    whatsapp_token: Optional[str] = Field(None, alias="WHATSAPP_TOKEN")
    whatsapp_phone_number_id: Optional[str] = Field(None, alias="WHATSAPP_PHONE_NUMBER_ID")
    whatsapp_app_secret: Optional[str] = Field(None, alias="WHATSAPP_APP_SECRET")

    line_channel_access_token: Optional[str] = Field(None, alias="LINE_CHANNEL_ACCESS_TOKEN")
    line_channel_secret: Optional[str] = Field(None, alias="LINE_CHANNEL_SECRET")
    
    llm_api_key: Optional[str] = Field(None, alias="LLM_API_KEY")
    llm_base_url: str = Field("https://api.openai.com/v1", alias="LLM_BASE_URL")
    llm_model: str = Field("gpt-4o-mini", alias="LLM_MODEL")
    
    telegram_bot_token: Optional[str] = Field(None, alias="TELEGRAM_BOT_TOKEN")
    telegram_webhook_secret: Optional[str] = Field(None, alias="TELEGRAM_WEBHOOK_SECRET")

    rate_limit_window_seconds: int = Field(60, alias="RATE_LIMIT_WINDOW_SECONDS")
    rate_limit_max: int = Field(30, alias="RATE_LIMIT_MAX")

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        case_sensitive=True,
    )

    @property
    def public_base_url(self) -> str:
        if self.base_url:
            return self.base_url.rstrip("/")

        if self.environment.lower() in {"prod", "production"}:
            raise RuntimeError("BASE_URL is required when ENVIRONMENT=production")

        return f"http://localhost:{self.port}"

    def validate_runtime(self) -> None:
        _ = self.public_base_url

    def require_jira(self) -> tuple[str, str, str, int]:
        missing: list[str] = []
        if not self.jira_base:
            missing.append("JIRA_BASE")
        if not self.jira_email:
            missing.append("JIRA_EMAIL")
        if not self.jira_token:
            missing.append("JIRA_TOKEN")
        if self.jira_service_desk_id is None:
            missing.append("JIRA_SERVICE_DESK_ID")

        if missing:
            raise RuntimeError(f"Jira config missing: {', '.join(missing)}")

        return (self.jira_base, self.jira_email, self.jira_token, self.jira_service_desk_id)

    def require_smtp(self) -> tuple[str, int, str, str, str]:
        missing: list[str] = []
        if not self.smtp_host:
            missing.append("SMTP_HOST")
        if self.smtp_port is None:
            missing.append("SMTP_PORT")
        if not self.smtp_username:
            missing.append("SMTP_USERNAME")
        if not self.smtp_password:
            missing.append("SMTP_PASSWORD")
        if not self.smtp_from_email:
            missing.append("SMTP_FROM_EMAIL")

        if missing:
            raise RuntimeError(f"SMTP config missing: {', '.join(missing)}")

        return (
            self.smtp_host,
            self.smtp_port,
            self.smtp_username,
            self.smtp_password,
            self.smtp_from_email,
        )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (init_settings, env_settings, dotenv_settings, file_secret_settings)

settings = Settings()
