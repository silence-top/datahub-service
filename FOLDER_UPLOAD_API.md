# 文件夹格式上传 API 文档

## 📋 支持的格式

| 格式 | 类型 | 说明 |
|------|------|------|
| **SVS** | 单文件 | 病理切片文件 |
| **TIFF** | 单文件 | 病理切片文件 |
| **TIF** | 单文件 | 病理切片文件 |
| **DZI** | 文件夹 | Deep Zoom Image 格式 |
| **LD** | 文件夹 | 自有格式（包含 Blocks/Fields/Thumbs 等子目录） |

---

## 🎯 文件夹格式上传流程

### 架构图

```
┌─────────────────────────────────────────┐
│  上传软件（客户端）                       │
│                                         │
│  1. 遍历文件夹（根据配置过滤）           │
│  2. 生成文件清单（filename + path）      │
│  3. 请求预签名 URL                       │
│  4. 直传 OSS（文件不经后端）             │
│  5. 确认上传完成                         │
└─────────────────────────────────────────┘
           ↓
┌─────────────────────────────────────────┐
│  服务端（datahub-service）               │
│                                         │
│  - 生成预签名 URL                        │
│  - 记录文件元数据到数据库                │
│  - file_format = "DZI" 或 "LD"          │
│  - relative_path 保留目录结构            │
└─────────────────────────────────────────┘
```

---

## 📡 API 接口

### 1️⃣ 生成文件夹预签名 URL

**接口**：`POST /api/v1/slices/folder-presign-urls`

**请求体**：
```json
{
  "format": "LD",
  "folder_name": "test20260701",
  "staining_type": "HE",
  "files": [
    {
      "filename": "B0000000C.jpg",
      "relative_path": "Blocks/L00/B0000000C.jpg",
      "file_size": 69321
    },
    {
      "filename": "B0000001C.jpg",
      "relative_path": "Blocks/L00/B0000001C.jpg",
      "file_size": 69587
    }
  ]
}
```

**响应**：
```json
{
  "code": 200,
  "data": {
    "batch_id": "a1b2c3d4e5f6...",
    "presigns": [
      {
        "filename": "B0000000C.jpg",
        "upload_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...",
        "oss_key": "app_code/a1b2c3d4/Blocks/L00/B0000000C.jpg"
      },
      {
        "filename": "B0000001C.jpg",
        "upload_url": "https://bucket.oss-cn-hangzhou.aliyuncs.com/...",
        "oss_key": "app_code/a1b2c3d4/Blocks/L00/B0000001C.jpg"
      }
    ],
    "expires_in": 300
  }
}
```

---

### 2️⃣ 客户端直传 OSS

上传软件使用预签名 URL 直接上传文件到 OSS（文件不经过后端）。

```python
import httpx

for presign in presigns:
    with open(local_file_path, "rb") as f:
        httpx.put(
            presign["upload_url"],
            content=f.read(),
            headers={"Content-Type": "application/octet-stream"}
        )
```

---

### 3️⃣ 确认文件夹上传完成

**接口**：`POST /api/v1/slices/folder-confirm`

**Query 参数**：
- `batch_id`: 批次 ID（从预签名响应获取）
- `oss_keys`: JSON 数组，每个文件的 OSS key

**请求体**：
```json
{
  "format": "LD",
  "folder_name": "test20260701",
  "staining_type": "HE",
  "files": [
    {
      "filename": "B0000000C.jpg",
      "relative_path": "Blocks/L00/B0000000C.jpg",
      "file_size": 69321
    },
    {
      "filename": "B0000001C.jpg",
      "relative_path": "Blocks/L00/B0000001C.jpg",
      "file_size": 69587
    }
  ]
}
```

**响应**：
```json
{
  "code": 201,
  "data": {
    "batch_id": "a1b2c3d4e5f6...",
    "folder_name": "test20260701",
    "file_format": "LD",
    "success_count": 2,
    "failure_count": 0,
    "failures": []
  },
  "message": "文件夹上传完成"
}
```

---

## 🗂️ 数据库存储

### SliceFile 表

| 字段 | 值示例 | 说明 |
|------|--------|------|
| `file_format` | `"LD"` | 文件夹格式标识 |
| `original_name` | `"B0000000C.jpg"` | 文件名 |
| `relative_path` | `"Blocks/L00/B0000000C.jpg"` | 相对路径 |
| `oss_key` | `"app_code/batch_id/Blocks/L00/B0000000C.jpg"` | OSS 存储路径 |
| `batch_id` | `"a1b2c3d4e5f6..."` | 批次 ID（关联同一文件夹） |

**特点**：
- 文件夹内每个文件都有一条记录
- `file_format` 统一为 `"LD"` 或 `"DZI"`
- 通过 `batch_id` 关联同一个文件夹的所有文件
- `relative_path` 保留完整的目录结构

---

## 🛠️ 客户端实现示例

### Python 示例

```python
import os
import json
import httpx
from pathlib import Path

# 配置
API_BASE = "http://localhost:5001/api/v1"
APP_CODE = "diagnosis"
FOLDER_PATH = "D:/Data/SampleData/2026-04-21/test20260701"
FORMAT = "LD"

# LD 格式配置（上传软件内置）
LD_CONFIG = {
    "include_dirs": ["Blocks", "Fields", "Thumbs"],
    "exclude_dirs": ["reports", "Data"],
    "file_types": [".jpg", ".txt", ".png"],
    "max_depth": 3
}

def collect_files(folder_path, config):
    """遍历文件夹，根据配置过滤"""
    files = []
    
    for item in Path(folder_path).iterdir():
        # 排除目录
        if item.name in config["exclude_dirs"]:
            continue
        
        # 包含目录
        if item.name in config["include_dirs"]:
            # 递归遍历（不超过 max_depth）
            for file in item.rglob("*"):
                if file.is_file() and file.suffix in config["file_types"]:
                    rel_path = file.relative_to(folder_path)
                    files.append({
                        "filename": file.name,
                        "relative_path": str(rel_path),
                        "file_size": file.stat().st_size
                    })
    
    return files

def upload_folder():
    """上传文件夹"""
    # 1. 收集文件
    files = collect_files(FOLDER_PATH, LD_CONFIG)
    
    # 2. 请求预签名 URL
    response = httpx.post(
        f"{API_BASE}/slices/folder-presign-urls",
        headers={"X-App-Code": APP_CODE, "X-User-Id": "1"},
        json={
            "format": FORMAT,
            "folder_name": Path(FOLDER_PATH).name,
            "staining_type": "HE",
            "files": files
        }
    )
    presign_data = response.json()["data"]
    batch_id = presign_data["batch_id"]
    presigns = presign_data["presigns"]
    
    # 3. 直传 OSS
    oss_keys = []
    for i, presign in enumerate(presigns):
        with open(files[i]["relative_path"], "rb") as f:
            httpx.put(
                presign["upload_url"],
                content=f.read(),
                headers={"Content-Type": "application/octet-stream"}
            )
        oss_keys.append(presign["oss_key"])
    
    # 4. 确认上传完成
    response = httpx.post(
        f"{API_BASE}/slices/folder-confirm",
        headers={"X-App-Code": APP_CODE, "X-User-Id": "1"},
        params={
            "batch_id": batch_id,
            "oss_keys": json.dumps(oss_keys)
        },
        json={
            "format": FORMAT,
            "folder_name": Path(FOLDER_PATH).name,
            "staining_type": "HE",
            "files": files
        }
    )
    
    print(f"上传完成：batch_id={batch_id}")

if __name__ == "__main__":
    upload_folder()
```

---

## 🎯 优势总结

| 优势 | 说明 |
|------|------|
| ✅ **高性能** | 文件直传 OSS，不经过后端 |
| ✅ **灵活配置** | 上传软件内置配置，可独立升级 |
| ✅ **完整记录** | 数据库记录每个文件的相对路径 |
| ✅ **批量处理** | 支持大规模文件夹（数千文件） |
| ✅ **格式标识** | `file_format` 清晰标识文件夹类型 |

---

## 📝 注意事项

1. **预签名 URL 有效期**：300 秒（5 分钟），超时需重新请求
2. **单次上传限制**：最多 10000 个文件
3. **文件大小限制**：根据设备配置（默认 500 MB）
4. **目录结构保留**：OSS 存储路径包含完整的相对路径

---

## 🔧 故障排查

### 问题 1：预签名 URL 过期

**现象**：上传 OSS 时报 403 Forbidden

**解决**：重新调用 `/folder-presign-urls` 获取新的 URL

### 问题 2：文件格式不支持

**现象**：服务端返回 `UnsupportedFileFormatError`

**解决**：检查 `format` 字段，必须为 `"DZI"` 或 `"LD"`

### 问题 3：文件数量超限

**现象**：服务端返回验证错误

**解决**：分批上传，每批不超过 10000 个文件
