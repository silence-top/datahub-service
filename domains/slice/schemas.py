# domains/slice/schemas.py — Pydantic schemas for SliceFile
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Upload / Create
# ---------------------------------------------------------------------------

class SliceUploadMeta(BaseModel):
    """文件上传时携带的元数据（form-data 字段）。"""
    staining_type: str = Field(..., max_length=32, description="染色类型，如 HE / IHC / PAS")
    description: str | None = Field(None, max_length=512, description="备注信息（可选）")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SliceFileOut(BaseModel):
    """切片文件元数据响应。"""

    id: int
    app_code: str

    original_name: str
    file_format: str
    staining_type: str
    file_size: int
    oss_key: str
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


# ---------------------------------------------------------------------------
# Batch upload
# ---------------------------------------------------------------------------

class BatchFileFailure(BaseModel):
    """单文件上传失败明细。"""

    filename: str
    error: str


class BatchUploadResult(BaseModel):
    """批量上传结果。"""

    batch_id: str
    device_code: str
    success_count: int
    failure_count: int
    failures: list[BatchFileFailure] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Presigned direct upload (服务端签名 + 客户端直传 OSS)
# ---------------------------------------------------------------------------

class PresignFileItem(BaseModel):
    """单个待签名文件信息。"""

    filename: str = Field(..., max_length=256, description="原始文件名")
    file_size: int = Field(..., gt=0, description="文件大小 (bytes)")
    relative_path: str | None = Field(None, max_length=512, description="文件夹场景的相对路径")


class PresignBatchRequest(BaseModel):
    """批量预签名请求。"""

    device_code: str = Field(..., max_length=64, description="设备编码（必须已注册）")
    files: list[PresignFileItem] = Field(..., min_length=1, max_length=200)


class PresignItemOut(BaseModel):
    """单个预签名结果。"""

    filename: str
    upload_url: str
    oss_key: str


class PresignBatchOut(BaseModel):
    """批量预签名响应。"""

    batch_id: str
    presigns: list[PresignItemOut]
    expires_in: int = Field(300, description="签名有效秒数")


class BatchConfirmFileItem(BaseModel):
    """批量确认中单个已上传文件信息。"""

    filename: str
    oss_key: str
    file_size: int
    file_format: str = Field(..., max_length=16, description="文件格式，如 SVS, TIFF")


class BatchConfirmRequest(BaseModel):
    """批量直传确认请求（文件已直传到 OSS，客户端汇报写入 DB）。"""

    batch_id: str
    device_code: str
    files: list[BatchConfirmFileItem] = Field(..., min_length=1)


# ---------------------------------------------------------------------------
# List / Filter
# ---------------------------------------------------------------------------

class SliceListQuery(BaseModel):
    """列表查询过滤参数。"""

    app_code: str | None = None
    status: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
