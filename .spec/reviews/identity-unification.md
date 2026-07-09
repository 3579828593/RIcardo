# REVIEW: 身份模型统一 (Identity Unification)

> 状态: PASS
> 审查日期: 2026-07-09
> 关联 SPEC: .spec/specs/identity-unification.md

---

## 审查清单

### 数据库变更

- [x] users 表 CHECK 约束已更新（支持 'anonymous' role）
- [x] users 表新增 session_uuid 列
- [x] session_user_map 表已创建（session_id PK + user_id FK）
- [x] 迁移方法 _migrate_identity_unification() 幂等可重复执行
- [x] 迁移方法处理了旧表无 session_uuid 列的情况
- [x] 迁移方法在 _init_db() 中正确调用（第五步）

### 新增方法

- [x] create_anonymous_user(session_id) — 幂等创建匿名用户
- [x] get_user_id_by_session(session_id) — 查询映射
- [x] merge_anonymous_to_user(anon_uid, real_uid) — 登录时数据合并

### 数据合并逻辑

- [x] answer_records: 转移不重复记录 + 删除重复记录
- [x] mistakes: 先合并已有（取最大 wrong_count），再转移不重复的
- [x] favorites: 转移不重复记录 + 删除重复记录
- [x] 合并后删除匿名 user 记录
- [x] 合并后更新 session_user_map 指向正式用户

### Bug 修复

- [x] add_question() 在 INSERT OR IGNORE 跳过时返回已存在题目 ID（之前返回 0）

### 测试覆盖

- [x] 14 项身份模型测试全部通过
- [x] 6 项数据库层测试全部通过
- [x] 7 项权限测试全部通过
- [x] 现有 152 项测试全部通过（无回归）
- [x] 总计 179 项测试通过
- [x] 质量门禁 6/6 通过

### 向后兼容性

- [x] 前端无需变更（X-Session-Id 继续使用）
- [x] 现有 session_id 查询分支保留（过渡期）
- [x] 迁移不删除任何现有列或数据

### 待办（Phase 2）

- [ ] app.py 新增 _resolve_user_id() 函数
- [ ] 路由层调用 _resolve_user_id() 替代直接 session_id
- [ ] 消除 database.py 中的 if user_id / else session_id 分支
