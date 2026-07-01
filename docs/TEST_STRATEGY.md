# 测试策略文档

> 期末冲刺刷题系统 — 测试分层、质量阈值与覆盖率目标

---

## 目录

1. [测试概览](#1-测试概览)
2. [测试分层](#2-测试分层)
3. [当前基线](#3-当前基线)
4. [质量阈值](#4-质量阈值)
5. [覆盖率目标](#5-覆盖率目标)
6. [测试命令](#6-测试命令)
7. [权限回归矩阵](#7-权限回归矩阵)
8. [测试文件详细说明](#8-测试文件详细说明)
9. [测试编写规范](#9-测试编写规范)
10. [CI/CD 集成](#10-cicd-集成)

---

## 1. 测试概览

### 1.1 测试理念

本系统采用**分层测试策略**，从单元测试到端到端测试逐层覆盖，确保每个功能层级都有对应的质量保障：

```
┌─────────────────────────────────────────────────────────┐
│                     E2E 测试                             │
│         Playwright 浏览器自动化 (test_quiz_flow)         │
│      页面加载 / 答题流程 / 数据隔离 / 离线模式           │
├─────────────────────────────────────────────────────────┤
│                 Frontend 测试                            │
│          UI 冒烟测试 / Vue 挂载验证                      │
├─────────────────────────────────────────────────────────┤
│                   回归测试                               │
│          关键 Bug 复现 / 判分逻辑 / API 契约             │
├─────────────────────────────────────────────────────────┤
│                 集成测试                                 │
│      管理员导入流程 / 数据库迁移验证                     │
├─────────────────────────────────────────────────────────┤
│                   单元测试                               │
│   API / Auth / Banks / CSV Importer / Sanitize          │
└─────────────────────────────────────────────────────────┘
```

### 1.2 测试框架

| 工具 | 用途 | 版本要求 |
|------|------|----------|
| pytest | 测试框架 | 内置（Python 标准库 unittest 也支持） |
| Flask test_client | API 集成测试 | Flask 3.0.3 内置 |
| Playwright | E2E 浏览器测试 | 需单独安装 |
| pytest-cov | 覆盖率统计 | 需在 pyproject.toml 中启用 |

---

## 2. 测试分层

### 2.1 Unit（单元测试）

单元测试聚焦于单个函数/模块的独立逻辑，使用临时数据库和 Flask test_client 隔离测试。

| 测试文件 | 测试目标 | 说明 |
|----------|----------|------|
| `test_api.py` | API 端点单元测试 | 题目搜索、随机题目、提交答案、统计、错题、收藏、分页校验 |
| `test_auth.py` | 认证模块单元测试 | 密码哈希/验证、CSRF token、限流、注册/登录/登出 API |
| `test_banks.py` | 题库 CRUD + 权限单元测试 | `can_read_bank`/`can_write_bank` 决策表、题库创建/列表/删除、CSV 导入、订阅、举报 |
| `test_csv_importer.py` | CSV 解析器单元测试 | `parse_csv()` 表头校验、字段校验、题型校验、答案解析、模板生成 |
| `test_sanitize.py` | 题目消毒单元测试 | `sanitize_question()` 敏感词检测、HTML 转义、长度校验 |

**单元测试特征**：
- 使用 `tempfile.TemporaryDirectory()` 创建临时数据库
- 每个测试独立，不依赖外部状态
- `conftest.py` 的 `_clear_auth_test_data` fixture 自动清理 `rate_limits` 和 `users` 表

### 2.2 Integration（集成测试）

集成测试验证多个模块协作的完整流程。

| 测试文件 | 测试目标 | 说明 |
|----------|----------|------|
| `test_admin_import.py` | 管理员 CSV 导入完整流程 | 文件上传、JSON 内容、解析错误处理、去重、模板下载 |
| `test_migrations.py` | 数据库迁移验证 | schema 演进、列添加、表重建、数据完整性 |

**集成测试特征**：
- 使用完整 Flask app + 真实 SQLite 数据库
- 验证多步骤业务流程（如 CSV 上传 → 解析 → 消毒 → 写入 → 计数更新）
- 验证数据库迁移的幂等性和数据完整性

### 2.3 Regression（回归测试）

回归测试复现历史关键 Bug，确保修复后不再复发。

| 测试文件 | 测试目标 | 说明 |
|----------|----------|------|
| `test_regression.py` | 关键 Bug 回归测试 | 判分逻辑、API 契约、安全响应头、幂等删除、管理员鉴权 |

**回归测试覆盖的 Bug 类别**：

| Bug 类别 | 测试用例 | 验证内容 |
|----------|----------|----------|
| 多选判分顺序 | `test_multiple_choice_order_does_not_affect_scoring` | 多选答案顺序不影响判分 |
| 判断题别名 | `test_true_false_accepts_common_false_aliases` | 接受"错"/"false"/"B"/"0"等写法 |
| 判断题误判 | `test_true_false_rejects_wrong_alias` | "A"不等于"错" |
| API 契约 | `test_questions_api_uses_new_schema_without_legacy_wrapper` | 响应不含旧版 `code`/`msg` 字段 |
| 分页参数 | `test_questions_api_rejects_negative_pagination_limits` | 负数页码返回 400 |
| 安全响应头 | `test_security_headers_are_set_on_responses` | X-Content-Type-Options 等存在 |
| Jinja/Vue 冲突 | `test_index_page_renders_vue_template_without_jinja_conflict` | Vue `{{ }}` 原样保留 |
| 收藏幂等删除 | `test_delete_favorite_is_idempotent_and_does_not_create_favorite` | DELETE 未收藏项不创建收藏 |
| 管理员鉴权 | `test_admin_write_requires_token` | 无 token 返回 401 |

### 2.4 Frontend（前端测试）

前端测试验证页面渲染和 UI 行为。

| 测试文件 | 测试目标 | 说明 |
|----------|----------|------|
| `test_frontend.py` | 前端页面测试 | HTML 结构、Vue 挂载、静态资源 |
| `ui_smoke.py` | UI 冒烟测试 | 基本页面可访问性 |

### 2.5 E2E（端到端测试）

端到端测试使用 Playwright 模拟真实用户操作，验证完整用户路径。

| 测试文件 | 测试目标 | 说明 |
|----------|----------|------|
| `e2e/test_quiz_flow.py` | 核心用户路径 E2E | 页面加载、答题流程、数据隔离、离线模式 |

**E2E 测试类**：

| 测试类 | 测试用例 | 验证内容 |
|--------|----------|----------|
| `TestQuizLoading` | `test_page_loads_without_error` | 页面加载无 JS 错误 |
| | `test_skeleton_disappears` | 骨架屏在 Vue 挂载后消失 |
| `TestQuizFlow` | `test_question_displays` | 题目正常显示 |
| | `test_progress_bar_visible` | 进度条可见 |
| | `test_select_and_submit` | 选择选项并提交答案 |
| | `test_next_question_button` | "下一题"按钮可点击 |
| `TestDataIsolation` | `test_fresh_session_no_progress` | 新会话初始状态为 0 题已答 |
| `TestOfflineMode` | `test_offline_question_cached` | 离线时仍可查看缓存题目 |

---

## 3. 当前基线

### 3.1 测试统计

| 指标 | 当前值 |
|------|--------|
| 测试文件数 | 11 |
| 测试项总数 | 151 |
| 通过率 | 100%（全通过） |
| 测试框架 | pytest + unittest |
| E2E 框架 | Playwright |

### 3.2 测试文件清单

| # | 文件路径 | 层级 | 测试项数（约） |
|---|----------|------|----------------|
| 1 | `backend/tests/test_api.py` | Unit | ~30 |
| 2 | `backend/tests/test_auth.py` | Unit | ~22 |
| 3 | `backend/tests/test_banks.py` | Unit | ~25 |
| 4 | `backend/tests/test_csv_importer.py` | Unit | ~15 |
| 5 | `backend/tests/test_sanitize.py` | Unit | ~10 |
| 6 | `backend/tests/test_admin_import.py` | Integration | ~12 |
| 7 | `backend/tests/test_migrations.py` | Integration | ~10 |
| 8 | `backend/tests/test_regression.py` | Regression | ~9 |
| 9 | `backend/tests/test_frontend.py` | Frontend | ~8 |
| 10 | `backend/tests/ui_smoke.py` | Frontend | ~5 |
| 11 | `backend/tests/e2e/test_quiz_flow.py` | E2E | ~8 |

### 3.3 测试环境配置

**`backend/tests/conftest.py`**：

```python
import os
# 测试环境使用固定 admin token
os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")

import pytest

@pytest.fixture(autouse=True)
def _clear_auth_test_data():
    """每个测试前清空 rate_limits 和 users 表，
    避免限流累积和重复用户影响测试。"""
    try:
        from app import db
        with db.connection() as conn:
            conn.execute("DELETE FROM rate_limits")
            conn.execute("DELETE FROM users")
    except Exception:
        pass
    yield
```

**`backend/tests/e2e/conftest.py`**：

```python
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="module")
def browser():
    """启动浏览器实例"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()
```

---

## 4. 质量阈值

### 4.1 通过标准

| 阈值项 | 要求 | 说明 |
|--------|------|------|
| pytest 全通过 | **必须** | 所有测试项必须通过，0 失败 |
| 无 error 状态 | **必须** | 无收集错误或执行错误 |
| 无 skip（除 E2E） | 建议 | 非 E2E 测试不应跳过 |
| E2E 可选通过 | 建议 | E2E 需要本地服务器 + Playwright，CI 中可选 |

### 4.2 权限测试覆盖要求

权限测试必须覆盖以下维度的组合：

| 维度 | 覆盖值 |
|------|--------|
| 身份 | `anonymous` / `student` / `owner` / `admin` |
| 题库可见性 | `private` / `public` / `unlisted` |
| 题库状态 | `active` / `hidden` / `deleted` |
| 操作 | `read` / `write` / `import` / `subscribe` |

**必须覆盖的权限场景**：

| 场景 | 预期结果 | 已覆盖测试 |
|------|----------|------------|
| anonymous → private bank | 403 | `test_can_read_private_bank_non_owner` |
| non-owner → private bank | 403 | `test_cannot_access_private_bank_via_legacy_api` |
| owner → private bank | 200 | `test_can_read_private_bank_owner` |
| admin → private bank | 200 | `test_can_read_hidden_bank_admin_only` |
| anyone → public/active bank | 200 | `test_can_read_public_bank` |
| anyone → official bank | 200 | `test_can_read_official_bank` |
| non-admin → hidden/deleted bank | 403 | `test_can_read_hidden_bank_admin_only` |
| admin → hidden/deleted bank | 200 | `test_can_read_hidden_bank_admin_only` |
| non-owner → import to bank | 403 | `test_api_import_to_other_user_bank` |
| non-owner → subscribe private bank | 403 | `test_cannot_subscribe_private_bank` |

### 4.3 回归测试要求

| 规则 | 说明 |
|------|------|
| 每个 Critical bug | **必须**有对应的回归测试 |
| 回归测试命名 | `test_<bug_description>` 或 `test_<scenario>_does_not_<bug_behavior>` |
| 回归测试位置 | `test_regression.py` 或对应层级的测试文件 |
| 回归测试生命周期 | 永久保留，不删除 |

### 4.4 Bug 严重级别与测试要求

| 严重级别 | 定义 | 测试要求 |
|----------|------|----------|
| Critical | 安全漏洞、数据丢失、核心功能不可用 | 必须有回归测试 |
| High | 主要功能异常、权限绕过 | 必须有回归测试 |
| Medium | 次要功能异常、边界条件错误 | 建议有回归测试 |
| Low | UI 界面问题、文案错误 | 视情况添加 |

---

## 5. 覆盖率目标

### 5.1 pytest-cov 配置

在项目根目录创建 `pyproject.toml` 启用覆盖率统计：

```toml
[tool.pytest.ini_options]
testpaths = ["backend/tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["backend"]
omit = [
    "backend/tests/*",
    "backend/wsgi.py",
    "backend/render_init.py",
    "backend/data_migration.py",
    "backend/desktop_app.py",
    "backend/lite.py",
]

[tool.coverage.report]
show_missing = true
precision = 2
fail_under = 60

[tool.coverage.html]
directory = "htmlcov"
```

### 5.2 覆盖率阈值

| 模块 | 最低行覆盖率 | 说明 |
|------|-------------|------|
| **整体** | **60%** | `fail_under = 60`，低于此值 CI 失败 |
| `auth.py` | 90% | 认证模块，安全关键 |
| `permissions.py` | 95% | 权限模块，安全关键 |
| `csv_importer.py` | 85% | 解析逻辑，数据安全 |
| `database.py` | 60% | 数据层，部分 CRUD 分支较多 |
| `app.py` | 50% | 路由层，部分端点较难全覆盖 |
| `config.py` | 80% | 配置加载 |

### 5.3 覆盖率运行命令

```bash
# 运行测试并生成覆盖率报告
python -m pytest backend/tests/ -v --tb=short --cov=backend --cov-report=term-missing --cov-report=html

# 仅查看终端报告
python -m pytest backend/tests/ -v --tb=short --cov=backend --cov-report=term-missing

# 查看 HTML 报告
# 打开 htmlcov/index.html
```

### 5.4 覆盖率提升策略

| 策略 | 优先级 | 说明 |
|------|--------|------|
| 补充权限分支测试 | 高 | `database.py` 中 `if user_id / else session_id` 分支 |
| 补充边界条件测试 | 高 | 空输入、超长输入、非法类型 |
| 补充错误路径测试 | 中 | 数据库异常、文件读取失败 |
| 移除死代码 | 中 | `exam_sessions`/`settings` 未使用的方法 |
| E2E 覆盖更多路径 | 低 | 登录流程、题库创建流程 |

---

## 6. 测试命令

### 6.1 单元 + 集成 + 回归测试

```bash
# 运行全部非 E2E 测试（推荐）
python -m pytest backend/tests/ -v --tb=short

# 运行指定测试文件
python -m pytest backend/tests/test_api.py -v --tb=short

# 运行指定测试类
python -m pytest backend/tests/test_regression.py::ScoringRegressionTest -v

# 运行指定测试用例
python -m pytest backend/tests/test_regression.py::ScoringRegressionTest::test_multiple_choice_order_does_not_affect_scoring -v

# 运行并显示打印输出
python -m pytest backend/tests/ -v --tb=short -s

# 仅运行上次失败的测试
python -m pytest backend/tests/ --lf -v

# 停止在第一个失败
python -m pytest backend/tests/ -v --tb=short -x
```

### 6.2 E2E 测试

```bash
# 前置条件：安装 Playwright
pip install playwright
playwright install chromium

# 前置条件：启动本地 Flask 服务器
cd backend && python app.py

# 运行 E2E 测试
python -m pytest backend/tests/e2e/ -v

# 运行指定 E2E 测试类
python -m pytest backend/tests/e2e/test_quiz_flow.py::TestQuizFlow -v
```

### 6.3 覆盖率测试

```bash
# 运行测试并生成覆盖率报告
python -m pytest backend/tests/ -v --tb=short --cov=backend --cov-report=term-missing --cov-report=html --cov-fail-under=60
```

### 6.4 全量测试（含覆盖率）

```bash
# 完整测试流程
python -m pytest backend/tests/ -v --tb=short --cov=backend --cov-report=term-missing --cov-report=html --cov-fail-under=60 && python -m pytest backend/tests/e2e/ -v
```

---

## 7. 权限回归矩阵

### 7.1 完整权限矩阵

权限回归矩阵是系统安全测试的核心，确保每种身份 × 题库状态 × 操作的组合都有预期结果：

| 身份 | 题库类型 | 操作 | 预期状态码 | 测试覆盖 |
|------|----------|------|-----------|----------|
| anonymous | private | read | **403** | `test_can_read_private_bank_non_owner` |
| anonymous | private | write | **403** | `test_can_write_bank_non_owner` |
| anonymous | private | import | **403** | `test_api_import_to_other_user_bank` |
| anonymous | private | subscribe | **403** | `test_cannot_subscribe_private_bank` |
| anonymous | public/active | read | **200** | `test_can_read_public_bank` |
| anonymous | public/active | subscribe | **401** | 需登录才能订阅 |
| anonymous | official | read | **200** | `test_can_read_official_bank` |
| anonymous | hidden | read | **403** | `test_can_read_hidden_bank_admin_only` |
| anonymous | deleted | read | **403** | `test_can_read_hidden_bank_admin_only` |
| non-owner (student) | private | read | **403** | `test_cannot_access_private_bank_via_legacy_api` |
| non-owner (student) | private | write | **403** | `test_can_write_bank_non_owner` |
| non-owner (student) | private | import | **403** | `test_api_import_to_other_user_bank` |
| non-owner (student) | public/active | read | **200** | `test_can_read_public_bank` |
| non-owner (student) | public/active | subscribe | **200** | `test_subscribe_bank` |
| **owner** | private | read | **200** | `test_can_read_private_bank_owner` |
| **owner** | private | write | **200** | `test_can_write_bank_owner` |
| **owner** | private | import | **201** | `test_api_import_csv_to_bank` |
| owner | public/active | read | **200** | 隐含覆盖 |
| owner | hidden | read | **403** | `test_can_read_hidden_bank_admin_only` |
| **admin** | private | read | **200** | `test_can_read_hidden_bank_admin_only` |
| **admin** | private | write | **200** | `test_can_write_official_bank_admin` |
| **admin** | hidden | read | **200** | `test_can_read_hidden_bank_admin_only` |
| **admin** | deleted | read | **200** | `test_can_read_hidden_bank_admin_only` |
| admin | official | write | **200** | `test_can_write_official_bank_admin` |
| student | official | write | **403** | `test_can_write_official_bank_admin` |

### 7.2 矩阵简化版

```
              private    public/active    hidden/deleted    official
anonymous      403          200              403              200
non-owner      403          200              403              200
owner          200          200              403              200
admin          200          200              200              200
```

### 7.3 订阅权限矩阵

| 身份 | 题库类型 | 订阅 | 退订 | 预期 |
|------|----------|------|------|------|
| anonymous | 任意 | — | — | **401**（需登录） |
| student | private | POST | — | **403** |
| student | public/active | POST | — | **200** |
| student | public/active | — | DELETE | **200** |
| student | unlisted | POST | — | **403** |

### 7.4 管理员鉴权矩阵

| 操作 | 无 token | 错误 token | 正确 token | 管理禁用 |
|------|----------|-----------|-----------|----------|
| GET /api/admin/questions | **401** | **401** | **200** | **403** |
| POST /api/admin/import/csv | **401** | **401** | **201** | **403** |
| GET /api/admin/template | **401** | **401** | **200** | **403** |
| POST /api/admin/dedupe | **401** | **401** | **200** | **403** |
| POST /api/admin/backup | **401** | **401** | **200** | **403** |
| GET /api/admin/reports | **401** | **401** | **200** | **403** |
| PUT /api/admin/reports/<id> | **401** | **401** | **200** | **403** |
| DELETE /api/admin/questions/<id> | **401** | **401** | **200** | **403** |

已覆盖测试：`test_admin_write_requires_token`（验证无 token → 401）

---

## 8. 测试文件详细说明

### 8.1 test_api.py

**测试范围**：题目搜索、随机题目、提交答案、统计、错题、收藏、分页

**关键测试用例**：

| 用例 | 验证内容 |
|------|----------|
| 题目搜索 | course/chapter/type/keyword 筛选 |
| 分页 | page/page_size 参数、上限 100 |
| 随机题目 | limit 参数、上限 100 |
| 提交答案 | 各题型判分（单选/多选/判断/填空/简答） |
| 统计 | answered/correct/accuracy/mistake_count |
| 错题 | 错题列表、错题计数 |
| 收藏 | 添加/取消收藏、幂等删除 |
| 重置进度 | 清除答题记录和错题 |

### 8.2 test_auth.py

**测试范围**：密码哈希、CSRF、限流、注册/登录/登出 API

**关键测试用例**：

| 用例 | 验证内容 |
|------|----------|
| `test_hash_password_format` | 哈希格式 `pbkdf2_sha256$300000$salt$hash` |
| `test_verify_password_correct` | 正确密码验证通过 |
| `test_verify_password_wrong` | 错误密码验证失败 |
| `test_hash_password_unique_salt` | 每次哈希使用不同盐 |
| `test_password_too_short` | 密码 < 6 位拒绝 |
| `test_student_id_format` | 学号格式校验 |
| `test_ensure_csrf_token` | CSRF token 生成且稳定 |
| `test_csrf_protection` | 登录后非 GET 请求需 CSRF token |
| `test_register_api` | 注册成功返回 csrf_token |
| `test_register_duplicate` | 重复学号返回 409 |
| `test_login_api` | 登录成功 |
| `test_login_wrong_password` | 错误密码返回 401 |
| `test_auth_me` | 获取当前用户 |
| `test_logout` | 登出后 session 清除 |
| `test_submit_records_user_id` | 登录用户提交记录 user_id |
| `test_stats_for_logged_in_user` | 登录用户获取自己的统计 |

### 8.3 test_banks.py

**测试范围**：题库 CRUD + 权限模型 + 订阅 + 举报

**关键测试用例**：见 [7. 权限回归矩阵](#7-权限回归矩阵)

### 8.4 test_csv_importer.py

**测试范围**：CSV 解析、模板生成、题目消毒

**关键测试用例**：

| 用例 | 验证内容 |
|------|----------|
| 表头校验 | 缺少必填列报错 |
| 字段校验 | 必填字段为空报错 |
| 题型校验 | 无效题型报错 |
| 章节号校验 | 非正整数报错 |
| 多选答案解析 | 逗号分隔 |
| 填空答案解析 | 管道符分隔 |
| 模板生成 | 包含 5 种题型示例 |
| BOM 处理 | UTF-8 BOM 头自动移除 |
| 空行跳过 | 空行不影响解析 |

### 8.5 test_sanitize.py

**测试范围**：`sanitize_question()` 消毒逻辑

**关键测试用例**：

| 用例 | 验证内容 |
|------|----------|
| `test_clean_question_not_flagged` | 正常题目不被标记 |
| `test_script_tag_detected` | `<script>` 被检测 |
| `test_javascript_url_detected` | `javascript:` 被检测 |
| `test_onerror_detected` | `onerror` 被检测 |
| `test_html_escaped_after_detection` | 检测后 HTML 转义 |
| 长度校验 | 题干超 2000 字符报错 |

### 8.6 test_admin_import.py

**测试范围**：管理员 CSV 导入完整流程

**关键测试用例**：

| 用例 | 验证内容 |
|------|----------|
| 文件上传导入 | multipart/form-data |
| JSON 内容导入 | application/json |
| 模板下载 | CSV 模板正确 |
| 解析错误处理 | 部分错误仍导入有效题目 |
| 去重 | 重复题目跳过 |
| 无 token 拒绝 | 401 |

### 8.7 test_migrations.py

**测试范围**：数据库迁移验证

**关键测试用例**：

| 用例 | 验证内容 |
|------|----------|
| schema 初始化 | 11 张表存在 |
| session_id 列迁移 | 旧表添加 session_id |
| UNIQUE 约束迁移 | mistakes/favorites 约束更新 |
| bank_id 架构迁移 | questions 表重建 |
| user_id/bank_id 列迁移 | 新列添加 |
| 迁移幂等性 | 重复执行不报错 |
| 数据完整性 | 迁移后数据量一致 |

### 8.8 test_regression.py

**测试范围**：关键 Bug 回归

**关键测试用例**：见 [2.3 Regression](#23-regression回归测试)

### 8.9 test_frontend.py

**测试范围**：前端页面测试

**关键测试用例**：

| 用例 | 验证内容 |
|------|----------|
| 主页面渲染 | HTML 包含关键元素 |
| Vue 挂载 | `{{ }}` 语法保留 |
| 静态资源 | JS/CSS/图标可访问 |
| manifest.json | PWA 配置正确 |

### 8.10 ui_smoke.py

**测试范围**：UI 冒烟测试

**关键测试用例**：

| 用例 | 验证内容 |
|------|----------|
| 页面可访问 | HTTP 200 |
| 基本元素存在 | 标题/容器存在 |

### 8.11 e2e/test_quiz_flow.py

**测试范围**：Playwright E2E 测试

**关键测试用例**：见 [2.5 E2E](#25-e2e端到端测试)

---

## 9. 测试编写规范

### 9.1 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 测试文件 | `test_<module>.py` | `test_auth.py`, `test_banks.py` |
| 测试类 | `Test<Feature>` 或 `<Feature>Test` | `TestQuizFlow`, `ScoringRegressionTest` |
| 测试函数 | `test_<scenario>` | `test_login_wrong_password` |
| 回归测试 | `test_<scenario>_<expected_behavior>` | `test_delete_favorite_is_idempotent` |

### 9.2 测试结构

**单元测试模板**（pytest 风格）：

```python
def test_<scenario>():
    """一句话描述测试目的"""
    # Arrange - 准备
    from module import function
    input_data = ...

    # Act - 执行
    result = function(input_data)

    # Assert - 断言
    assert result == expected
```

**API 测试模板**：

```python
def test_<scenario>():
    """描述"""
    import os
    os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
    from app import app, db
    client = app.test_client()

    # 准备数据
    qid = db.add_question({...})

    # 发送请求
    resp = client.get(f"/api/questions/{qid}")

    # 断言
    assert resp.status_code == 200
    data = resp.get_json()
    assert data['id'] == qid
```

**权限测试模板**：

```python
def test_<identity>_<operation>_<bank_type>():
    """<身份> 对 <题库类型> 的 <操作> 应返回 <状态码>"""
    from permissions import can_read_bank, Bank, User

    bank = Bank({'owner_id': 5, 'visibility': 'private', 'status': 'active'})
    user = User({'id': 3, 'role': 'student'})

    assert can_read_bank(user, bank) is False  # 非 owner 不可读私有题库
```

### 9.3 测试数据管理

| 规则 | 说明 |
|------|------|
| 使用临时数据库 | `tempfile.TemporaryDirectory()` + `QuizDatabase(tmpdir/test.db)` |
| 不依赖共享状态 | 每个测试独立准备数据 |
| 清理测试数据 | `conftest.py` 自动清理 `rate_limits` 和 `users` |
| 唯一标识 | 测试数据使用唯一 stem/student_id 避免冲突 |
| 恢复全局状态 | 替换 `app_module.db` 后在 `tearDown` 恢复 |

### 9.4 断言规范

| 规则 | 说明 |
|------|------|
| 状态码断言 | `assert resp.status_code == 200` |
| 响应体断言 | `assert data['field'] == expected` |
| 错误消息断言 | `assert "关键词" in data['error']` |
| 不断言实现细节 | 不断言 SQL 语句、内部变量名 |
| 使用 `subTest` | 多参数场景使用 `with self.subTest(param=value)` |

---

## 10. CI/CD 集成

### 10.1 CI 测试流程

```
代码提交
  │
  ├─ 1. 安装依赖
  │     pip install -r backend/requirements.txt
  │     pip install pytest pytest-cov
  │
  ├─ 2. 运行单元 + 集成 + 回归测试
  │     python -m pytest backend/tests/ -v --tb=short \
  │       --cov=backend --cov-report=term-missing \
  │       --cov-fail-under=60
  │
  ├─ 3. 检查覆盖率阈值
  │     └─ 低于 60% → CI 失败
  │
  ├─ 4. E2E 测试（可选，需 Playwright）
  │     playwright install chromium
  │     cd backend && python app.py &  # 启动服务器
  │     python -m pytest backend/tests/e2e/ -v
  │
  └─ 5. 全部通过 → 允许合并
```

### 10.2 质量门禁

| 门禁 | 条件 | 失败行为 |
|------|------|----------|
| 测试通过 | 0 失败 | 阻止合并 |
| 覆盖率 | ≥ 60% | 阻止合并 |
| 权限矩阵 | 全覆盖 | 警告（不阻止） |
| 回归测试 | 全通过 | 阻止合并 |
| E2E | 全通过（可选） | 警告（不阻止） |

### 10.3 本地开发流程

```bash
# 开发前：运行现有测试确保基线
python -m pytest backend/tests/ -v --tb=short

# 开发中：运行相关测试
python -m pytest backend/tests/test_api.py -v --tb=short -x

# 提交前：运行全量测试 + 覆盖率
python -m pytest backend/tests/ -v --tb=short --cov=backend --cov-report=term-missing --cov-fail-under=60

# Bug 修复后：添加回归测试
# 在 test_regression.py 中添加 test_<bug_description>
```

---

## 附录：测试命令速查

```bash
# 全量测试（不含 E2E）
python -m pytest backend/tests/ -v --tb=short

# 全量测试 + 覆盖率
python -m pytest backend/tests/ -v --tb=short --cov=backend --cov-report=term-missing --cov-fail-under=60

# E2E 测试（需先启动服务器）
python -m pytest backend/tests/e2e/ -v

# 指定文件
python -m pytest backend/tests/test_auth.py -v --tb=short

# 仅失败项
python -m pytest backend/tests/ --lf -v

# 停止在第一个失败
python -m pytest backend/tests/ -v --tb=short -x

# 显示打印
python -m pytest backend/tests/ -v --tb=short -s
```
