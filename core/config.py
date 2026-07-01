# core/config.py — Datahub Service configuration
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=False)


class DbSettings(BaseSettings):
    model_config = _ENV
    DATABASE_URL: str
    DEBUG: bool = False


class AppSettings(BaseSettings):
    model_config = _ENV
    PROJECT_NAME: str = "Datahub Service"
    ENVIRONMENT: str = "development"
    # NexusKit 内部调用凭证（服务间鉴权）
    NEXUSKIT_URL: str = "http://localhost:5000"
    NEXUSKIT_APP_CODE: str = "datahub"
    NEXUSKIT_APP_SECRET: str = ""
    # 与 gateway/core-service 共享的内部密钥（生成 X-Gateway-Token）
    INTERNAL_SECRET: str = ""


class S3Settings(BaseSettings):
    model_config = _ENV
    S3_ACCESS_KEY_ID: str
    S3_SECRET_ACCESS_KEY: str


@lru_cache
def get_s3_settings() -> S3Settings:
    return S3Settings()


@lru_cache
def get_db_settings() -> DbSettings:
    return DbSettings()


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()
