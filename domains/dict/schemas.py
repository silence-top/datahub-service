# domains/dict/schemas.py — Pydantic schemas for Dictionary
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# DictType
# ---------------------------------------------------------------------------

class DictTypeCreate(BaseModel):
    """新建字典类型。"""

    type_code: str = Field(..., max_length=64, description="字典类型编码，如 device_model")
    type_name: str = Field(..., max_length=128, description="字典类型名称，如 设备型号")
    description: str | None = Field(None, max_length=256, description="描述")


class DictTypeUpdate(BaseModel):
    """更新字典类型，所有字段可选。"""

    type_name: str | None = Field(None, max_length=128)
    description: str | None = Field(None, max_length=256)
    is_active: bool | None = None


class DictTypeOut(BaseModel):
    """字典类型输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type_code: str
    type_name: str
    description: str | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class DictTypeListQuery(BaseModel):
    """字典类型列表查询参数。"""

    is_active: bool | None = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)


# ---------------------------------------------------------------------------
# DictValue
# ---------------------------------------------------------------------------

class DictValueCreate(BaseModel):
    """新建字典值。"""

    value_key: str = Field(..., max_length=128, description="存储值")
    value_label: str = Field(..., max_length=256, description="显示标签")
    sort: int = Field(0, ge=0, description="排序序号")


class DictValueUpdate(BaseModel):
    """更新字典值，所有字段可选。"""

    value_key: str | None = Field(None, max_length=128)
    value_label: str | None = Field(None, max_length=256)
    sort: int | None = Field(None, ge=0)
    is_active: bool | None = None


class DictValueOut(BaseModel):
    """字典值输出。"""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type_code: str
    value_key: str
    value_label: str
    sort: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
