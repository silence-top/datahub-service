# middleware/gateway_auth.py — Trust gateway-injected identity headers
"""
本服务不自行验证 JWT。所有请求必须经过 NexusKit 网关。
网关在转发前会注入：
  - X-User-Id  : 已认证用户 ID（整型字符串）
  - X-App-Code : 请求所属应用编码

本中间件检查这两个 Header：
  - 缺失任意一个 → 401 Unauthorized（说明请求绕过了网关）
  - 合法 → 注入 request.state.user_id 和 request.state.app_code
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from nexuskit_sdk import BizCode, response, trace_ctx


class GatewayAuthMiddleware(BaseHTTPMiddleware):
    """验证请求携带网关注入的身份 Header，并将身份信息写入 request.state。"""

    # 不需要鉴权的路径前缀（设备密钥认证的端点走各自的 DeviceAuthDep）
    _SKIP_PATHS = (
        "/docs",
        "/redoc",
        "/openapi.json",
        "/health",
        "/api/v1/devices/scanner",
        "/api/v1/slices/presign-upload-urls",
        "/api/v1/slices/batch-confirm",
    )

    async def dispatch(self, request: Request, call_next):
        # 跳过白名单路径
        if any(request.url.path.startswith(p) for p in self._SKIP_PATHS):
            return await call_next(request)

        user_id_raw = request.headers.get("X-User-Id")
        app_code = request.headers.get("X-App-Code")

        if not user_id_raw or not app_code:
            return JSONResponse(
                status_code=401,
                content=response.fail(
                    code=BizCode.UNAUTHORIZED,
                    message="未授权：请求头缺少 X-User-Id 和 X-App-Code，请通过网关访问",
                    trace_id=trace_ctx.get(),
                ),
            )

        try:
            user_id = int(user_id_raw)
        except ValueError:
            return JSONResponse(
                status_code=401,
                content=response.fail(
                    code=BizCode.UNAUTHORIZED,
                    message="未授权：X-User-Id 格式不合法",
                    trace_id=trace_ctx.get(),
                ),
            )

        request.state.user_id = user_id
        request.state.app_code = app_code

        return await call_next(request)
