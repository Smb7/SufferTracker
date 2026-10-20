from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/suffertracker"
    jwt_key: str = ""
    jwt_issuer: str = "SufferTracker"
    jwt_audience: str = "SufferTracker.Web"
    frontend_origin: str = "http://localhost:4200"
    admin_emails: str = ""
    admin_password: str = ""
    ocr_endpoint: str = ""
    ocr_api_key: str = ""
    ocr_api_key_header: str = "Ocp-Apim-Subscription-Key"
    app_env: str = "development"
    auto_migrate: bool = True

    @property
    def is_dev(self) -> bool:
        return self.app_env.lower() in {"development", "dev"}

    @property
    def admin_email_list(self) -> list[str]:
        return [item.strip().lower() for item in self.admin_emails.split(",") if item.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
