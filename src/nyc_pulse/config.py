from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = ""
    database_url_direct: str = ""
    nyc_open_data_app_token: str = ""
    nyc_geoclient_app_id: str = ""
    nyc_geoclient_app_key: str = ""
    default_radius_ft: int = 500
    default_window_days: int = 90


settings = Settings()

