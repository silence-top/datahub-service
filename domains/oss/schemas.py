# domains/oss/schemas.py — Pydantic schemas for OssConfig
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class OssConfigCreate(BaseModel):
    """新建 S3 Bucket 配置。"""

    app_code: str = Field(..., max_length=32, description="应用编码，用于路由存储")
    config_name: str = Field(..., max_length=128, description="配置名称")
    endpoint_url: str | None = Field(None, max_length=256, description="S3 Endpoint（AWS S3 留空）")
    region_name: str = Field("us-east-1", max_length=32, description="S3 Region")
    bucket_name: str = Field(..., max_length=128, description="Bucket 名称")
    is_default: bool = Field(False, description="是否默认配置")


class OssConfigUpdate(BaseModel):
    """更新 S3 Bucket 配置，所有字段可选。"""

    config_name: str | None = Field(None, max_length=128)
    endpoint_url: str | None = Field(None, max_length=256)
    region_name: str | None = Field(None, max_length=32)
    bucket_name: str | None = Field(None, max_length=128)
    is_default: bool | None = None
    is_active: bool | None = None


class OssConfigOut(BaseModel):
    """S3 Bucket 配置输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    app_code: str
    config_name: str
    endpoint_url: str | None
    region_name: str
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
