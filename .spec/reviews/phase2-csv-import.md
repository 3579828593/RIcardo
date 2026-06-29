# REVIEW: 阶段2 — CSV 题目导入 + 管理界面

> 审查日期: 2026-06-29
> SPEC: .spec/specs/phase2-csv-import.md
> 状态: 通过

## 自检清单

### 功能完整性
- [x] CSV 模板下载 → 4 种题型示例
- [x] CSV 文件上传导入 → 支持 multipart/form-data
- [x] JSON body 导入 → 支持 { content: "csv文本" }
- [x] 格式校验 → 必填字段、题型、章节号、答案非空
- [x] 错误报告 → 行号 + 原因，部分错误仍导入有效行
- [x] 重复跳过 → UNIQUE(course, stem) + INSERT OR IGNORE
- [x] 题目列表 → 分页 + 课程/题型/关键词筛选
- [x] 题目删除 → 带确认对话框
- [x] Admin Token 认证 → 401 无效 token
- [x] 前端管理 Tab → Token 输入 + 导入区 + 管理区

### 代码质量
- [x] CSV 解析器独立模块 (csv_importer.py) — 纯函数，无副作用
- [x] 数据库层 batch_add_questions 利用 INSERT OR IGNORE 去重
- [x] API 接口复用现有 _positive_int_arg 和 search_questions
- [x] 前端 adminFetch 封装，自动带 X-Admin-Token header
- [x] Token 存储在 localStorage，切 Tab 自动验证
- [x] BOM 头处理 (utf-8-sig 解码 + 手动去除 \ufeff)
- [x] 字段名大小写不敏感 (normalized dict 全小写)

### 边界条件
- [x] 空 CSV → 400
- [x] 仅表头 CSV → 400 "没有可导入的题目"
- [x] 全部行有错误 → 400 + 错误详情
- [x] 部分行有错误 → 201 + 导入有效行 + parse_errors
- [x] 重复导入 → 201, added=0, skipped=N
- [x] 空行跳过
- [x] 章节号非正整数 → 错误
- [x] 无效题型 → 错误
- [x] 答案为空 → 错误
- [x] 多选答案逗号分隔解析
- [x] 填空题管道符分隔多空

### 测试覆盖
- [x] 20 项 CSV 解析器单元测试
- [x] 20 项管理 API 接口测试
- [x] 17 项回归测试（全部通过）
- [x] 总计 57 项测试全部通过
- [x] 测试使用唯一 UID 避免跨运行冲突

### 安全性
- [x] 所有管理接口需要 X-Admin-Token
- [x] 错误 token 返回 401
- [x] 无 token 返回 401
- [x] Token 比较使用 compare_digest（防时序攻击）

### Service Worker
- [x] 版本号 v6 → v7
- [x] 前端代码变更触发缓存更新

### 遗留问题
- [ ] 题目编辑 UI 未实现（本期仅删除，SPEC 已标注 YAGNI）
- [ ] Excel (.xlsx) 格式未支持（CSV 足够，SPEC 已标注 YAGNI）
- [ ] E2E 管理流程测试未编写（需要线上环境验证）
- [ ] 导入预览未实现（直接导入，有错误返回详情）

## 文件变更清单

| 文件 | 操作 | 行数 |
|------|------|------|
| backend/csv_importer.py | 新增 | 110 |
| backend/database.py | 修改 | +28 |
| backend/app.py | 修改 | +55 |
| backend/static/js/app.js | 修改 | +120 |
| backend/templates/index.html | 修改 | +110 |
| backend/static/sw.js | 修改 | v6→v7 |
| backend/tests/test_csv_importer.py | 新增 | 202 |
| backend/tests/test_admin_import.py | 新增 | 286 |
| .spec/specs/phase2-csv-import.md | 新增 | SPEC |
| .spec/reviews/phase2-csv-import.md | 新增 | 本文件 |

## 结论

阶段2 核心功能（CSV 导入 + 管理界面）实现完成，所有测试通过，可以提交部署。
