# domains/slice/schemas.py — Pydantic schemas for Slide
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SlideOut(BaseModel):
    """切片元数据响应。"""

    id: int
    app_code: str
    device_id: int | None
    batch_id: str | None
    relative_path: str | None
    slide_code: str
    file_format: str
    staining_type: str | None
    file_size: int
    oss_key: str | None
    thumbnail_key: str | None
    status: str
    uploaded_by: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SlicePresignedUrlOut(BaseModel):
    """OSS 预签名下载 URL。"""

    slice_id: int
    url: str
    expires_in: int = Field(3600, description="URL 有效秒数")


class STSCredentials(BaseModel):
    """STS 临时凭证。"""

    access_key_id: str
    secret_access_key: str
    session_token: str
    expiration: str = Field(..., description="ISO 8601 格式过期时间")


class UploadUrlOut(BaseModel):
    """上传凭证响应（STS 临时凭证模式）。"""

    slice_id: int
    dir_key: str = Field(..., description="样本目录 OSS 路径")
    endpoint_url: str | None = Field(None, description="S3 Endpoint（如 https://oss-cn-hangzhou.aliyuncs.com）")
    region_name: str = Field(..., description="S3 区域，如 us-east-1")
    bucket_name: str = Field(..., description="Bucket 名称")
    credentials: STSCredentials
    expires_in: int = Field(900, description="凭证有效秒数")



# ---------------------------------------------------------------------------
# Slice registration
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    """注册切片请求。"""

    device_code: str = Field(..., max_length=64, description="设备编码")
    slide_code: str = Field(..., max_length=255, description="切片编码（扫描仪 barcode）")
    file_format: str = Field(..., max_length=16, description="文件格式：SVS/TIFF/TIF/DZI/LD")
    staining_type: str | None = Field(None, max_length=32, description="染色类型：HE/IHC/PAS/Masson 等")
    file_size: int = Field(..., ge=0, description="文件大小 (bytes)")


class RegisterOut(BaseModel):
    """注册响应。"""

    slice_id: int
    slide_code: str
    status: str


# ---------------------------------------------------------------------------
# Status update
# ---------------------------------------------------------------------------

class SlideStatusUpdate(BaseModel):
    """切片状态更新请求。"""

    slice_id: int = Field(..., gt=0, description="切片 ID")
    status: str = Field(..., pattern="^(pending|uploading|ready|error)$", description="状态：pending/uploading/ready/error")
    error_message: str | None = Field(None, max_length=512, description="错误信息（status=error 时必填）")


# ---------------------------------------------------------------------------
# List / Filter
# ---------------------------------------------------------------------------

class SlideListQuery(BaseModel):
    """列表查询过滤参数。"""

    app_code: str | None = None
    status: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)



