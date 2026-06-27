# domains/slice/schemas.py — Pydantic schemas for SliceFile
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Upload / Create
# ---------------------------------------------------------------------------

class SliceUploadMeta(BaseModel):
    """文件上传时携带的元数据（form-data 字段）。"""

    case_id: str | None = Field(None, max_length=64, description="关联诊断病例 ID（可选）")
    patient_id: str | None = Field(None, max_length=64, description="患者 ID（可选）")
    staining_type: str = Field(..., max_length=32, description="染色类型，如 HE / IHC / PAS")
    description: str | None = Field(None, max_length=512, description="备注信息（可选）")


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class SliceFileOut(BaseModel):
    """切片文件元数据响应。"""

    id: int
    app_code: str
    case_id: str | None
    patient_id: str | None
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
# List / Filter
# ---------------------------------------------------------------------------

class SliceListQuery(BaseModel):
    """列表查询过滤参数。"""

    app_code: str | None = None
    case_id: str | None = None
    patient_id: str | None = None
    status: str | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
