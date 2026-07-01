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
        """生成 AppSecretDep 所需的 HMAC-SHA256 签名头（调用 /internal/* 接口）。"""
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

    def _build_proxy_headers(self, user_id: int) -> dict[str, str]:
        """构建代理调用 core-service 常规管理接口所需的请求头。

        模拟网关转发：注入 X-Internal-Secret + X-User-Id + X-App-Code，
        使 core-service 的 get_current_user 走网关信任模式。
        """
        return {
            "X-Gateway-Token": self._build_gateway_token(),
            "X-Internal-Secret": self._internal_secret,
            "X-User-Id": str(user_id),
            "X-App-Code": self._app_code,
            "X-NexusKit-Trace-Id": f"dh-{uuid.uuid4().hex[:8]}",
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
    # 管理接口代理（模拟网关转发，调用 core-service 常规接口）
    # ------------------------------------------------------------------

    async def list_users(
        self, user_id: int, keyword: str | None = None,
        is_active: bool | None = None, dept_id: int | None = None,
        page: int = 1, page_size: int = 20,
    ) -> dict:
        """代理：获取用户列表。"""
        params: dict = {"page": page, "page_size": page_size}
        if keyword:
            params["keyword"] = keyword
        if is_active is not None:
            params["is_active"] = is_active
        if dept_id:
            params["dept_id"] = dept_id
        url = f"{self._base_url}/api/v1/identity/users"
        resp = await self._client.get(url, headers=self._build_proxy_headers(user_id), params=params)
        resp.raise_for_status()
        return resp.json()

    async def list_roles(self, user_id: int) -> dict:
        """代理：获取本系统的角色列表。"""
        url = f"{self._base_url}/api/v1/identity/apps/{self._app_code}/roles"
        resp = await self._client.get(url, headers=self._build_proxy_headers(user_id))
        resp.raise_for_status()
        return resp.json()

    async def create_role(self, user_id: int, role_name: str, role_code: str) -> dict:
        """代理：新建角色。"""
        url = f"{self._base_url}/api/v1/identity/apps/{self._app_code}/roles"
        resp = await self._client.post(
            url, headers=self._build_proxy_headers(user_id),
            json={"role_name": role_name, "role_code": role_code, "app_code": self._app_code},
        )
        resp.raise_for_status()
        return resp.json()

    async def update_role(self, user_id: int, role_id: int, data: dict) -> dict:
        """代理：更新角色。"""
        url = f"{self._base_url}/api/v1/identity/roles/{role_id}"
        resp = await self._client.put(url, headers=self._build_proxy_headers(user_id), json=data)
        resp.raise_for_status()
        return resp.json()

    async def delete_role(self, user_id: int, role_id: int) -> None:
        """代理：删除角色。"""
        url = f"{self._base_url}/api/v1/identity/roles/{role_id}"
        resp = await self._client.delete(url, headers=self._build_proxy_headers(user_id))
        resp.raise_for_status()

    async def get_role_permissions(self, user_id: int, role_id: int) -> dict:
        """代理：获取角色已绑定的权限节点。"""
        url = f"{self._base_url}/api/v1/identity/roles/{role_id}/permissions"
        resp = await self._client.get(url, headers=self._build_proxy_headers(user_id))
        resp.raise_for_status()
        return resp.json()

    async def assign_role_permissions(self, user_id: int, role_id: int, permission_ids: list[int]) -> dict:
        """代理：批量设置角色权限。"""
        url = f"{self._base_url}/api/v1/identity/roles/{role_id}/permissions"
        resp = await self._client.put(
            url, headers=self._build_proxy_headers(user_id),
            json={"permission_ids": permission_ids},
        )
        resp.raise_for_status()
        return resp.json()

    async def list_user_roles(self, user_id: int, target_user_id: int) -> dict:
        """代理：获取用户的角色列表（按 app_code 过滤）。"""
        url = f"{self._base_url}/api/v1/identity/users/{target_user_id}/roles"
        resp = await self._client.get(
            url, headers=self._build_proxy_headers(user_id),
            params={"app_code": self._app_code},
        )
        resp.raise_for_status()
        return resp.json()

    async def assign_user_role(self, user_id: int, target_user_id: int, role_id: int) -> dict:
        """代理：给用户分配角色。"""
        url = f"{self._base_url}/api/v1/identity/users/{target_user_id}/roles"
        resp = await self._client.post(
            url, headers=self._build_proxy_headers(user_id), json={"role_id": role_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def revoke_user_role(self, user_id: int, target_user_id: int, role_id: int) -> None:
        """代理：撤销用户的角色。"""
        url = f"{self._base_url}/api/v1/identity/users/{target_user_id}/roles/{role_id}"
        resp = await self._client.delete(url, headers=self._build_proxy_headers(user_id))
        resp.raise_for_status()

    async def list_menus(self, user_id: int) -> dict:
        """代理：获取本系统的菜单列表（平铺）。"""
        url = f"{self._base_url}/api/v1/identity/apps/{self._app_code}/menus"
        resp = await self._client.get(url, headers=self._build_proxy_headers(user_id))
        resp.raise_for_status()
        return resp.json()

    async def list_menus_tree(self, user_id: int) -> dict:
        """代理：获取本系统的菜单树（嵌套）。"""
        url = f"{self._base_url}/api/v1/identity/apps/{self._app_code}/menus/tree"
        resp = await self._client.get(url, headers=self._build_proxy_headers(user_id))
        resp.raise_for_status()
        return resp.json()

    async def create_menu(self, user_id: int, data: dict) -> dict:
        """代理：新增菜单/按钮。"""
        url = f"{self._base_url}/api/v1/identity/apps/{self._app_code}/menus"
        resp = await self._client.post(url, headers=self._build_proxy_headers(user_id), json=data)
        resp.raise_for_status()
        return resp.json()

    async def update_menu(self, user_id: int, menu_id: int, data: dict) -> dict:
        """代理：更新菜单。"""
        url = f"{self._base_url}/api/v1/identity/menus/{menu_id}"
        resp = await self._client.put(url, headers=self._build_proxy_headers(user_id), json=data)
        resp.raise_for_status()
        return resp.json()

    async def delete_menu(self, user_id: int, menu_id: int) -> None:
        """代理：删除菜单。"""
        url = f"{self._base_url}/api/v1/identity/menus/{menu_id}"
        resp = await self._client.delete(url, headers=self._build_proxy_headers(user_id))
        resp.raise_for_status()

    async def list_departments(self, user_id: int) -> dict:
        """代理：获取所有部门（只读，用于用户列表筛选）。"""
        url = f"{self._base_url}/api/v1/identity/departments"
        resp = await self._client.get(url, headers=self._build_proxy_headers(user_id))
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def close(self) -> None:
        await self._client.aclose()
