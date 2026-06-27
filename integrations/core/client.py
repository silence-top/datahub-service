# integrations/core/client.py — Core-service HTTP client
"""datahub-service -> core-service 跨服务 HTTP 客户端。

鉴权流程：
  1. X-Gateway-Token: HMAC-SHA256(timestamp, INTERNAL_SECRET) — 通过 GatewayTrustMiddleware
  2. X-App-Code / X-Timestamp / X-Nonce / X-Signature — 通过 AppSecretDep (HMAC-SHA256)
"""
import hashlib
import hmac
import logging
import time
import uuid

import httpx

from core.config import get_app_settings

logger = logging.getLogger("datahub-service.core_client")


class CoreServiceClient:
    """跨服务调用 core-service 内部 API 的客户端。"""

    def __init__(self) -> None:
        s = get_app_settings()
        self._base_url = s.NEXUSKIT_URL.rstrip("/")
        self._app_code = s.NEXUSKIT_APP_CODE
        self._app_secret = s.NEXUSKIT_APP_SECRET
        self._internal_secret = s.INTERNAL_SECRET
        self._client = httpx.AsyncClient(timeout=10.0)

    # ------------------------------------------------------------------
    # 鉴权头构建
    # ------------------------------------------------------------------

    def _build_gateway_token(self) -> str:
        """生成 X-Gateway-Token: {timestamp}.{hmac}"""
        ts = str(int(time.time()))
        sig = hmac.new(
            self._internal_secret.encode(), ts.encode(), hashlib.sha256
        ).hexdigest()
        return f"{ts}.{sig}"

    def _build_auth_headers(self) -> dict[str, str]:
        """生成 AppSecretDep 所需的 HMAC-SHA256 签名头。"""
        ts = str(int(time.time()))
        nonce = uuid.uuid4().hex
        string_to_sign = f"{self._app_code}\n{ts}\n{nonce}"
        sig = hmac.new(
            self._app_secret.encode(), string_to_sign.encode(), hashlib.sha256
        ).hexdigest()
        return {
            "X-App-Code": self._app_code,
            "X-Timestamp": ts,
            "X-Nonce": nonce,
            "X-Signature": sig,
            "X-Gateway-Token": self._build_gateway_token(),
        }

    # ------------------------------------------------------------------
    # API 调用
    # ------------------------------------------------------------------

    async def get_app(self, app_code: str) -> dict | None:
        """查询应用信息。

        Returns: {"id", "app_code", "app_name", "perm_mode", "description"} 或 None
        """
        url = f"{self._base_url}/api/v1/identity/internal/apps/{app_code}"
        try:
            resp = await self._client.get(url, headers=self._build_auth_headers())
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception as exc:
            logger.warning("get_app('%s') failed: %s", app_code, exc)
            return None

    async def get_department(self, dept_id: int) -> dict | None:
        """查询部门信息。

        Returns: {"id", "dept_name", "parent_id", "sort", "leader", "phone", "email", "is_active"} 或 None
        """
        url = f"{self._base_url}/api/v1/identity/internal/departments/{dept_id}"
        try:
            resp = await self._client.get(url, headers=self._build_auth_headers())
            if resp.status_code == 404:
                return None
            resp.raise_for_status()
            return resp.json().get("data")
        except Exception as exc:
            logger.warning("get_department(%d) failed: %s", dept_id, exc)
            return None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()
