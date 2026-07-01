# REVIEW: UGC Security Hardening

## 状态：通过
## 审查日期：2026-07-02
## 审查基准：commit 5c74ab6 + 1a6442e

## 权限校验
- [x] anonymous + private bank_id → 403
- [x] non-owner + private bank_id → 403
- [x] owner + private bank_id → 200
- [x] admin + private bank_id → 200
- [x] public + active → 200
- [x] hidden/deleted → admin only
- [x] /api/questions 无 bank_id → 默认官方题库
- [x] /api/questions/random 带 bank_id → 权限校验
- [x] /api/submit 带 bank_id → 权限校验
- [x] /api/banks/<id>/questions → can_read_bank 校验
- [x] /api/banks/<id>/progress → can_read_bank 校验

## 数据安全
- [x] flagged 写入 questions 表
- [x] answer 参与 sanitize_question 检测
- [x] answer 中的危险字符被标记
- [x] sanitize 顺序：先检测后转义

## 订阅安全
- [x] public + active 可订阅
- [x] public + hidden 不可订阅
- [x] public + deleted 不可订阅
- [x] private 不可订阅

## 限流
- [x] 登录失败 10 次/10分钟 → 锁定
- [x] 登录成功不增加失败计数
- [x] 注册 5 次/小时
- [x] 导入 10 次/天
- [x] 举报 5 次/小时

## 测试
- [x] test_banks.py 权限测试通过
- [x] test_auth.py 认证测试通过
- [x] test_sanitize.py 净化测试通过
- [x] test_admin_import.py 导入测试通过
- [x] test_regression.py 回归测试通过
- [x] 全量 pytest 151 项通过

## 遗留项（Minor，可选修复）
- [ ] /api/auth/logout 豁免 CSRF（低风险）
- [ ] 迁移后 options_json/answer_json 丢失 NOT NULL 约束
- [ ] 错误响应格式不完全统一
- [ ] 限流清理每次检查时执行 DELETE（小规模无影响）
