# main.py — FastAPI application entry point
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from nexuskit_sdk import init_app, response

from core.config import get_app_settings
from core.lifespan import lifespan
from domains.admin.router import router as admin_router
from domains.device.router import router as device_router
from domains.dict.router import router as dict_router
from domains.oss.router import router as oss_router
from domains.slice.router import router as slice_router
from middleware.gateway_auth import GatewayAuthMiddleware

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
)

_settings = get_app_settings()

app = FastAPI(
    title=_settings.PROJECT_NAME,
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ------------------------------------------------------------------
# State — storage client 由 lifespan 动态注入（从 DB 加载 OSS 配置）
# ------------------------------------------------------------------

# ------------------------------------------------------------------
# Middleware（注册顺序：后注册先执行）
# 1. GatewayAuth（最先执行，拦截非网关请求）
# 2. CORS
# 3. NexusTraceMiddleware（由 init_app 注册）
# ------------------------------------------------------------------

app.add_middleware(GatewayAuthMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ------------------------------------------------------------------
# SDK: 注册 NexusTraceMiddleware + 异常处理器（422 / 500）
# ------------------------------------------------------------------
init_app(app)

# ------------------------------------------------------------------
# Routers
# ------------------------------------------------------------------

app.include_router(admin_router, prefix="/api/v1")
app.include_router(slice_router, prefix="/api/v1")
app.include_router(device_router, prefix="/api/v1")
app.include_router(dict_router, prefix="/api/v1")
app.include_router(oss_router, prefix="/api/v1")

# ------------------------------------------------------------------
# Health check
# ------------------------------------------------------------------

@app.get("/health", tags=["ops"])
async def health():
    return response.success(data={"status": "ok", "service": _settings.PROJECT_NAME})
