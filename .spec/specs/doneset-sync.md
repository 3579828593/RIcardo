# SPEC: doneSet 服务端同步

## 目标
从 /api/stats 获取已答题 ID 列表，在前端初始化时恢复 doneSet，解决换设备/清缓存后进度丢失问题。

## 背景
当前 doneSet 纯客户端 localStorage 存储。用户换设备或清除浏览器数据后，已做题进度归零，但服务端 answer_records 表中仍有记录。需要从服务端恢复 doneSet。

## 接口设计

### 现有 API: GET /api/stats
当前返回：
```json
{
  "answered_questions": 5,
  "correct_answers": 3,
  "accuracy": 60.0,
  "type_distribution": {...},
  "course_distribution": {...},
  "total_questions": 351,
  "mistake_count": 2
}
```

### 新增字段: answered_question_ids
在 /api/stats 响应中增加 `answered_question_ids` 数组：
```json
{
  "answered_questions": 5,
  "answered_question_ids": [1, 3, 7, 12, 15],
  ...
}
```

后端实现：database.py 的 `get_stats(session_id)` 方法中查询 `SELECT question_id FROM answer_records WHERE session_id = ?`，返回 ID 列表。

## 前端逻辑

### 初始化流程（app.js onMounted）
```
1. 从 localStorage 读取 doneSet（本地缓存）
2. 调用 /api/stats 获取 answered_question_ids
3. 合并：doneSet = new Set([...localDoneSet, ...serverIds])
4. 如果合并后有新题，更新 localStorage
```

### 合并策略
- 取并集（本地 + 服务端），不丢失任何一端的记录
- 服务端为权威源：如果服务端有但本地没有，补入本地
- 本地为补充源：如果本地有但服务端没有（离线答题未同步），保留本地

## 边界条件
- 空值：answered_question_ids 为空数组时，doneSet 保持本地值
- 大量数据：351 题最多 351 个 ID，JSON 数组约 2KB，不影响性能
- 并发：不涉及并发写入，doneSet 只在前端内存中操作
- 首次使用：localStorage 无 doneSet + 服务端无记录 → doneSet 为空 Set（正常）

## 验收标准
- [ ] /api/stats 返回 answered_question_ids 字段
- [ ] 前端 onMounted 时从服务端恢复 doneSet
- [ ] 换设备后 doneSet 不丢失（模拟：清除 localStorage → 刷新 → doneSet 从服务端恢复）
- [ ] 本地+服务端合并正确（并集）
- [ ] 35/35 回归测试通过
- [ ] 新增测试覆盖 doneSet 恢复逻辑

## 涉及文件
- backend/database.py — get_stats() 增加 answered_question_ids
- backend/app.py — 无需改动（已调用 get_stats）
- backend/static/js/app.js — onMounted 增加 doneSet 恢复逻辑
- backend/tests/test_api.py — 新增 answered_question_ids 测试
