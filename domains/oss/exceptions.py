# domains/oss/exceptions.py — OSS config domain exceptions
"""OSS 配置域异常定义，遵循 nexuskit-sdk 异常体系。"""
from nexuskit_sdk import BizCode, NexusKitException


class OssConfigDomainError(NexusKitException):
    """OSS 配置域异常基类。"""
    status_code = 400
    code = BizCode.BAD_REQUEST


class OssConfigNotFoundError(OssConfigDomainError):
    """OSS 配置不存在 (404)。"""
    status_code = 404
    code = BizCode.NOT_FOUND

    def __init__(self, config_id: int | str):
        super().__init__(
            message=f"OSS 配置 '{config_id}' 不存在",
            code=BizCode.NOT_FOUND,
            status_code=404,
        )


class OssConfigInactiveError(OssConfigDomainError):
    """OSS 配置已停用 (403)。"""
    status_code = 403
    code = BizCode.FORBIDDEN

    def __init__(self, app_code: str):
        super().__init__(
            message=f"app_code='{app_code}' 的 OSS 配置已停用",
            code=BizCode.FORBIDDEN,
            status_code=403,
        )


class DuplicateDefaultConfigError(OssConfigDomainError):
    """重复默认配置 (409)。"""
    status_code = 409
    code = BizCode.CONFLICT

    def __init__(self, app_code: str):
        super().__init__(
            message=f"app_code='{app_code}' 已有默认 OSS 配置，请先取消原有默认",
            code=BizCode.CONFLICT,
            status_code=409,
        )


class OssConfigInUseError(OssConfigDomainError):
    """OSS 配置被引用，无法删除 (409)。"""
    status_code = 409
    code = BizCode.CONFLICT

    def __init__(self, config_id: int, ref_count: int):
        super().__init__(
            message=f"OSS 配置(id={config_id}) 仍有 {ref_count} 条切片引用，无法删除",
            code=BizCode.CONFLICT,
            status_code=409,
        )


class NoOssConfigAvailableError(OssConfigDomainError):
    """无可用 OSS 配置 (503)。"""
    status_code = 503
    code = BizCode.INTERNAL_ERROR

    def __init__(self, app_code: str):
        super().__init__(
            message=f"找不到 app_code='{app_code}' 的 OSS 配置且无默认配置，请先在平台添加 OSS 配置",
            code=BizCode.INTERNAL_ERROR,
            status_code=503,
        )
