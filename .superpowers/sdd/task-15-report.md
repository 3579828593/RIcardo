# Task 15 报告：Step 3 — 公开题库订阅/退订

## 状态
DONE

## 提交 hash
`10e90824ff529c551b514d9faa16bbe9d898212f`（短 hash: `10e9082`）

提交信息：`feat: Step 3 — 公开题库订阅/退订 + 权限校验`

## 测试数量
- 新增测试：3 个（`test_subscribe_bank`、`test_unsubscribe_bank`、`test_cannot_subscribe_private_bank`）
- test_banks.py 文件测试：29 个（26 原有 + 3 新增）全部通过
- 完整回归测试：151 passed, 8 subtests passed（148 原有 + 3 新增），0 失败

## TDD 流程执行记录
1. **追加测试**：在 `backend/tests/test_banks.py` 末尾追加 3 个测试，代码与简报完全一致。
2. **验证失败**：运行 `pytest tests/test_banks.py::test_subscribe_bank -v`，结果 `assert 404 == 200`，订阅路由不存在，符合预期失败。
3. **实现 database.py**：在 `QuizDatabase` 类的 `handle_report` 方法之后、`backup` 方法之前，新增 `subscribe_bank` 和 `unsubscribe_bank` 两个方法，代码与简报完全一致。
4. **实现 app.py**：在举报路由（`api_admin_handle_report`）之后、`@app.errorhandler(404)` 之前，新增 `POST/DELETE /api/banks/<int:bank_id>/subscribe` 路由，代码与简报完全一致。
5. **验证通过**：运行 `pytest tests/test_banks.py -v`，29 个测试全部通过。
6. **完整回归**：运行 `pytest tests/ -v --ignore=tests/e2e --tb=short`，151 passed, 8 subtests passed。
7. **提交**：`git add` 三个文件并提交。

## 修改文件
1. `backend/database.py` — 新增 `subscribe_bank`、`unsubscribe_bank` 方法（+22 行）
2. `backend/app.py` — 新增 `api_bank_subscribe` 路由（+24 行）
3. `backend/tests/test_banks.py` — 追加 3 个测试（+90 行）

## 顾虑或偏差
无。所有代码与简报完全一致，未重新定义或重新导入任何简报标注"DO NOT re-import or re-define"的函数。`bank_subscriptions` 表（Task 10 创建）和 `list_banks` 的 `scope=subscribed`（Task 10 实现）以及 `GET /api/banks?scope=subscribed`（Task 11 实现）均按预期复用，无需改动。
