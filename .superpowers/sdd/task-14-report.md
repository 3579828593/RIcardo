# Task 14 报告：Step 3 — reports 表 + 举报路由 + 管理员审核面板

## 状态
**DONE**

## 提交 hash
- 短 hash: `657af50`
- 完整 hash: `657af50a96004636942db95c7af13f837fda7d9b`
- 提交信息: `feat: Step 3 — reports 表 + 举报路由 + 管理员审核面板`
- 变更: 3 files changed, 177 insertions(+)

## 测试摘要
- 新增测试: 4 个（test_report_question / test_report_question_logged_in / test_admin_list_reports / test_admin_handle_report）
- test_banks.py 测试数: 26 个（22 旧 + 4 新），全部通过
- 完整回归测试: 148 passed, 8 subtests passed（144 旧 + 4 新），0 失败
- 运行命令: `python -m pytest tests/ -v --ignore=tests/e2e --tb=short`

## 实现摘要

### 1. backend/database.py
- 在 `_init_db()` 的 `executescript` 中，于 `rate_limits` 表之后、闭合 `""")` 之前，新增 `reports` 表 SQL（含 `idx_reports_user_question` 唯一索引和 `idx_reports_status` 索引）。
- 在 `QuizDatabase` 类中，于 `count_user_banks` 方法之后、`backup` 方法之前，新增 3 个举报 CRUD 方法：
  - `create_report(question_id, reason, detail, reporter_id, session_id)` — 创建举报，已登录用户重复举报返回 None
  - `list_reports(status)` — 列出举报（可按 status 过滤）
  - `handle_report(report_id, status, admin_note, handler_id)` — 处理举报

### 2. backend/app.py
在 `api_bank_import` 路由之后、`@app.errorhandler(404)` 之前，新增 3 个举报路由：
- `POST /api/questions/<int:qid>/report` — 举报题目（登录或匿名，含 IP/用户限流 5 次/60 分钟，重复举报返回 409）
- `GET /api/admin/reports` — 管理员查看举报列表（`@require_admin` 保护，支持 `?status=` 过滤）
- `PUT /api/admin/reports/<int:report_id>` — 管理员处理举报（`@require_admin` 保护，status 仅接受 resolved/dismissed）

### 3. backend/tests/test_banks.py
在文件末尾追加 4 个测试，内容与简报完全一致。

## TDD 流程执行记录
1. 追加 4 个测试到 test_banks.py 末尾
2. 运行 `test_report_question` 验证失败：`assert 404 == 201`（路由不存在，符合预期）
3. 在 database.py 加 reports 表 + 3 个 CRUD 方法
4. 在 app.py 加 3 个举报路由
5. 运行 test_banks.py：26 passed（4 个新测试全部通过）
6. 运行完整回归：148 passed, 8 subtests passed
7. git 提交成功

## 顾虑或偏差
无顾虑，无偏差。所有代码与简报完全一致，未重新定义任何简报标注"DO NOT re-import or re-define"的函数/装饰器（`require_admin`、`_get_session_id`、`_get_current_user`、`check_rate_limit`、`get_question` 等均直接复用）。

唯一提示：git 提交时出现 LF→CRLF 换行符警告（Windows 环境正常行为），不影响功能。
