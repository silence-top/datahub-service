# domains/oss/schemas.py — Pydantic schemas for OssConfig
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class OssConfigCreate(BaseModel):
    """新建 OSS 配置。"""

    app_code: str = Field(..., max_length=32, description="应用编码，用于路由 OSS")
    config_name: str = Field(..., max_length=128, description="配置名称")
    access_key_id: str = Field(..., max_length=128, description="OSS AccessKey ID")
    access_key_secret: str = Field(..., max_length=128, description="OSS AccessKey Secret")
    endpoint: str = Field(..., max_length=256, description="OSS Endpoint")
    bucket_name: str = Field(..., max_length=128, description="Bucket 名称")
    is_default: bool = Field(False, description="是否默认配置")


class OssConfigUpdate(BaseModel):
    """更新 OSS 配置，所有字段可选。"""

    config_name: str | None = Field(None, max_length=128)
    access_key_id: str | None = Field(None, max_length=128)
    access_key_secret: str | None = Field(None, max_length=128)
    endpoint: str | None = Field(None, max_length=256)
    bucket_name: str | None = Field(None, max_length=128)
    is_default: bool | None = None
    is_active: bool | None = None


class OssConfigOut(BaseModel):
    """OSS 配置输出（access_key_secret 脱敏）。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    app_code: str
    config_name: str
    access_key_id: str
    access_key_secret: str  # 脱敏后
    endpoint: str
    bucket_name: str
    is_default: bool
    is_active: bool
    created_by: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# List / Filter
# ---------------------------------------------------------------------------

class OssConfigListQuery(BaseModel):
    """列表查询过滤参数。"""

    app_code: str | None = None
    is_active: bool | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
