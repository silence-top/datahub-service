# core/config.py — Datahub Service configuration
import os
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


# --- OSS 环境变量（仅首次 seed 时使用，后续从 DB 管理）---
# 读取 .env 中的 OSS_* 变量作为初始值，不存在时返回空字符串
OSS_ACCESS_KEY_ID = os.getenv("OSS_ACCESS_KEY_ID", "")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET", "")
OSS_ENDPOINT = os.getenv("OSS_ENDPOINT", "")
OSS_BUCKET_MAP = os.getenv("OSS_BUCKET_MAP", '{"default":"bucket-default"}')


@lru_cache
def get_db_settings() -> DbSettings:
    return DbSettings()


@lru_cache
def get_app_settings() -> AppSettings:
    return AppSettings()
