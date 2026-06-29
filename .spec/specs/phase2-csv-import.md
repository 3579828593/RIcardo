# SPEC: 阶段2 — CSV 题目导入 + 管理界面

> 创建日期: 2026-06-29
> 状态: 实现中
> 路线图阶段: 阶段2 自己能加题（暑假第3-4周）

## 1. 目标

不用改代码就能批量加题。Excel/CSV 模板 → 上传 → 题库更新，附管理后台基础版。

## 2. 现有基础（无需重复实现）

- `require_admin` 装饰器：`X-Admin-Token` header 验证 ✅
- `POST /api/admin/questions`：单题创建 ✅
- `PUT/DELETE /api/admin/questions/<qid>`：单题编辑/删除 ✅
- `POST /api/admin/dedupe`：去重 ✅
- `POST /api/admin/backup`：备份 ✅
- `database.py` 的 `add_question()`, `update_question()`, `delete_question()` ✅

## 3. 新增功能

### 3.1 后端

#### 3.1.1 CSV 解析器 (`csv_importer.py`)

独立模块，纯函数，易于测试。

```
输入: CSV 文本字符串
输出: { questions: [...], errors: [{row, error}, ...] }
```

CSV 格式：
| 列名 | 必填 | 说明 |
|------|------|------|
| course | 是 | 课程标识 (weather/english/自定义) |
| chapter | 是 | 章节号 (正整数) |
| type | 是 | 题型: single/multiple/true_false/fill_blank/short_answer |
| stem | 是 | 题干文本 |
| option_A | 否 | 选项A |
| option_B | 否 | 选项B |
| option_C | 否 | 选项C |
| option_D | 否 | 选项D |
| answer | 是 | 正确答案 (多选用逗号分隔如"A,C"，填空多空用\|分隔) |
| explanation | 否 | 解析 |
| knowledge | 否 | 知识点 |

校验规则：
- 必填字段缺失 → 记录错误行号和原因
- 题型不在有效列表 → 记录错误
- chapter 非正整数 → 记录错误
- answer 为空 → 记录错误
- 有错误时仍解析正确行，返回两部分

#### 3.1.2 批量导入接口

`POST /api/admin/import/csv`
- 认证: `X-Admin-Token` header
- 接受: multipart/form-data (file 字段) 或 JSON (content 字段)
- 返回:
  - 成功: `{ added: N, skipped: M, total: T }` (201)
  - 解析错误: `{ error: "CSV 解析有错误", parse_errors: [...], parsed_count: N }` (400)
  - 空内容: `{ error: "CSV 内容为空" }` (400)

#### 3.1.3 题目列表接口

`GET /api/admin/questions?page=1&page_size=20&course=&chapter=&type=&keyword=`
- 复用 `db.search_questions()`
- 返回与 `/api/questions` 相同格式

#### 3.1.4 模板下载接口

`GET /api/admin/template`
- 返回 CSV 模板文件 (Content-Disposition: attachment)
- 包含表头 + 4 种题型示例行

#### 3.1.5 数据库层

`database.py` 新增 `batch_add_questions(questions: list) -> dict`:
- 利用 `INSERT OR IGNORE` + `UNIQUE(course, stem)` 自动去重
- 返回 `{ added: int, skipped: int }`

### 3.2 前端

#### 3.2.1 管理 Tab

底部导航新增第 5 个 Tab "管理"（齿轮图标）。

未认证状态：
- 显示 Admin Token 输入框
- 输入 token 后存入 localStorage (`quiz_admin_token`)
- 验证方式：调用 `GET /api/admin/questions`，成功则标记 `isAdmin = true`

认证后显示两个区域：

#### 3.2.2 CSV 导入区

- "下载模板" 按钮 → 调用 `GET /api/admin/template` 下载 CSV
- 文件选择/拖拽上传区域
- 导入结果展示：
  - 成功: "成功导入 N 题，跳过 M 题（重复）"
  - 部分错误: 错误行号 + 原因列表
  - 全部错误: 错误详情

#### 3.2.3 题目管理区

- 表格展示：ID、题型、课程、章节、题干（截断）、操作
- 分页器
- 筛选：课程、题型、关键词
- 操作：删除（带确认）
- 编辑（后续迭代，本期仅删除）

### 3.3 Service Worker

- 版本号 v6 → v7（前端代码变更）

## 4. 测试计划

### 单元测试
- `test_csv_importer.py`: 
  - 正常解析 4 种题型
  - 缺失必填字段
  - 无效题型
  - 多选答案逗号分隔
  - 填空多空管道分隔
  - 空内容
  - BOM 头处理
- `test_admin_import.py`:
  - 无 token → 401
  - 错误 token → 401
  - 正常导入 → 201
  - 重复题导入 → skipped 计数
  - 解析错误 → 400 + 错误详情
  - 模板下载 → 200 + CSV 内容

### E2E 测试
- `test_admin_flow.py`:
  - 管理页 Tab 显示
  - Token 输入 + 验证
  - CSV 上传 + 结果展示

## 5. 验收标准

- [ ] 下载 CSV 模板 → 填写 → 上传 → 题库新增成功
- [ ] 格式错误时返回具体错误行号和原因
- [ ] 管理后台需要 admin token 才能操作
- [ ] 支持单选/多选/判断/填空四种题型导入
- [ ] 重复题目自动跳过（基于 course+stem 唯一约束）
- [ ] 所有测试通过（回归 + 新增）

## 6. 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `backend/csv_importer.py` | 新增 | CSV 解析器 |
| `backend/database.py` | 修改 | 添加 batch_add_questions |
| `backend/app.py` | 修改 | 添加导入/列表/模板接口 |
| `backend/static/js/app.js` | 修改 | 管理状态和方法 |
| `backend/templates/index.html` | 修改 | 管理 Tab UI |
| `backend/static/sw.js` | 修改 | v6 → v7 |
| `backend/tests/test_csv_importer.py` | 新增 | CSV 解析测试 |
| `backend/tests/test_admin_import.py` | 新增 | 导入接口测试 |

## 7. 不做（YAGNI）

- Excel (.xlsx) 格式支持（CSV 足够，Excel 可另存为 CSV）
- Markdown 导入（后续迭代）
- CI/CD 自动部署（后续迭代）
- 题目编辑 UI（本期仅删除，编辑用 API）
- 批量删除
- 导入预览（直接导入，有错误返回）
