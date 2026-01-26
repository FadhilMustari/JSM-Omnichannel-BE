from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

class Settings(BaseSettings):
    base_url: str = Field(..., alias="BASE_URL")
    
    database_url: str = Field(..., alias="DATABASE_URL")
    
    jira_base: str = Field(..., alias="JIRA_BASE")
    jira_email: str = Field(..., alias="JIRA_EMAIL")
    jira_token: str = Field(..., alias="JIRA_TOKEN")
    jira_service_desk_id: int = Field(..., alias="JIRA_SERVICE_DESK_ID")
    
    smtp_host: str = Field(..., alias="SMTP_HOST")
    smtp_port: int = Field(..., alias="SMTP_PORT")
    smtp_username: str = Field(..., alias="SMTP_USERNAME")
    smtp_password: str = Field(..., alias="SMTP_PASSWORD")
    smtp_from_email: str = Field(..., alias="SMTP_FROM_EMAIL")
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

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls,
        init_settings,
        env_settings,
        dotenv_settings,
        file_secret_settings,
    ):
        return (dotenv_settings, env_settings, init_settings)

settings = Settings()
