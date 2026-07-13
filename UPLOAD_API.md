# Datahub Service 上传接口文档

> 供上传软件（客户端）开发使用，基于 **OSS 直传模式**（文件不经过服务端）。

---

## 1. 架构概述

```
上传软件                          服务端                          OSS 存储
   │                              │                              │
   │  ① 注册切片（创建 DB 记录）    │                              │
   │─────────────────────────────>│                              │
   │  返回 slice_id 列表           │                              │
   │<─────────────────────────────│                              │
   │                              │                              │
   │  ② 请求上传凭证（传入 slice_id）│                          │
   │─────────────────────────────>│                              │
   │  返回 dir_key + STS 临时凭证    │                              │
   │<─────────────────────────────│                              │
   │                              │                              │
   │  ③ 同步状态：uploading        │                              │
   │─────────────────────────────>│                              │
   │                              │                              │
   │  ④ 直传文件（AWS SDK + STS）  │                              │
   │─────────────────────────────────────────────────────────────>│
   │                              │                              │
   │  ⑤ 同步状态：ready / error    │                              │
   │─────────────────────────────>│                              │
```

**核心原则**：文件数据不经过服务端，客户端通过 STS 临时凭证 + AWS SDK 直传 OSS。单文件和文件夹使用同一接口。

### 1.1 多云 OSS 支持

服务端支持多种 OSS 运营商，通过数据库 `oss_configs` 表的 `provider` 字段区分：

| provider | 运营商 | STS 实现 | Endpoint 推导 |
|----------|--------|----------|---------------|
| `aliyun` | 阿里云 OSS | httpx + HMAC-SHA1 签名（阿里云自有 STS API） | `https://sts.{region}.aliyuncs.com` |
| `aws` | AWS S3 | aiobotocore STS Client | `https://sts.{region}.amazonaws.com` |
| `minio` | MinIO（自建） | aiobotocore STS Client | 同 S3 Endpoint |

**客户端无需关心 provider**，接口返回的 `endpoint_url` / `region_name` / `bucket_name` / `credentials` 格式统一，客户端统一用 AWS SDK 连接即可。

---

## 2. 认证方式

所有上传接口通过请求头认证设备身份：

| 请求头 | 说明 |
|--------|------|
| `X-Device-Code` | 设备编码（在平台注册后获取） |
| `X-Device-Secret` | 设备密钥（在平台注册后获取） |

---

## 3. OSS 存储路径格式

所有文件在 OSS 中的存储路径统一为：

```
slices/{device_code}/{YYYY-MM-DD}/{batch_id}/{file}
```

| 段 | 说明 | 示例 |
|------|------|------|
| `slices` | 固定前缀 | `slices` |
| `{device_code}` | 设备编码 | `scanner-001` |
| `{YYYY-MM-DD}` | 上传日期 | `2026-06-27` |
| `{batch_id}` | 批次 UUID（同一批文件共享） | `a1b2c3d4e5f6` |
| `{file}` | 文件名或相对路径（文件夹场景） | `slide.svs` / `Blocks/L00/B0000000C.jpg` |

示例：
- 单文件：`slices/scanner-001/2026-06-27/a1b2c3d4/slide-001.svs`
- 文件夹：`slices/scanner-001/2026-06-27/f1e2d3c4/Blocks/L00/B0000000C.jpg`

---

## 4. 支持的格式

| 格式 | 类型 | 说明 |
|------|------|------|
| SVS | 单文件 | 病理切片文件 |
| TIFF / TIF | 单文件 | 病理切片文件 |
| DZI | 文件夹 | Deep Zoom Image 格式 |
| LD | 文件夹 | 自有格式（Blocks / Fields / Thumbs 等） |

---

## 5. 接口列表

### 5.0 统一上传流程（单文件 + 文件夹通用）

适用于 SVS/TIFF 单文件和 LD/DZI 文件夹格式，流程完全统一：

```
① register（创建 DB 记录，返回 slice_id）
  → POST /slices/register
  
② upload-url（获取 STS 临时凭证）
  → POST /slices/upload-url?slice_id=xxx
  
③ 同步状态：uploading
  → PUT /slices/status { slice_id, status: "uploading" }
  
④ 直传 OSS（AWS SDK + STS 凭证）
  → s3_client.upload_file(local_path, bucket, f"{dir_key}/{filename}")
  
⑤ 同步状态：ready / error
  → PUT /slices/status { slice_id, status: "ready"/"error" }
```

#### 5.0.1 注册切片

**POST** `/api/datahub/slices/register`

**请求头**：
```
X-Device-Code: scanner-001
X-Device-Secret: xxxxxxxx
```

**请求体**：
```json
{
  "device_code": "scanner-001",
  "slide_code": "slide-001",
  "file_format": "SVS",
  "staining_type": "HE",
  "file_size": 1073741824
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| device_code | string | ✅ | 设备编码 |
| slide_code | string | ✅ | 切片编码（扫描仪 barcode） |
| file_format | string | ✅ | 文件格式：SVS/TIFF/TIF/DZI/LD |
| staining_type | string | ❌ | 染色类型：HE/IHC/PAS/Masson 等 |
| file_size | int | ✅ | 文件大小（字节），可为 0 |

**响应**：
```json
{
  "code": 201,
  "data": {
    "slice_id": 1,
    "slide_code": "slide-001",
    "status": "pending"
  },
  "message": "注册完成"
}
```

> **说明**：每次注册一个切片/样本。LD/DZI 文件夹作为一个样本注册一次，拿到 `slice_id` 后用同一个 STS 凭证上传所有子文件。

#### 5.0.2 获取上传凭证

**POST** `/api/datahub/slices/upload-url`

上传前即时调用，获取 STS 临时凭证。本接口会计算 `dir_key` 并写入 DB。

**Query 参数**：
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| slice_id | int | ✅ | 切片 ID（从 register 接口获取） |
| expires | int | ❌ | 凭证有效秒数（60s ~ 1h），默认 900 |

**响应**：
```json
{
  "code": 200,
  "data": {
    "slice_id": 1,
    "dir_key": "slices/scanner-001/2026-07-06/slide001_a1b2c3d4",
    "endpoint_url": "https://oss-cn-hangzhou.aliyuncs.com",
    "region_name": "cn-hangzhou",
    "bucket_name": "my-medical-bucket",
    "credentials": {
      "access_key_id": "STS.xxx",
      "secret_access_key": "xxx",
      "session_token": "xxx",
      "expiration": "2026-07-06T10:15:00+08:00"
    },
    "expires_in": 900
  }
}
```

| 字段 | 说明 |
|------|------|
| dir_key | 样本目录前缀，所有文件上传到此目录下 |
| endpoint_url | S3 Endpoint（阿里云 OSS、MinIO 等自建服务会返回） |
| region_name | S3 区域 |
| bucket_name | Bucket 名称 |
| credentials | STS 临时凭证，用于 AWS SDK 直传 |
| expires_in | 凭证有效期（秒） |

**单文件上传**：上传文件到 `{dir_key}/{filename}`
**文件夹上传**：上传所有文件到 `{dir_key}/{relative_path}`

#### 5.0.3 同步状态

**PUT** `/api/datahub/slices/status`

开始上传时：
```json
{"slice_id": 1, "status": "uploading"}
```

上传成功时：
```json
{"slice_id": 1, "status": "ready"}
```

上传失败时：
```json
{"slice_id": 1, "status": "error", "error_message": "网络超时"}
```

---

### 5.1 文件夹格式上传（DZI / LD）

文件夹格式使用与单文件完全相同的接口，区别仅在于客户端上传多个文件到同一目录。

#### 5.1.1 完整流程

与 5.0 统一流程相同：

```
① register（创建样本记录，file_format=LD/DZI）
  → POST /slices/register
  
② upload-url（获取 STS 临时凭证）
  → POST /slices/upload-url?slice_id=xxx
  
③ PUT /slices/status → { slice_id, status: "uploading" }
  
④ 使用 AWS SDK + STS 凭证上传所有文件到 {dir_key}/{relative_path}
  
⑤ PUT /slices/status → { slice_id, status: "ready" }
```

#### 5.1.2 注册样本

同 5.0.1，`file_format` 填 `LD` 或 `DZI`，`file_size` 填文件夹总大小。

```json
{
  "device_code": "scanner-001",
  "slide_code": "test20260701",
  "file_format": "LD",
  "staining_type": "HE",
  "file_size": 52428800
}
```

返回 `slice_id`。

#### 5.1.3 获取上传凭证

同 5.0.2，调用 `POST /slices/upload-url?slice_id=xxx` 获取 STS 凭证。

#### 5.1.4 直传 OSS

使用 AWS SDK + STS 凭证上传所有文件：

```python
import boto3

# 使用 STS 凭证创建客户端
s3_client = boto3.client(
    's3',
    endpoint_url="https://your-oss-endpoint",
    aws_access_key_id=credentials["access_key_id"],
    aws_secret_access_key=credentials["secret_access_key"],
    aws_session_token=credentials["session_token"],
)

# 遍历文件夹上传
for local_file in folder.glob("**/*"):
    if local_file.is_file():
        relative_path = local_file.relative_to(folder)
        s3_key = f"{dir_key}/{relative_path}"
        s3_client.upload_file(str(local_file), bucket, s3_key)
```

#### 5.1.5 同步状态

同 5.0.3，使用 `PUT /slices/status` 同步状态。

---

### 5.2 状态同步接口

扫描仪可在上传过程中实时同步状态，方便服务端追踪上传进度。

#### 5.2.1 更新切片状态

**PUT** `/api/datahub/slices/status`

**请求体**：
```json
{
  "slice_id": 1,
  "status": "uploading",
  "error_message": null
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| slice_id | int | ✅ | 切片记录 ID |
| status | string | ✅ | 状态值：`pending`、`uploading`、`ready`、`error` |
| error_message | string | ❌ | 错误信息（仅 `status=error` 时填写） |

**状态值说明**：
| 状态 | 含义 | 触发时机 |
|------|------|----------|
| `pending` | 待上传 | 预签名 URL 已获取，等待开始上传 |
| `uploading` | 上传中 | 客户端开始上传文件 |
| `ready` | 上传完成 | 文件已成功上传到 OSS |
| `error` | 上传失败 | 上传过程中发生错误 |

**响应**：
```json
{
  "code": 200,
  "data": {
    "id": 1,
    "app_code": "datahub",
    "device_id": 1,
    "batch_id": "a1b2c3d4e5f67890",
    "slide_code": "slide-001.svs",
    "file_format": "SVS",
    "staining_type": "HE",
    "file_size": 1073741824,
    "oss_key": "slices/scanner-001/2026-06-27/a1b2c3d4/slide-001.svs",
    "status": "uploading",
    "created_at": "2026-06-27T10:00:00+08:00",
    "updated_at": "2026-06-27T10:01:00+08:00"
  }
}
```

---

## 6. LD 文件夹结构参考

```
test20260701/
├── Blocks/              ← 上传
│   ├── L00/
│   │   ├── B0000000C.jpg
│   │   └── ...
│   └── L01/
├── Fields/              ← 上传
│   ├── F000000C.jpg
│   └── ...
├── Thumbs/              ← 上传
│   ├── Result.jpg
│   └── SampleState.txt
├── Data/                ← 可选上传
├── Report/              ← 可选上传
└── reports/             ← 通常排除
    └── *.docx
```

上传软件内置配置示例：
```json
{
  "include_dirs": ["Blocks", "Fields", "Thumbs"],
  "exclude_dirs": ["reports"],
  "file_types": [".jpg", ".txt", ".png"],
  "max_depth": 3
}
```

---

## 7. 完整上传流程示例

```python
import json
import httpx
import boto3
from pathlib import Path

API_BASE = "http://your-server/api/datahub"
DEVICE_CODE = "scanner-001"
DEVICE_SECRET = "your-device-secret"

HEADERS = {
    "X-Device-Code": DEVICE_CODE,
    "X-Device-Secret": DEVICE_SECRET,
}


def upload_file(local_path: str, slide_code: str, file_format: str = "SVS", staining_type: str = None):
    """
    单文件上传流程。
    """
    file_size = Path(local_path).stat().st_size
    
    # ① 注册切片
    resp = httpx.post(
        f"{API_BASE}/slices/register",
        headers=HEADERS,
        json={
            "device_code": DEVICE_CODE,
            "slide_code": slide_code,
            "file_format": file_format,
            "file_size": file_size,
            "staining_type": staining_type,
        },
    )
    slice_id = resp.json()["data"]["slice_id"]

    # ② 获取 STS 凭证
    resp = httpx.post(
        f"{API_BASE}/slices/upload-url",
        headers=HEADERS,
        params={"slice_id": slice_id},
    )
    data = resp.json()["data"]
    dir_key = data["dir_key"]
    credentials = data["credentials"]
    endpoint_url = data["endpoint_url"]
    bucket_name = data["bucket_name"]

    # ③ 同步状态：uploading
    httpx.put(
        f"{API_BASE}/slices/status",
        headers=HEADERS,
        json={"slice_id": slice_id, "status": "uploading"},
    )

    # ④ 直传 OSS（AWS SDK + STS）
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=credentials["access_key_id"],
        aws_secret_access_key=credentials["secret_access_key"],
        aws_session_token=credentials["session_token"],
    )
    s3_key = f"{dir_key}/{slide_code}"
    
    try:
        s3_client.upload_file(local_path, bucket_name, s3_key)
        # ⑤ 同步状态：ready
        httpx.put(
            f"{API_BASE}/slices/status",
            headers=HEADERS,
            json={"slice_id": slice_id, "status": "ready"},
        )
    except Exception as e:
        # 同步状态：error
        httpx.put(
            f"{API_BASE}/slices/status",
            headers=HEADERS,
            json={"slice_id": slice_id, "status": "error", "error_message": str(e)},
        )
        raise

    return slice_id


def upload_folder(folder_path: str, slide_code: str, file_format: str = "LD", staining_type: str = None):
    """
    文件夹上传流程（LD/DZI）。
    """
    folder = Path(folder_path)
    total_size = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
    
    # ① 注册切片
    resp = httpx.post(
        f"{API_BASE}/slices/register",
        headers=HEADERS,
        json={
            "device_code": DEVICE_CODE,
            "slide_code": slide_code,
            "file_format": file_format,
            "file_size": total_size,
            "staining_type": staining_type,
        },
    )
    slice_id = resp.json()["data"]["slice_id"]

    # ② 获取 STS 凭证
    resp = httpx.post(
        f"{API_BASE}/slices/upload-url",
        headers=HEADERS,
        params={"slice_id": slice_id},
    )
    data = resp.json()["data"]
    dir_key = data["dir_key"]
    credentials = data["credentials"]
    endpoint_url = data["endpoint_url"]
    bucket_name = data["bucket_name"]

    # ③ 同步状态：uploading
    httpx.put(
        f"{API_BASE}/slices/status",
        headers=HEADERS,
        json={"slice_id": slice_id, "status": "uploading"},
    )

    # ④ 直传 OSS（遍历文件夹）
    s3_client = boto3.client(
        's3',
        endpoint_url=endpoint_url,
        aws_access_key_id=credentials["access_key_id"],
        aws_secret_access_key=credentials["secret_access_key"],
        aws_session_token=credentials["session_token"],
    )
    
    try:
        for local_file in folder.rglob("*"):
            if local_file.is_file():
                relative_path = local_file.relative_to(folder)
                s3_key = f"{dir_key}/{relative_path}"
                s3_client.upload_file(str(local_file), bucket_name, s3_key)
        
        # ⑤ 同步状态：ready
        httpx.put(
            f"{API_BASE}/slices/status",
            headers=HEADERS,
            json={"slice_id": slice_id, "status": "ready"},
        )
    except Exception as e:
        httpx.put(
            f"{API_BASE}/slices/status",
            headers=HEADERS,
            json={"slice_id": slice_id, "status": "error", "error_message": str(e)},
        )
        raise

    return slice_id
```

---

## 8. 注意事项

| 项目 | 说明 |
|------|------|
| 凭证有效期 | 60 ~ 3600 秒，默认 900 秒（15 分钟） |
| 单次文件数量 | 无限制（STS 凭证有效期内可自由上传） |
| 文件大小限制 | 根据设备配置（默认 500 MB） |
| 上传方式 | 使用 AWS SDK + STS 临时凭证直传 |
| 目录结构 | 文件夹上传时保留完整目录结构（relative_path） |
| 格式校验 | 服务端会校验设备 `allowed_formats` 配置 |
| 状态同步 | 建议上传时同步状态（`uploading` → `ready`/`error`） |
| 染色类型 | `staining_type` 为可选字段，可填 `null` 或不填 |
| 多云透明 | 客户端统一使用 AWS SDK，服务端根据 provider 自动适配阿里云/AWS/MinIO |
| STS 安全机制 | 阿里云使用 AssumeRole（RAM 角色），临时凭证仅有指定目录的 PutObject 权限 |

---

## 9. 错误码

| HTTP 状态码 | 说明 |
|-------------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 401 | 认证失败（设备编码或密钥错误） |
| 403 | 设备已禁用 |
| 422 | 参数校验失败（格式不支持、文件超限等） |
| 502 | OSS 操作失败 |
