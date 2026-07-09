# Task 13 Report: Step 2 — CSV 导入到题库路由

## 状态
**DONE**

## 提交 hash
`a4f81563e4be0ef91ff34799757e78a0f2f198ba` (短 hash: `a4f8156`)

提交信息：`feat: Step 2 — CSV 导入到指定题库 + sanitize + 限流`

## 测试数量
- 新增测试：2 个
  - `test_api_import_csv_to_bank` — POST /api/banks/<id>/import CSV 导入到指定题库
  - `test_api_import_to_other_user_bank` — 不能导入到别人的题库（权限校验 403）
- test_banks.py 测试数：22 个（20 原有 + 2 新增），全部通过
- 完整回归测试：144 passed, 8 subtests passed（142 原有 + 2 新增），无回归

## TDD 流程执行记录
1. **Step 1 — 写失败测试**：在 `backend/tests/test_banks.py` 顶部添加 `import io`，末尾追加 2 个测试
2. **Step 2 — 验证失败**：运行 `test_api_import_csv_to_bank`，预期失败（404 路由不存在），实际 `assert 404 == 201` 失败 ✓
3. **Step 3 — 实现路由**：
   - 更新 `backend/app.py` 第 23 行 import：`from csv_importer import parse_csv, generate_template, sanitize_question`
   - 在 `api_bank_progress` 之后、`@app.errorhandler(404)` 之前插入 `api_bank_import` 路由
4. **Step 4 — 验证通过**：`tests/test_banks.py` 22 passed ✓
5. **Step 5 — 完整回归**：`144 passed, 8 subtests passed` ✓
6. **Step 6 — 提交**：仅提交 `backend/app.py` 和 `backend/tests/test_banks.py`（未提交测试运行产生的 quiz.db 变更）

## 修改的文件
- `backend/app.py`
  - 第 23 行：import 新增 `sanitize_question`
  - 第 707-790 行：新增 `POST /api/banks/<int:bank_id>/import` 路由 `api_bank_import`
- `backend/tests/test_banks.py`
  - 第 5 行：新增 `import io`
  - 末尾追加 2 个测试函数

## 路由功能说明
新增的 `POST /api/banks/<int:bank_id>/import` 路由实现：
1. 登录校验（401）
2. 题库存在性校验（404）
3. 导入权限校验 `can_import_to_bank`（403）
4. 限流：每用户每天最多 `MAX_IMPORT_PER_DAY`(10) 次（429）
5. 读取 CSV（支持 multipart 文件上传 或 JSON body）
6. `parse_csv` 解析 + 单次导入上限 `MAX_QUESTIONS_PER_IMPORT`(500) 校验（400）
7. 逐题 `sanitize_question` 清洗：错误题跳过记录、flagged 统计、过滤后全空则 400
8. `db.batch_add_questions` 写入 + `db.update_bank_question_count` 更新计数（201）
9. 数据库异常返回 500

## 顾虑或偏差
无。所有代码与简报完全一致，未做任何偏差修改。测试运行产生的 `backend/data/quiz.db` 变更未提交（仅提交简报指定的 2 个文件）。
