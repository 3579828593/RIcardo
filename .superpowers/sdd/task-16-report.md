# Task 16 实现报告 — 前端登录注册 UI + 题库选择

## 状态：DONE

## 提交信息
- 提交 hash（完整）：`34876078a900ba65f528a90fc22ddcf98d3b7b71`
- 提交 hash（短）：`3487607`
- 提交信息：`feat: 前端 — 登录注册 UI + 题库选择 + 进度同步`
- 变更统计：3 files changed, 245 insertions(+), 2 deletions(-)

## 回归测试结果
- 命令：`cd d:\期末冲刺刷题系统\backend && python -m pytest tests/ -v --ignore=tests/e2e --tb=short`
- 结果：**151 passed, 8 subtests passed in 29.14s**
- 结论：前端修改未影响任何后端 API 测试，无回归。

## 修改的文件与行数

### 1. `backend/static/js/app.js`（+157 行）
- **新增认证状态**（setup() 内）：`currentUser`、`csrfToken`、`showLoginModal`、`loginMode`、`loginForm`、`loginError`
- **新增题库状态**：`currentBankId`、`myBanks`、`officialBanks`、`subscribedBanks`、`showBankSelector`
- **新增 `authFetch`**：在 apiFetch 基础上为非 GET 请求附加 `X-CSRF-Token`，并处理 401 自动登出
- **新增认证方法**：`checkAuth`、`submitLogin`、`logout`
- **新增题库方法**：`loadMyBanks`、`loadOfficialBanks`、`loadSubscribedBanks`、`selectBank`、`createBank`
- **更新 `loadAllForSingleMode`**：URL 参数追加 `bank_id`
- **更新 `loadQuestions`**：URL 参数追加 `bank_id`（条件追加）
- **更新 `onMounted`**：初始化时调用 `checkAuth()` 与 `loadOfficialBanks()`
- **更新 return 语句**：暴露所有新增变量与方法，确保模板可访问
- 语法校验：`node --check` 通过（exit 0）

### 2. `backend/templates/index.html`（+86 行）
- **Header 认证区**：在 `<h1>` 与主题切换按钮之间插入 `.nav-auth-area`（未登录显示「登录 / 注册」按钮，已登录显示昵称 + 退出按钮）
- **题库选择器**：在 `.main-content` 顶部插入 `.bank-selector-bar`（下拉分组：官方题库 / 我的题库（含新建）/ 已订阅）
- **登录/注册弹窗**：在 `#app` 闭合 `</div>` 前插入 `.modal-overlay`（学号 / 密码 / 昵称，回车提交，登录↔注册切换）
- **新增 CSS**：在 `</style>` 前追加认证区、题库选择器、弹窗样式，全部使用项目现有 CSS 变量系统保持主题一致

### 3. `backend/static/sw.js`（2 处修改）
- `CACHE_VERSION` 由 `v8` 改为 `v9`（注释行 + 常量行）

## 顾虑 / 偏差说明

1. **CSS 变量名适配（非破坏性偏差）**：任务简报提供的 CSS 使用了通用回退变量名（`--card-bg`、`--text`、`--hover-bg`、`--text-secondary`），这些在本项目中并不存在。为严格遵守简报「使用现有 CSS 变量系统保持主题一致」的要求，已将其替换为项目实际定义的变量（`--card`、`--foreground`、`--muted`、`--muted-foreground`、`--accent`、`--accent-foreground`、`--border`、`--input`、`--bg`），确保亮/暗主题下均正确渲染。

2. **圆角风格统一**：简报 CSS 使用了圆角（`border-radius: 20px/12px` 等），与本项目「像素/方块风」全局设计（`border-radius: 0` + `3px/2px` 实线边框 + 位移交互）不一致。已将新增元素的 `border-radius` 统一为 `0`，并沿用项目的 hover/active 位移微交互，保持视觉语言统一。

3. **防御性增强（向后兼容）**：在简报代码基础上做了少量不影响接口的健壮性增强：
   - 题库列表解析追加 `|| []` 防止 `undefined`；
   - `selectBank` 中对 `progress.done_question_ids` 增加 `Array.isArray` 校验后再构造 Set；
   - 题库 / 认证相关 fetch 调用包裹 `try/catch` 避免未捕获异常中断流程；
   - 登录/登出/创建题库成功或失败时追加 `showToast` 反馈，提升可用性。
   这些增强不改变任何方法签名与对外行为。

4. **无功能顾虑**：所有现有方法签名保持兼容，回归测试 151 全通过。
