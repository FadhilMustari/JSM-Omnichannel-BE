from typing import Optional

from pydantic_settings import BaseSettings
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
    
    line_channel_access_token: Optional[str] = Field(None, alias="LINE_CHANNEL_ACCESS_TOKEN")
    
    telegram_bot_token: Optional[str] = Field(None, alias="TELEGRAM_BOT_TOKEN")

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
