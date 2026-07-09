# SPEC: 身份模型统一 (Identity Unification)

> 状态: DRAFT
> 优先级: P0 (最高影响力架构债)
> 创建: 2026-07-09
> 关联: ARCHITECTURE.md §8.1, agentic-sdd-workflow-v2.md R-6

---

## 1. 问题陈述

### 1.1 现状

系统维护两套并行的身份标识：

- **session_id**: 匿名用户标识，前端在 localStorage 生成 UUID，通过 `X-Session-Id` 请求头传递
- **user_id**: 登录用户标识，存储在 Flask session 中

这导致 `database.py` 中 **8 个方法** 存在 `if user_id / else session_id` 双分支：

| 方法 | 分支数 | 影响范围 |
|------|--------|----------|
| `record_answer()` | 2 | 答题记录 + 错题本写入 |
| `get_stats()` | 4 | 统计面板（bank_id × identity 组合） |
| `get_mistakes()` | 2 | 错题列表 |
| `get_favorites()` | 2 | 收藏列表 |
| `toggle_favorite()` | 2 | 收藏切换 |
| `remove_favorite()` | 2 | 取消收藏 |
| `reset_progress()` | 2 | 重置进度 |
| `migrate_session_data()` | 复杂 | 登录时数据迁移 |

### 1.2 核心痛点

1. **代码膨胀**: `get_stats()` 因 2×2 组合产生 4 个分支，70+ 行重复查询
2. **迁移复杂**: `migrate_session_data()` 需处理去重 + 清理，逻辑难以验证
3. **安全债务**: 匿名用户 POST 请求不受 CSRF 保护
4. **维护成本**: 每新增一个用户数据查询，都需要写两套逻辑

### 1.3 非目标

- 不改变前端 session_id 生成逻辑（向后兼容）
- 不引入 JWT 或外部认证服务
- 不改变 Flask session 作为登录态载体的方式

---

## 2. 设计方案

### 2.1 核心思路

**统一为 user_id 模型**: 匿名用户首次访问时自动创建 `users` 表记录（`role='anonymous'`），`session_id` 映射为 `user.id`。

```
Before:                          After:
┌─────────────┐                 ┌─────────────────────┐
│  session_id │ ──→ queries ──→ │  user_id (统一)     │
│  (X-Header) │                 │  ┌───────────────┐  │
├─────────────┤                 │  │ anonymous     │  │
│  user_id    │ ──→ queries ──→ │  │ (auto-created)│  │
│  (Session)  │                 │  └───────────────┘  │
└─────────────┘                 │  ┌───────────────┐  │
  双分支查询                     │  │ student/admin │  │
                                │  │ (registered)  │  │
                                │  └───────────────┘  │
                                └─────────────────────┘
                                 统一查询：WHERE user_id = ?
```

### 2.2 数据模型变更

#### 2.2.1 users 表扩展

```sql
-- 修改 role CHECK 约束，增加 'anonymous'
-- 新增 session_uuid 列，存储匿名用户的 session_id
ALTER TABLE users ADD COLUMN session_uuid TEXT;
-- 更新约束（需要重建表，在迁移脚本中处理）
-- role CHECK IN ('student', 'admin', 'anonymous')
```

#### 2.2.2 session_user_map 表（过渡期）

```sql
CREATE TABLE IF NOT EXISTS session_user_map (
    session_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);
CREATE INDEX IF NOT EXISTS idx_sum_user ON session_user_map(user_id);
```

### 2.3 身份解析流程

```python
def _resolve_user_id(session_id: str, logged_in_user: dict = None) -> int:
    """统一身份解析：返回 user_id

    1. 已登录 → 返回 logged_in_user['id']
    2. 匿名 → 查 session_user_map
       2a. 已有映射 → 返回映射的 user_id
       2b. 无映射 → 创建 anonymous user + 映射 → 返回新 user_id
    """
    if logged_in_user:
        return logged_in_user['id']

    # 查映射
    user_id = db.get_user_id_by_session(session_id)
    if user_id:
        return user_id

    # 创建匿名用户
    user_id = db.create_anonymous_user(session_id)
    return user_id
```

### 2.4 数据查询统一

**Before** (8 个方法的双分支):
```python
def get_mistakes(self, page=1, page_size=20, session_id='anon', user_id=None):
    if user_id:
        rows = conn.execute("... WHERE m.user_id = ?", (user_id,))
    else:
        rows = conn.execute("... WHERE m.session_id = ?", (session_id,))
```

**After** (统一为 user_id):
```python
def get_mistakes(self, page=1, page_size=20, user_id: int = None):
    if user_id is None:
        user_id = _resolve_user_id(session_id)
    rows = conn.execute("... WHERE m.user_id = ?", (user_id,))
```

### 2.5 登录时数据合并

```python
def merge_anonymous_to_user(self, anon_user_id: int, real_user_id: int):
    """登录时将匿名数据合并到正式用户

    1. answer_records: UPDATE user_id = real WHERE user_id = anon
    2. mistakes: UPSERT (同题取最大 wrong_count)
    3. favorites: INSERT OR IGNORE (去重)
    4. 删除匿名 user 记录
    5. 更新 session_user_map 指向 real_user_id
    """
```

---

## 3. 迁移策略

### 3.1 迁移步骤（幂等，可重复执行）

```
Step 1: 扩展 users 表
  - ALTER TABLE users ADD COLUMN session_uuid TEXT
  - 重建 users 表以更新 role CHECK 约束

Step 2: 创建 session_user_map 表

Step 3: 数据迁移（向后兼容）
  - 遍历 answer_records 中 session_id != 'legacy' AND user_id IS NULL 的记录
  - 为每个唯一 session_id 创建 anonymous user + 映射
  - UPDATE answer_records SET user_id = mapped_uid WHERE session_id = ? AND user_id IS NULL
  - 同样处理 mistakes 和 favorites

Step 4: 验证
  - 确认所有 answer_records/mistakes/favorites 都有 user_id
  - 确认 session_user_map 条目数 = 匿名 user 数
```

### 3.2 过渡期策略

- **Phase 1**（本次）: 新增 `_resolve_user_id()`，所有查询方法增加 `user_id` 参数
- **Phase 2**（下次）: 修改路由层调用 `_resolve_user_id()`，消除 session_id 传递
- **Phase 3**（最终）: 删除 session_id 参数和旧查询分支

### 3.3 回滚方案

- 迁移脚本不删除 session_id 列，仅添加 user_id 列和映射表
- 如果出现问题，路由层可回退到使用 session_id 查询
- 新增 feature flag `IDENTITY_UNIFIED = True/False` 控制行为

---

## 4. API 变更

### 4.1 对前端的影响

**无变更**。前端继续发送 `X-Session-Id` 请求头。后端在 `_resolve_user_id()` 中自动处理映射。

### 4.2 对后端的影响

| 模块 | 变更 |
|------|------|
| `app.py` | `_get_session_id()` 不变；新增 `_resolve_user_id()`；路由中调用 resolve |
| `database.py` | 8 个方法签名统一为 `user_id` 参数；新增 `create_anonymous_user()`、`get_user_id_by_session()`、`merge_anonymous_to_user()` |
| `auth.py` | 无变更 |

---

## 5. 测试计划

### 5.1 新增测试

```
test_identity.py:
  - test_anonymous_user_auto_created: 首次请求创建匿名用户
  - test_anonymous_user_reused: 同一 session_id 复用匿名用户
  - test_anonymous_answer_recorded: 匿名答题记录写入 user_id
  - test_anonymous_mistakes: 匿名错题本按 user_id 查询
  - test_anonymous_favorites: 匿名收藏按 user_id 查询
  - test_login_merges_data: 登录后匿名数据合并到正式用户
  - test_login_no_duplicate: 合并后无重复记录
  - test_stats_unified: 统计查询不再有分支
  - test_reset_progress_unified: 重置进度按 user_id
  - test_session_map_persistence: 映射关系持久化
```

### 5.2 回归测试

- 所有现有 152 项测试必须通过
- `test_banks.py` 中的权限测试不受影响（权限模型不变）
- `test_auth.py` 中的登录测试需验证数据合并

### 5.3 验收标准

```
- [ ] users 表支持 role='anonymous'
- [ ] session_user_map 表已创建
- [ ] _resolve_user_id() 函数已实现
- [ ] 8 个方法不再有 if user_id / else session_id 分支
- [ ] 新增 10 项测试全部通过
- [ ] 现有 152 项测试全部通过
- [ ] 质量门禁 6/6 通过
- [ ] 数据迁移脚本幂等可重复执行
```

---

## 6. 风险与缓解

| 风险 | 等级 | 缓解 |
|------|------|------|
| 匿名用户数据膨胀 | 中 | 定期清理 30 天未活跃的匿名用户 |
| 迁移脚本执行慢 | 低 | 分批迁移，每批 1000 条 |
| 前端兼容性 | 低 | 前端无变更，完全后端透明 |
| 并发创建匿名用户 | 低 | session_user_map PK 防重复 + INSERT OR IGNORE |
