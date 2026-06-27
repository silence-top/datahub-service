# domains/device/schemas.py — Pydantic schemas for Device
import json
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

class DeviceCreate(BaseModel):
    """注册新设备。"""

    app_code: str = Field(..., max_length=32, description="所属应用编码")
    dept_id: int = Field(..., description="部门ID（引用 core-service）")
    device_code: str = Field(..., max_length=64, description="设备唯一编码（序列号）")
    device_name: str = Field(..., max_length=128, description="设备名称")
    model: str | None = Field(None, max_length=64, description="设备型号")
    manufacturer: str | None = Field(None, max_length=64, description="厂商名称")
    allowed_formats: list[str] = Field(
        default=[".svs", ".ndpi", ".tiff", ".tif", ".mrxs"],
        description="允许上传的文件扩展名列表",
    )
    allowed_staining: list[str] = Field(
        default=["HE", "IHC", "PAS", "Masson"],
        description="允许的染色类型列表",
    )
    max_file_size_mb: int = Field(500, ge=1, le=10240, description="单文件大小上限 MB")


class DeviceUpdate(BaseModel):
    """更新设备信息，所有字段可选。"""

    dept_id: int | None = Field(None, description="部门ID")
    device_name: str | None = Field(None, max_length=128)
    model: str | None = Field(None, max_length=64)
    manufacturer: str | None = Field(None, max_length=64)
    allowed_formats: list[str] | None = None
    allowed_staining: list[str] | None = None
    max_file_size_mb: int | None = Field(None, ge=1, le=10240)
    is_active: bool | None = None


class DeviceOut(BaseModel):
    """设备详情输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    app_code: str
    dept_id: int | None
    device_code: str
    device_name: str
    model: str | None
    manufacturer: str | None
    allowed_formats: list[str]
    allowed_staining: list[str]
    max_file_size_mb: int
    is_active: bool
    registered_by: int
    created_at: datetime
    updated_at: datetime

    @field_validator("allowed_formats", "allowed_staining", mode="before")
    @classmethod
    def _parse_json_list(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Device detail (enriched with core-service app/department info)
# ---------------------------------------------------------------------------

class DeviceDetailOut(BaseModel):
    """设备详情输出（含从 core-service 获取的应用和部门信息）。"""

    model_config = ConfigDict(from_attributes=True)

    # --- 设备本地字段 ---
    id: int
    app_code: str
    dept_id: int | None
    device_code: str
    device_name: str
    model: str | None
    manufacturer: str | None
    allowed_formats: list[str]
    allowed_staining: list[str]
    max_file_size_mb: int
    is_active: bool
    registered_by: int
    created_at: datetime
    updated_at: datetime

    # --- 从 core-service 获取的关联信息（core-service 不可用时为 None）---
    app_name: str | None = None
    app_perm_mode: str | None = None
    app_description: str | None = None
    dept_name: str | None = None
    dept_leader: str | None = None
    dept_phone: str | None = None
    dept_email: str | None = None
    dept_is_active: bool | None = None

    @field_validator("allowed_formats", "allowed_staining", mode="before")
    @classmethod
    def _parse_json_list(cls, v: object) -> list[str]:
        if isinstance(v, str):
            return json.loads(v)
        return v  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Batch upload metadata
# ---------------------------------------------------------------------------

class BatchUploadMeta(BaseModel):
    """批量上传时携带的元数据（form-data 字段）。"""

    device_code: str = Field(..., max_length=64, description="设备编码（必须已注册）")
    case_id: str | None = Field(None, max_length=64, description="关联病例 ID")
    patient_id: str | None = Field(None, max_length=64, description="患者 ID")
    staining_type: str | None = Field(None, max_length=32, description="染色类型（可选覆盖设备默认）")


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

class DeviceListQuery(BaseModel):
    """列表查询过滤参数。"""

    app_code: str | None = None
    is_active: bool | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
