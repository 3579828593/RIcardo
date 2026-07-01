# SPEC: UGC Security Hardening

## 状态：已完成（commit 5c74ab6）
## 审查报告：UGC题库系统_最终代码审查报告.md

## 目标
修复 UGC 题库系统中的私有题库泄露和审核链路缺陷。

## 修复清单

### P0-1: /api/questions 权限校验（Critical → 已修复）
- 问题：/api/questions, /api/questions/random, /api/questions/<qid> 缺少题库权限校验
- 修复：新增 _check_bank_access() 统一权限检查函数，bank_id=None 或 1 时允许（官方题库），其他需要 can_read_bank
- 验收：非 owner 访问私有题库 → 403

### P0-2: /api/submit 权限校验（Critical → 已修复）
- 问题：提交答案时未检查题目所属题库权限
- 修复：从 JSON body 获取 bank_id（默认1），调用 _check_bank_access 校验
- 验收：非 owner 提交私有题库答案 → 403

### P0-3: flagged 持久化（Important → 已修复）
- 问题：sanitize_question 设置了 _flagged，但 batch_add_questions INSERT 未写入 flagged 列
- 修复：INSERT 语句添加 flagged 字段，值来自 q.get("_flagged")
- 验收：CSV 含 <script> → questions.flagged = 1

### P0-4: answer 字段 sanitize（Important → 已修复）
- 问题：sanitize_question 未处理 answer 字段
- 修复：raw_texts 包含 answer 字段，参与敏感词检测
- 验收：答案含 javascript: → flagged

### P0-5: subscribe status 检查（Important → 已修复）
- 问题：订阅接口只检查 visibility='public'，未检查 status
- 修复：增加 bank.status not in ('active',) 检查
- 验收：hidden/deleted 题库不可订阅

### P0-6: 登录限流逻辑（Important → 已修复）
- 问题：登录限流覆盖所有尝试，成功登录也计入
- 修复：check_rate_limit 在登录前检查，成功登录后通过
- 验收：10次成功登录不锁定

## 验收标准（全部通过）
- [x] 非 owner 无法读取私有题库题目
- [x] 非 owner 无法通过 qid 获取私有题目答案
- [x] /api/questions 默认 bank_id=1（官方题库）
- [x] flagged 可持久化到数据库
- [x] answer 字段参与 sanitize 检测
- [x] hidden/deleted 题库不可订阅
- [x] 登录成功不触发失败限流锁定
- [x] pytest 151 项全通过
