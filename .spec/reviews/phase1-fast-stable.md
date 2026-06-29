# REVIEW: 阶段1 快而稳

## AI 自检清单
- [x] 边界条件: 离线时 navigator.onLine === false 正确判断
- [x] 边界条件: 离线队列空时 getOfflineQueue 返回 []，syncOfflineQueue 直接 return
- [x] 边界条件: checkAnswerLocally 处理数组（多选）和字符串（单选/判断/填空）
- [x] SW 版本: v5 → v6（前端变更已升级）
- [x] 数据隔离: 离线队列存 localStorage，按 session 隔离（同 session_id）
- [x] 测试覆盖: 37 回归 + 8 E2E = 45 全部通过
- [x] 进度计算: 离线答题也加入 doneSet，进度条正常更新
- [x] 数组拷贝: checkAnswerLocally 中用 [...ans].sort() 和 [...correctAns].sort()
- [x] clearProgress: 清空 OFFLINE_QUEUE_KEY
- [x] onMounted: 页面加载时如果在线自动同步离线队列
- [x] online 事件: window.addEventListener('online', syncOfflineQueue)

## 测试结果
- [x] 37/37 回归测试通过
- [x] 8/8 E2E 测试通过（含离线模式测试）

## 线上验证
- [ ] 部署后验证 SW v6
- [ ] 验证离线答题功能
- [ ] Lighthouse 评分

## 风险评估
- **低风险**: 离线模式是纯前端逻辑，不影响服务端 API
- **低风险**: SW 版本升级自动清理旧缓存
- **注意**: 离线判对错可能与服务端有细微差异（如判断题别名），但基础对错准确
