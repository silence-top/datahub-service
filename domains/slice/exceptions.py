# domains/slice/exceptions.py — Slice domain exceptions
"""
域级异常定义，遵循 nexuskit-sdk 异常体系。
Service 层只抛出域异常，由全局异常处理器转换为标准 JSON 响应。
"""
from nexuskit_sdk import BizCode, NexusKitException


class SliceDomainError(NexusKitException):
    """切片域异常基类。"""
    status_code = 400
    code = BizCode.BAD_REQUEST


class SliceNotFoundError(SliceDomainError):
    """切片记录不存在 (404)。"""
    status_code = 404
    code = BizCode.NOT_FOUND

    def __init__(self, slice_id: int):
        super().__init__(message=f"切片 #{slice_id} 不存在", code=BizCode.NOT_FOUND, status_code=404)


class UnsupportedFileFormatError(SliceDomainError):
    """不支持的文件格式 (422)。"""
    status_code = 422
    code = BizCode.UNPROCESSABLE

    def __init__(self, ext: str, allowed: list[str]):
        super().__init__(
            message=f"不支持的文件格式 '{ext}'，允许格式：{sorted(allowed)}",
            code=BizCode.UNPROCESSABLE,
            status_code=422,
        )


class StorageUploadError(SliceDomainError):
    """OSS 上传失败 (502)。"""
    status_code = 502
    code = BizCode.BAD_GATEWAY

    def __init__(self, detail: str):
        super().__init__(message=f"OSS 上传失败：{detail}", code=BizCode.BAD_GATEWAY, status_code=502)


class StorageDeleteError(SliceDomainError):
    """OSS 删除失败 (502)。"""
    status_code = 502
    code = BizCode.BAD_GATEWAY

    def __init__(self, detail: str):
        super().__init__(message=f"OSS 删除失败：{detail}", code=BizCode.BAD_GATEWAY, status_code=502)
