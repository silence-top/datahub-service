# domains/device/exceptions.py — Device domain exceptions
"""
设备域异常定义，遵循 nexuskit-sdk 异常体系。
"""
from nexuskit_sdk import BizCode, NexusKitException


class DeviceDomainError(NexusKitException):
    """设备域异常基类。"""
    status_code = 400
    code = BizCode.BAD_REQUEST


class DeviceNotFoundError(DeviceDomainError):
    """设备不存在 (404)。"""
    status_code = 404
    code = BizCode.NOT_FOUND

    def __init__(self, device_code: str):
        super().__init__(message=f"设备 '{device_code}' 不存在", code=BizCode.NOT_FOUND, status_code=404)


class DeviceInactiveError(DeviceDomainError):
    """设备已停用 (403)。"""
    status_code = 403
    code = BizCode.FORBIDDEN

    def __init__(self, device_code: str):
        super().__init__(
            message=f"设备 '{device_code}' 已停用，禁止上传",
            code=BizCode.FORBIDDEN,
            status_code=403,
        )


class DeviceNotRegisteredError(DeviceDomainError):
    """设备未注册 (403)。"""
    status_code = 403
    code = BizCode.FORBIDDEN

    def __init__(self, device_code: str):
        super().__init__(
            message=f"设备 '{device_code}' 未注册，请先在平台注册",
            code=BizCode.FORBIDDEN,
            status_code=403,
        )


class FileFormatNotAllowedError(DeviceDomainError):
    """文件格式不在设备允许列表 (422)。"""
    status_code = 422
    code = BizCode.UNPROCESSABLE

    def __init__(self, ext: str, allowed: list[str], filename: str = ""):
        prefix = f"文件 '{filename}' " if filename else ""
        super().__init__(
            message=f"{prefix}格式 '{ext}' 不在设备允许列表 {sorted(allowed)} 中",
            code=BizCode.UNPROCESSABLE,
            status_code=422,
        )


class FileSizeExceededError(DeviceDomainError):
    """文件超过设备配置的单文件上限 (422)。"""
    status_code = 422
    code = BizCode.UNPROCESSABLE

    def __init__(self, size_mb: float, limit_mb: int, filename: str = ""):
        prefix = f"文件 '{filename}' " if filename else ""
        super().__init__(
            message=f"{prefix}大小 {size_mb:.1f} MB 超过设备上限 {limit_mb} MB",
            code=BizCode.UNPROCESSABLE,
            status_code=422,
        )


class BatchUploadError(DeviceDomainError):
    """批量上传整体异常 (422)。"""
    status_code = 422
    code = BizCode.UNPROCESSABLE

    def __init__(self, detail: str):
        super().__init__(message=f"批量上传失败：{detail}", code=BizCode.UNPROCESSABLE, status_code=422)
