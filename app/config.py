"""
Central configuration. Everything business-specific (service areas, max
out-of-area attempts, business name, AI disclosure) is here so you can
tune the agent's behaviour from environment variables without touching
code.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- App ---
    APP_NAME: str = "Real Estate WhatsApp Agent"
    ENV: str = "production"
    LOG_LEVEL: str = "INFO"

    # --- Database (Neon Postgres) ---
    DATABASE_URL: str = "postgresql+psycopg2://user:pass@host/dbname?sslmode=require"

    # --- Meta WhatsApp Cloud API ---
    META_ACCESS_TOKEN: str = ""
    META_PHONE_NUMBER_ID: str = ""
    META_VERIFY_TOKEN: str = "change-this-verify-token"
    META_APP_SECRET: str = ""  # used to verify webhook signatures
    META_API_VERSION: str = "v21.0"

    # --- Groq (free LLM inference) ---
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # --- Business rules ---
    BUSINESS_NAME: str = "YouWe Realty"
    AGENT_NAME: str = "Riya"
    # Comma-separated list of sectors/areas you actually serve, e.g.
    # "Sector 70,Sector 69,Sector 71"
    SERVICE_AREAS: str = "Sector 70"
    OUT_OF_AREA_MAX_ATTEMPTS: int = 4
    # Soft AI disclosure line shown once per new conversation. Some
    # jurisdictions require this; recommended to keep on. You decide.
    DISCLOSE_AI: bool = True
    DEFAULT_LANGUAGE_MODE: str = "auto"  # auto | en | hi | hinglish

    # --- Google Sheets (live property inventory, same sheet the CRM uses) ---
    GOOGLE_SHEET_ID: str = ""
    SHEET_TAB_PROPERTIES: str = "Properties"
    GOOGLE_SERVICE_ACCOUNT_EMAIL: str = ""
    GOOGLE_SERVICE_ACCOUNT_PRIVATE_KEY: str = ""
    # Each property row's "id" gets appended to this to build a shareable
    # link (CRM's public property page with photos/videos).
    PROPERTY_SHARE_BASE_URL: str = "https://youwe-crm.vercel.app/share/property/"

    # --- Admin ---
    ADMIN_API_KEY: str = "change-this-admin-key"
    # Comma-separated team phone numbers (with country code, no +) that get
    # alerted when a customer needs something the AI can't handle (photos,
    # price lock, exact location, etc). Each gets an individual WhatsApp
    # message — official Cloud API can't post into a WhatsApp group.
    TEAM_NOTIFY_PHONES: str = ""
    # Kept for backward compatibility — included automatically alongside
    # TEAM_NOTIFY_PHONES if set.
    ADMIN_NOTIFY_PHONE: str = ""

    @property
    def team_notify_phones_list(self) -> list[str]:
        phones = [p.strip() for p in self.TEAM_NOTIFY_PHONES.split(",") if p.strip()]
        if self.ADMIN_NOTIFY_PHONE and self.ADMIN_NOTIFY_PHONE not in phones:
            phones.append(self.ADMIN_NOTIFY_PHONE)
        return phones

    @property
    def service_areas_list(self) -> List[str]:
        return [a.strip() for a in self.SERVICE_AREAS.split(",") if a.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
