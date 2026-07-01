---
name: "pythonanywhere-deploy"
description: "Deploy Flask apps to PythonAnywhere via file upload API. Auto-detects changed files, uploads them, reloads webapp, and verifies. Invoke when user asks to deploy/update/push code online, or mentions 3579828593.pythonanywhere.com."
---

# PythonAnywhere 智能部署技能

## 适用场景

当用户提到以下任何一种需求时，自动调用此技能：
- "部署到线上" / "更新线上" / "推送代码" / "上线"
- "看看网站状态" / "网站正常吗"
- "重载应用" / "重启"
- 任何涉及 `3579828593.pythonanywhere.com` 的操作
- 代码提交后需要同步到生产环境

## 核心信息

| 项目 | 值 |
|------|-----|
| 线上地址 | https://3579828593.pythonanywhere.com |
| GitHub 仓库 | https://github.com/3579828593/RIcardo.git |
| PythonAnywhere 用户名 | 3579828593 |
| Python 版本 | 3.10 |
| 项目路径（远程） | ~/RIcardo/backend |
| 本地项目路径 | d:\期末冲刺刷题系统 |
| 部署脚本 | d:\期末冲刺刷题系统\scripts\pa_deploy.py |
| 智能部署脚本 | d:\期末冲刺刷题系统\scripts\pa_smart_deploy.py |
| API Token 文件 | ~/.pa_token |
| 用户名文件 | ~/.pa_username |

## 智能部署工作流（主要方式）

### 核心逻辑：检测变更 → 分类部署 → 验证

当用户说"部署"、"更新线上"、"上线"时，执行以下智能流程：

#### Step 1: 检测变更文件

```bash
cd d:\期末冲刺刷题系统
git diff --name-only HEAD~1 HEAD
# 如果有未提交的变更，也检测：
git diff --name-only
```

#### Step 2: 分类部署策略

根据变更的文件类型，选择不同的部署策略：

| 文件类型 | 部署策略 |
|----------|----------|
| `backend/*.py` (Python 后端) | 上传文件 → 清除 .pyc 缓存 → 重载 |
| `backend/templates/*.html` | 上传文件 → 重载 |
| `backend/static/js/*.js` | 上传文件 → 重载（sw.js 版本号需递增） |
| `backend/static/css/*.css` | 上传文件 → 重载 |
| `backend/static/sw.js` | 上传文件 → 重载 |
| `backend/requirements.txt` | 上传 → 远程 pip install → 重载 |
| `backend/render_init.py` | 上传 → 远程执行初始化 → 重载 |
| 无变更但需要重载 | 仅重载 |

#### Step 3: 通过 API 上传文件

使用 PythonAnywhere 文件上传 API（不需要控制台，不会出现 412 错误）：

```python
# 核心上传逻辑
import urllib.request, os

def upload_file(local_path, remote_path, token, username):
    with open(local_path, "rb") as f:
        content = f.read()
    boundary = "----pa_deploy_boundary"
    filename = os.path.basename(local_path)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="content"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
    url = f"https://www.pythonanywhere.com/api/v0/user/{username}/files/path{remote_path}"
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Token {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.status == 200 or resp.status == 201
```

#### Step 4: 重载应用

```python
url = f"https://www.pythonanywhere.com/api/v0/user/{username}/webapps/{domain}/reload/"
req = urllib.request.Request(url, data=b"", method="POST", headers={
    "Authorization": f"Token {token}",
})
urllib.request.urlopen(req, timeout=30)
```

#### Step 5: 验证部署

部署后自动验证：
1. 访问 `/api/questions?page=1&per_page=1` — 确认题库正常
2. 访问 `/api/auth/me` — 确认认证系统正常（应返回 401）
3. 访问 `/api/banks?scope=official` — 确认题库 API 正常
4. 如果有新 API 端点，针对性验证

### 使用智能部署脚本

```bash
# 自动检测变更并部署（最常用）
cd d:\期末冲刺刷题系统
python scripts\pa_smart_deploy.py

# 指定文件部署
python scripts\pa_smart_deploy.py backend/app.py backend/database.py

# 全量部署（上传所有关键文件）
python scripts\pa_smart_deploy.py --all

# 仅重载（不上传文件）
python scripts\pa_smart_deploy.py --reload-only
```

## 传统部署方式（备用）

### 控制台方式（需要浏览器先加载控制台）

```bash
python scripts\pa_deploy.py update     # git pull + 重载
python scripts\pa_deploy.py status     # 查看状态
python scripts\pa_deploy.py logs       # 查看日志
python scripts\pa_deploy.py reload     # 仅重载
python scripts\pa_deploy.py restart    # 强制重启
python scripts\pa_deploy.py backup     # 备份数据库
```

注意：控制台方式可能返回 412 错误（"Console not yet started"），此时改用智能部署脚本。

## Agent 执行指引

当 Agent 收到部署相关请求时，按以下决策树执行：

```
用户请求部署/更新
├── 检查 ~/.pa_token 和 ~/.pa_username 是否存在
│   ├── 不存在 → 提示用户运行 setup
│   └── 存在 → 继续
├── 检测变更文件 (git diff)
│   ├── 无变更 → 询问是否仅重载
│   └── 有变更 → 分类文件
├── 执行部署
│   ├── Python 文件变更 → 上传 + 清缓存 + 重载
│   ├── 静态文件变更 → 上传 + 重载
│   └── 数据库变更 → 上传 + 运行迁移 + 重载
├── 验证部署
│   ├── API 可访问 → 报告成功
│   └── API 异常 → 查看日志 + 故障排除
└── 报告结果（线上地址 + 验证状态）
```

## 故障排除

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| 412 Console not started | 控制台未在浏览器加载 | 改用 `pa_smart_deploy.py`（文件上传 API） |
| 500 错误 | SQLite 锁定或代码错误 | `pa_deploy.py restart` 或查看日志 |
| 模块导入错误 | 依赖未装到 3.10 | `pa_deploy.py console "pip3.10 install --user -r ~/RIcardo/backend/requirements.txt"` |
| 502 错误 | 应用未启动 | `pa_deploy.py reload` |
| 上传失败 401 | Token 过期 | 重新生成 API Token 并运行 setup |
| 页面空白 | WSGI 配置错误 | `pa_deploy.py deploy`（完整重部署） |

## 注意事项

- **优先使用智能部署**：`pa_smart_deploy.py` 不依赖控制台，更可靠
- **免费账户限制**：每天 100 CPU 秒，512MB 存储
- **3 个月续期**：免费 Web 应用每 3 个月需在网页上点击续期
- **sw.js 版本号**：每次修改前端文件时，递增 sw.js 中的 CACHE_VERSION
- **git push 前测试**：推送前建议运行 `python -m pytest backend/tests/ --ignore=backend/tests/e2e`
- **数据库迁移**：如果 database.py 有 schema 变更，部署后远程会自动执行 _init_db() 迁移
