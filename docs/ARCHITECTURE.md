# 系统架构文档

> 期末冲刺刷题系统 — 架构设计与技术决策

---

## 目录

1. [系统概述](#1-系统概述)
2. [系统上下文图](#2-系统上下文图)
3. [容器图](#3-容器图)
4. [模块图](#4-模块图)
5. [核心数据流](#5-核心数据流)
6. [权限边界](#6-权限边界)
7. [数据库表关系](#7-数据库表关系)
8. [已知架构债务](#8-已知架构债务)
9. [未来重构目标](#9-未来重构目标)

---

## 1. 系统概述

### 1.1 技术栈

| 层次 | 技术选型 | 说明 |
|------|----------|------|
| 前端 | Vue 3 (CDN) + Service Worker | 单文件 SPA，PWA 离线缓存 |
| 后端 | Flask 3.0.3 (Python) | 单文件 `app.py` 胖控制器 |
| 数据库 | SQLite (WAL 模式) | 单文件 `quiz.db`，长连接 + 线程锁 |
| 部署 | PythonAnywhere | WSGI 部署，`wsgi.py` 入口 |
| 依赖 | Flask + PyYAML + Gunicorn | 零前端构建，零重型依赖 |

### 1.2 设计原则

- **零构建前端**：Vue 3 通过 CDN 引入，无 Webpack/Vite 构建步骤
- **单数据库文件**：SQLite WAL 模式，便于备份和迁移
- **双身份模型**：匿名（session_id）+ 登录（user_id）并行支持
- **渐进增强**：主页面 Vue SPA + 轻量版服务端渲染，兼容受限浏览器
- **零外部认证服务**：自实现密码哈希、CSRF、限流，无 Redis/JWT 依赖

---

## 2. 系统上下文图

```
                    ┌──────────────────────────────────────────┐
                    │              用户浏览器                    │
                    │                                          │
                    │  ┌─────────────┐    ┌─────────────────┐  │
                    │  │ Vue 3 SPA   │    │ Service Worker  │  │
                    │  │ (index.html)│    │ (sw.js - PWA)   │  │
                    │  │             │    │ 离线缓存/拦截    │  │
                    │  └──────┬──────┘    └────────┬────────┘  │
                    │         │                    │           │
                    │         └───────┬────────────┘           │
                    │                 │ fetch()                │
                    │     X-Session-Id / Cookie / X-CSRF-Token │
                    └─────────────────┼────────────────────────┘
                                      │
                            HTTPS 请求 │
                                      │
                    ┌─────────────────┼────────────────────────┐
                    │          PythonAnywhere                   │
                    │                 │                         │
                    │     ┌───────────▼───────────┐             │
                    │     │     Flask App          │             │
                    │     │  (wsgi.py → app.py)    │             │
                    │     │                        │             │
                    │     │  32 个路由端点          │             │
                    │     │  auth.py / permissions │             │
                    │     │  csv_importer.py       │             │
                    │     │  database.py           │             │
                    │     └───────────┬───────────┘             │
                    │                 │                         │
                    │     ┌───────────▼───────────┐             │
                    │     │      SQLite            │             │
                    │     │   quiz.db (WAL)        │             │
                    │     │   11 张表               │             │
                    │     └───────────────────────┘             │
                    │                                           │
                    │   环境变量:                                │
                    │     SECRET_KEY                            │
                    │     QUIZ_ADMIN_TOKEN                      │
                    └───────────────────────────────────────────┘
```

### 2.1 外部交互

| 参与者 | 交互方式 | 说明 |
|--------|----------|------|
| 学生（匿名） | HTTPS + X-Session-Id | 无需注册即可刷题，数据按 session_id 隔离 |
| 学生（登录） | HTTPS + Session Cookie | 注册后数据持久化，支持跨设备 |
| 管理员 | HTTPS + X-Admin-Token | 通过环境变量配置的静态令牌认证 |
| PythonAnywhere | WSGI | 托管 Flask 应用，提供 HTTPS 终端 |

---

## 3. 容器图

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户浏览器                                 │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                    Vue 3 SPA                               │  │
│  │                                                           │  │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐  │  │
│  │  │ 答题模块 │  │ 统计模块  │  │ 题库模块  │  │ 认证模块   │  │  │
│  │  │         │  │          │  │          │  │           │  │  │
│  │  │ 单题模式 │  │ 进度统计  │  │ UGC题库  │  │ 登录/注册  │  │  │
│  │  │ 随机练习 │  │ 错题本    │  │ 订阅     │  │ CSRF管理   │  │  │
│  │  │ 收藏     │  │ 图表     │  │ 导入CSV  │  │           │  │  │
│  │  └─────────┘  └──────────┘  └──────────┘  └───────────┘  │  │
│  │                                                           │  │
│  │  vendor/vue.global.prod.js (CDN 本地缓存)                  │  │
│  │  js/app.js (应用逻辑)                                      │  │
│  │  js/sw-register.js (SW 注册)                               │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                 Service Worker (sw.js)                     │  │
│  │                                                           │  │
│  │  • 缓存策略: stale-while-revalidate                       │  │
│  │  • 离线回退: 缓存的 index.html                             │  │
│  │  • scope: / (全站)                                        │  │
│  │  • manifest.json (PWA 安装)                                │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
          │                              │
          │ fetch() API 请求              │ 页面请求
          ▼                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Flask 应用 (app.py)                         │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    路由层 (32 路由)                       │    │
│  │                                                         │    │
│  │  页面(3)  题目(5)  答题(3)  错题/收藏(3)                  │    │
│  │  认证(4)  题库(7)  管理(8)  举报(1)                       │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                   │
│  ┌──────────────────────────▼──────────────────────────────┐    │
│  │                   中间件层                                │    │
│  │                                                         │    │
│  │  • before_request: CSRF 校验 (csrf_protect)              │    │
│  │  • after_request: 安全响应头 (CSP/X-Frame/etc)           │    │
│  │  • require_admin: 管理员令牌校验装饰器                    │    │
│  │  • _get_session_id: 匿名身份提取                         │    │
│  │  • _get_current_user: 登录身份提取                        │    │
│  │  • _check_bank_access: 题库权限校验                       │    │
│  └──────────────────────────┬──────────────────────────────┘    │
│                             │                                   │
│  ┌──────────┬───────────────┼───────────────┬────────────────┐  │
│  │          │               │               │                │  │
│  ▼          ▼               ▼               ▼                ▼  │
│ ┌────┐  ┌────────┐  ┌────────────┐  ┌────────────┐  ┌──────┐ │  │
│ │auth│  │permis- │  │csv_importer│  │  database  │  │config│ │  │
│ │.py │  │sions.py│  │   .py      │  │   .py      │  │.py   │ │  │
│ │    │  │        │  │            │  │            │  │      │ │  │
│ │88行│  │ 68行   │  │  纯函数     │  │  884行     │  │配置  │ │  │
│ │    │  │        │  │  易测试     │  │  数据层    │  │加载  │ │  │
│ └────┘  └────────┘  └────────────┘  └─────┬──────┘  └──────┘ │  │
│                                          │                     │
└──────────────────────────────────────────┼─────────────────────┘
                                           │
                              ┌────────────▼────────────┐
                              │       SQLite            │
                              │    quiz.db (WAL)        │
                              │                         │
                              │  ┌───────────────────┐  │
                              │  │  questions        │  │
                              │  │  answer_records   │  │
                              │  │  mistakes         │  │
                              │  │  favorites        │  │
                              │  │  users            │  │
                              │  │  question_banks   │  │
                              │  │  bank_subscriptions│  │
                              │  │  reports          │  │
                              │  │  rate_limits      │  │
                              │  │  exam_sessions    │  │
                              │  │  settings         │  │
                              │  └───────────────────┘  │
                              │                         │
                              │  data/backups/ (备份)    │
                              └─────────────────────────┘
```

### 3.1 容器职责

| 容器 | 职责 | 技术细节 |
|------|------|----------|
| Browser (Vue 3 SPA) | UI 渲染、用户交互、答题逻辑 | CDN 引入 Vue 3，`{{ }}` 文本插值，无 v-html |
| Service Worker | 离线缓存、PWA 安装 | scope `/`，stale-while-revalidate 策略 |
| Flask App | 请求路由、业务逻辑、权限校验、判分 | 单文件 `app.py`，胖控制器模式 |
| SQLite | 数据持久化 | WAL 模式，长连接 + threading.Lock，11 张表 |
| PythonAnywhere | 应用托管 | WSGI 部署，HTTPS 终端，环境变量注入 |

---

## 4. 模块图

### 4.1 后端模块依赖关系

```
                    ┌─────────────┐
                    │  config.py  │
                    │  (配置加载)  │
                    └──────┬──────┘
                           │ load_config()
                           │ SECRET_KEY / QUIZ_ADMIN_TOKEN
                           ▼
    ┌──────────────────────────────────────────────────┐
    │                    app.py (781行)                  │
    │                  胖控制器 / 路由层                  │
    │                                                  │
    │  ┌──────────┐  ┌───────────┐  ┌──────────────┐   │
    │  │ 32 路由  │  │ _check_   │  │ _get_session │   │
    │  │          │  │ bank_access│  │ _id / user   │   │
    │  │ GET /    │  │           │  │              │   │
    │  │ POST/    │  │ require_  │  │ _positive_   │   │
    │  │ PUT/     │  │ admin     │  │ int_arg      │   │
    │  │ DELETE   │  │           │  │              │   │
    │  └────┬─────┘  └─────┬─────┘  └──────────────┘   │
    │       │              │                           │
    └───────┼──────────────┼───────────────────────────┘
            │              │
            │     ┌────────▼────────┐
            │     │  permissions.py │
            │     │    (68行)       │
            │     │                 │
            │     │ can_read_bank   │
            │     │ can_write_bank  │
            │     │ can_import_     │
            │     │   to_bank       │
            │     │                 │
            │     │ Bank / User     │
            │     │   数据类        │
            │     └─────────────────┘
            │
     ┌──────┼──────────────┐
     │      │              │
     ▼      ▼              ▼
┌────────┐  ┌──────────┐  ┌──────────────┐
│auth.py │  │csv_imp-  │  │ database.py  │
│(88行)  │  │orter.py  │  │  (884行)     │
│        │  │          │  │              │
│hash_   │  │parse_csv │  │QuizDatabase  │
│password│  │          │  │              │
│        │  │generate_ │  │  _init_db    │
│verify_ │  │ template │  │  _pre/post_  │
│password│  │          │  │   migrate    │
│        │  │sanitize_ │  │              │
│validate│  │ question │  │  CRUD:       │
│_password│ │          │  │  questions   │
│        │  │REQUIRED_ │  │  banks       │
│validate│  │  FIELDS  │  │  users       │
│_student│  │          │  │  reports     │
│  _id   │  │SENSITIVE │  │  favorites   │
│        │  │  _WORDS  │  │  mistakes    │
│ensure_ │  └──────────┘  │  answer_     │
│csrf_   │                │   records    │
│  token │                │              │
│        │                │  connection()│
│csrf_   │                │  (上下文管理) │
│ protect│                │              │
│        │                │  migrate_    │
│check_  │                │  session_data│
│rate_   │                └──────────────┘
│  limit │
└────────┘
```

### 4.2 模块职责明细

| 模块 | 行数 | 职责 | 关键函数/类 |
|------|------|------|-------------|
| `app.py` | 781 | 路由定义、请求处理、判分逻辑、胖控制器 | `index()`, `api_submit()`, `_check_answer()`, `_check_bank_access()`, `require_admin` |
| `auth.py` | 88 | 密码哈希、CSRF、限流（零外部依赖） | `hash_password()`, `verify_password()`, `ensure_csrf_token()`, `csrf_protect()`, `check_rate_limit()` |
| `permissions.py` | 68 | 题库读写权限模型 | `can_read_bank()`, `can_write_bank()`, `can_import_to_bank()`, `Bank`, `User` |
| `database.py` | 884 | SQLite 数据层、数据库迁移、所有 CRUD | `QuizDatabase`, `_init_db()`, `search_questions()`, `record_answer()`, `migrate_session_data()` |
| `csv_importer.py` | ~180 | CSV 解析、模板生成、题目消毒 | `parse_csv()`, `generate_template()`, `sanitize_question()` |
| `config.py` | ~45 | 配置加载（YAML + 环境变量） | `load_config()`, `DEFAULT_CONFIG` |
| `lite.py` | — | 轻量版服务端渲染 | `render_lite_page()` |
| `wsgi.py` | — | PythonAnywhere WSGI 入口 | — |

### 4.3 模块间调用关系

```
app.py
  ├── config.load_config()          # 启动时加载配置
  ├── database.QuizDatabase()       # 启动时初始化数据库
  ├── auth.hash_password()          # 注册时
  ├── auth.verify_password()        # 登录时
  ├── auth.validate_password()      # 注册时校验
  ├── auth.validate_student_id()    # 注册时校验
  ├── auth.ensure_csrf_token()      # 登录/注册后
  ├── auth.csrf_protect()           # before_request 中间件
  ├── auth.check_rate_limit()       # 登录/注册/导入/举报
  ├── permissions.can_read_bank()   # 题库读权限
  ├── permissions.can_write_bank()  # 题库写权限
  ├── permissions.can_import_to_bank() # 题库导入权限
  ├── permissions.Bank / User       # 权限数据类
  ├── csv_importer.parse_csv()      # CSV 导入
  ├── csv_importer.generate_template() # 模板下载
  ├── csv_importer.sanitize_question() # 题目消毒
  ├── lite.render_lite_page()       # 轻量版渲染
  └── database.QuizDatabase.*       # 所有数据操作
```

---

## 5. 核心数据流

### 5.1 答题流程

```
 用户选择答案并点击"提交"
         │
         ▼
┌─────────────────┐
│  Vue SPA        │
│  app.js         │
│                 │
│  组装请求:       │
│  {              │
│    question_id, │
│    answer,      │
│    elapsed_secs,│
│    bank_id      │
│  }              │
│                 │
│  Headers:       │
│    X-Session-Id │ (匿名)
│    Cookie       │ (登录)
│    X-CSRF-Token │ (登录)
└────────┬────────┘
         │ POST /api/submit
         ▼
┌─────────────────────────────────────────┐
│  Flask app.py - api_submit()            │
│                                         │
│  1. 解析 JSON body                      │
│  2. _get_current_user() → user/None     │
│  3. _check_bank_access(bank_id, user)   │
│     └─ can_read_bank(user, bank)        │
│        └─ 403 if 无权                   │
│  4. db.get_question(qid)                │
│     └─ 404 if 不存在                    │
│  5. _check_answer(type, ans, correct)   │
│     └─ 单选: 大写比较                    │
│     └─ 多选: 排序比较                    │
│     └─ 判断: 归一化比较                  │
│     └─ 填空: 去空白比较                  │
│     └─ 简答: 包含匹配                   │
│  6. _get_session_id() → sid             │
│  7. db.record_answer(                   │
│       qid, answer, correct,             │
│       elapsed, sid, user_id, bank_id)   │
│     └─ INSERT answer_records            │
│     └─ if correct:                      │
│          DELETE mistakes                │
│     └─ if wrong:                        │
│          UPSERT mistakes                │
│                                         │
│  返回: {correct, correct_answer,        │
│         explanation, knowledge}         │
└──────────────────┬──────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Vue SPA                                 │
│                                          │
│  • 显示正确/错误反馈                      │
│  • 显示正确答案和解析                     │
│  • 更新本地进度统计                       │
│  • 答对: 移出错题本                       │
│  • 答错: 加入错题本                       │
└──────────────────────────────────────────┘
```

### 5.2 登录流程

```
 用户输入学号+密码，点击"登录"
         │
         ▼
┌─────────────────┐
│  Vue SPA        │
│  POST /api/auth/│
│    login        │
│  {              │
│    student_id,  │
│    password     │
│  }              │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│  Flask app.py - api_login()                 │
│                                             │
│  1. check_rate_limit(db, "login:ip:{ip}",   │
│                      10, 10)                │
│     └─ 429 if 超限                           │
│                                             │
│  2. db.get_user_by_student_id(student_id)   │
│     └─ 401 if 用户不存在                     │
│                                             │
│  3. verify_password(password,               │
│                     user['password_hash'])  │
│     └─ secrets.compare_digest() 常量时间     │
│     └─ 401 if 密码错误                       │
│                                             │
│  4. 保留旧 csrf_token (如果有)               │
│  5. session.clear()                         │
│  6. session['user_id'] = user['id']         │
│  7. session['role'] = user['role']          │
│  8. session.permanent = True (30天)          │
│  9. ensure_csrf_token() → 新 CSRF token     │
│                                             │
│  10. sid = _get_session_id()                │
│  11. if sid != 'anon':                      │
│        db.migrate_session_data(uid, sid)    │
│        └─ 迁移匿名答题/错题/收藏到 user_id   │
│        └─ 去重: 已有同题记录不重复迁移        │
│        └─ 清理: 删除残留的匿名记录            │
│                                             │
│  返回: {id, student_id, nickname,           │
│         role, csrf_token}                   │
└──────────────────┬──────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Vue SPA                                 │
│                                          │
│  • 保存 csrf_token 到内存                 │
│  • 后续写请求携带 X-CSRF-Token            │
│  • 切换到登录态 UI                        │
│  • 重新拉取统计数据 (现在按 user_id)       │
└──────────────────────────────────────────┘
```

### 5.3 CSV 导入流程

```
 用户在题库管理页选择 CSV 文件并上传
         │
         ▼
┌─────────────────────┐
│  Vue SPA            │
│  POST /api/banks/   │
│    <id>/import      │
│                     │
│  multipart/form-data│
│  file: xxx.csv      │
│                     │
│  Headers:           │
│    Cookie (登录)    │
│    X-CSRF-Token     │
└──────────┬──────────┘
           │
           ▼
┌──────────────────────────────────────────────────┐
│  Flask app.py - api_bank_import()                │
│                                                  │
│  1. _get_current_user() → user                   │
│     └─ 401 if 未登录                              │
│                                                  │
│  2. db.get_bank(bank_id)                         │
│     └─ 404 if 题库不存在                          │
│                                                  │
│  3. can_import_to_bank(user, bank)               │
│     └─ can_write_bank() → 403 if 无权             │
│                                                  │
│  4. check_rate_limit(db,                         │
│       "import:user:{uid}", 10, 1440)             │
│     └─ 429 if 当日超 10 次                        │
│                                                  │
│  5. 读取 CSV 内容 (file 或 JSON content)          │
│     └─ utf-8-sig 解码 (处理 BOM)                  │
│                                                  │
│  6. parse_csv(content)                           │
│     ┌──────────────────────────────────┐         │
│     │ csv_importer.parse_csv()         │         │
│     │                                  │         │
│     │  • 处理 BOM 头                    │         │
│     │  • DictReader 解析               │         │
│     │  • 校验表头 (REQUIRED_FIELDS)     │         │
│     │  • 逐行校验:                      │         │
│     │    - 必填字段                     │         │
│     │    - 题型 (VALID_TYPES)           │         │
│     │    - 章节号 (正整数)              │         │
│     │  • 解析答案:                      │         │
│     │    - multiple: 逗号分隔           │         │
│     │    - fill_blank: 管道符分隔       │         │
│     │  • 返回 {questions, errors}       │         │
│     └──────────────────────────────────┘         │
│                                                  │
│  7. len(questions) > 500 → 400                   │
│                                                  │
│  8. 逐题 sanitize_question(q)                    │
│     ┌──────────────────────────────────┐         │
│     │ csv_importer.sanitize_question() │         │
│     │                                  │         │
│     │  • 长度校验 (stem≤2000, opt≤500) │         │
│     │  • 检测敏感词 (原始文本):         │         │
│     │    <script, javascript:, onerror,│         │
│     │    onload, onclick               │         │
│     │    → _flagged = True             │         │
│     │  • HTML 转义 (html.escape)       │         │
│     │  • 返回处理后的 dict              │         │
│     └──────────────────────────────────┘         │
│                                                  │
│  9. db.batch_add_questions(valid, bank_id)       │
│     └─ INSERT OR IGNORE (UNIQUE(bank_id,stem))   │
│     └─ 自动去重                                   │
│                                                  │
│  10. db.update_bank_question_count(bank_id)      │
│                                                  │
│  返回: {ok, imported, skipped, flagged, errors}  │
└──────────────────┬───────────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Vue SPA                                 │
│                                          │
│  • 显示导入结果: 成功N条, 跳过N条          │
│  • 显示被标记(flagged)的题目数             │
│  • 显示解析错误列表 (行号+原因)            │
│  • 刷新题库题目计数                        │
└──────────────────────────────────────────┘
```

### 5.4 订阅流程

```
 用户浏览公开题库列表，点击"订阅"
         │
         ▼
┌──────────────────────┐
│  Vue SPA             │
│  POST /api/banks/    │
│    <id>/subscribe    │
│                      │
│  Headers:            │
│    Cookie (登录)     │
│    X-CSRF-Token      │
└──────────┬───────────┘
           │
           ▼
┌──────────────────────────────────────────────┐
│  Flask app.py - api_bank_subscribe()         │
│                                              │
│  1. _get_current_user() → user               │
│     └─ 401 if 未登录                          │
│                                              │
│  2. db.get_bank(bank_id)                     │
│     └─ 404 if 不存在                          │
│                                              │
│  3. POST (订阅):                              │
│     • bank.visibility == 'public'?           │
│       └─ 403 if 非 public                     │
│     • bank.status == 'active'?               │
│       └─ 403 if 非 active                     │
│     • db.subscribe_bank(user_id, bank_id)    │
│       └─ INSERT bank_subscriptions            │
│       └─ IntegrityError → 已订阅 (幂等)       │
│                                              │
│  4. DELETE (退订):                            │
│     • db.unsubscribe_bank(user_id, bank_id)  │
│       └─ DELETE bank_subscriptions            │
│                                              │
│  返回: {"ok": true}                          │
└──────────────────┬───────────────────────────┘
                   │
                   ▼
┌──────────────────────────────────────────┐
│  Vue SPA                                 │
│                                          │
│  订阅后:                                  │
│  • 题库出现在 "已订阅" 列表                │
│  • 可通过 /api/questions?bank_id=X 答题   │
│  • 可查看 /api/banks/<id>/progress 进度   │
│                                          │
│  退订后:                                  │
│  • 题库从 "已订阅" 列表移除                │
│  • 答题进度保留（不删除）                  │
└──────────────────────────────────────────┘
```

---

## 6. 权限边界

### 6.1 权限层级模型

系统定义了四级身份，权限从低到高：

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│anonymous │ <  │ student  │ <  │  owner   │    │  admin   │
│ (匿名)   │    │ (学生)   │    │ (题库主) │    │ (管理员) │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
```

| 身份 | 标识 | 读权限 | 写权限 | 管理权限 |
|------|------|--------|--------|----------|
| anonymous | `X-Session-Id` | 官方题库 + 公开题库 | 无 | 无 |
| student | `session['user_id']` | 官方题库 + 公开题库 + 自己的题库 | 自己的题库 | 无 |
| owner | `user.id == bank.owner_id` | + 自己的私有题库 | + 自己的题库 | 无 |
| admin | `session['role'] == 'admin'` | 全部（含 hidden/deleted） | 全部（含官方题库） | 全部 |

### 6.2 权限函数调用链

```
_check_bank_access(bank_id, user, write=False)
    │
    ├─ bank_id is None or bank_id == 1?
    │   └─ YES → 允许 (官方题库，任何人可读)
    │
    ├─ db.get_bank(bank_id)
    │   └─ None → 404 (题库不存在)
    │
    ├─ Bank(bank_data)  # 封装为权限对象
    ├─ User(user)       # 封装为权限对象
    │
    └─ write=False → can_read_bank(user, bank)
       write=True  → can_write_bank(user, bank)
       │
       └─ 不允许 → 403 (无权访问)
```

### 6.3 `can_read_bank` 决策表

| bank.status | bank.owner_id | bank.visibility | user | 结果 |
|-------------|---------------|-----------------|------|------|
| hidden / deleted | * | * | None / student / owner | **False** |
| hidden / deleted | * | * | admin | **True** |
| * | NULL (官方) | * | 任何人 | **True** |
| active | 5 | public | 任何人 | **True** |
| active | 5 | private | user.id=5 | **True** |
| active | 5 | private | user.id=3 | **False** |
| active | 5 | private | None | **False** |
| active | 5 | private/unlisted | admin | **True** |

### 6.4 `can_write_bank` 决策表

| bank.owner_id | user.role | user.id == owner_id | 结果 |
|---------------|-----------|---------------------|------|
| NULL (官方) | admin | — | **True** |
| NULL (官方) | student | — | **False** |
| 5 | admin | — | **True** |
| 5 | student | True | **True** |
| 5 | student | False | **False** |
| 5 | None | — | **False** |

### 6.5 权限校验位置

| 端点 | 权限函数 | 位置 |
|------|----------|------|
| `GET /api/questions` | `_check_bank_access(bank_id, user)` | app.py:222 |
| `GET /api/questions/random` | `_check_bank_access(bank_id, user)` | app.py:243 |
| `POST /api/submit` | `_check_bank_access(bank_id, user, write=False)` | app.py:280 |
| `GET /api/banks/<id>` | `can_read_bank(user, bank)` | app.py:656 |
| `PUT /api/banks/<id>` | `can_write_bank(user, bank)` | app.py:661 |
| `DELETE /api/banks/<id>` | `can_write_bank(user, bank)` | app.py:668 |
| `GET /api/banks/<id>/questions` | `can_read_bank(user, bank)` | app.py:682 |
| `GET /api/banks/<id>/progress` | `can_read_bank(user, bank)` | app.py:703 |
| `POST /api/banks/<id>/import` | `can_import_to_bank(user, bank)` | app.py:757 |
| `POST /api/banks/<id>/subscribe` | visibility + status 检查 | app.py:898 |
| `GET/POST /api/admin/*` | `require_admin` 装饰器 | app.py:59-69 |

---

## 7. 数据库表关系

### 7.1 ER 图

```
┌───────────────────┐         ┌──────────────────────┐
│     users         │         │   question_banks     │
├───────────────────┤         ├──────────────────────┤
│ id (PK)           │◄──┐     │ id (PK)              │
│ student_id (UQ)   │   │     │ owner_id (FK) ───────┘  ←─ NULL = 官方题库
│ password_hash     │   │     │ name                 │
│ nickname          │   │     │ course               │
│ role              │   │     │ description          │
│ created_at        │   │     │ visibility           │
└───────────────────┘   │     │ status               │
                        │     │ question_count       │
                        │     │ created_at           │
                        │     └──────┬───────────────┘
                        │            │
                        │            │ 1:N
                        │            ▼
                        │     ┌──────────────────────┐
                        │     │     questions        │
                        │     ├──────────────────────┤
                        │     │ id (PK)              │
                        │     │ original_id          │
                        │     │ bank_id (FK) ────────┘  ←─ question_banks.id
                        │     │ course               │
                        │     │ chapter              │
                        │     │ type                 │
                        │     │ stem                 │
                        │     │ options_json         │
                        │     │ answer_json          │
                        │     │ explanation          │
                        │     │ knowledge            │
                        │     │ difficulty           │
                        │     │ flagged              │
                        │     │ created_at           │
                        │     │ updated_at           │
                        │     │ UNIQUE(bank_id, stem)│
                        │     └──────┬───────────────┘
                        │            │
          ┌─────────────┼────────────┼─────────────────────┐
          │             │            │                     │
          │             │            │ 1:N                 │
          │             │            ▼                     ▼
          │  ┌──────────┴──┐  ┌──────────────┐  ┌──────────────┐
          │  │answer_records│  │  mistakes    │  │  favorites   │
          │  ├──────────────┤  ├──────────────┤  ├──────────────┤
          │  │id (PK)       │  │id (PK)       │  │id (PK)       │
          │  │question_id   │  │question_id   │  │question_id   │
          └──│user_id (FK)  │  │user_id (FK)  │  │user_id (FK)  │
             │session_id    │  │session_id    │  │session_id    │
             │bank_id       │  │bank_id       │  │bank_id       │
             │user_answer   │  │wrong_count   │  │tag           │
             │correct       │  │last_wrong_at │  │created_at    │
             │elapsed_secs  │  │UNIQUE(qid,   │  │UNIQUE(qid,   │
             │created_at    │  │  session_id) │  │  session_id) │
             │              │  │UNIQUE(uid,   │  │UNIQUE(uid,   │
             │              │  │  qid) WHERE  │  │  qid) WHERE  │
             │              │  │  uid NOT NULL│  │  uid NOT NULL│
             └──────────────┘  └──────────────┘  └──────────────┘

┌─────────────────────┐  ┌──────────────────────┐  ┌──────────────────┐
│ bank_subscriptions  │  │      reports         │  │   rate_limits    │
├─────────────────────┤  ├──────────────────────┤  ├──────────────────┤
│ user_id (FK) ───────┘  │ id (PK)              │  │ key              │
│ bank_id (FK) ────────┘  │ reporter_id (FK) ────┘  │ count           │
│ subscribed_at          │ session_id            │  │ window_start    │
│ PK(user_id, bank_id)  │ question_id            │  │ PK(key, window) │
└─────────────────────┘  │ reason                │  └──────────────────┘
                         │ detail                │
                         │ status                │
                         │ handled_by            │
                         │ handled_at            │
                         │ admin_note            │
                         │ created_at            │
                         │ UNIQUE(reporter_id,   │
                         │   question_id)        │
                         │  WHERE reporter_id    │
                         │  IS NOT NULL          │
                         └──────────────────────┘

┌──────────────────┐  ┌──────────────────┐
│  exam_sessions   │  │    settings      │
├──────────────────┤  ├──────────────────┤
│ id (PK)          │  │ key (PK)         │
│ mode             │  │ value            │
│ question_ids     │  └──────────────────┘
│ start_time       │
│ duration         │
│ completed        │
│ score            │
└──────────────────┘
```

### 7.2 表清单（11 张表）

| # | 表名 | 用途 | 关键约束 |
|---|------|------|----------|
| 1 | `questions` | 题目存储 | `UNIQUE(bank_id, stem)` 去重 |
| 2 | `answer_records` | 答题记录 | FK → questions；session_id + user_id 双身份 |
| 3 | `mistakes` | 错题记录 | `UNIQUE(question_id, session_id)`；`UNIQUE(user_id, question_id) WHERE user_id IS NOT NULL` |
| 4 | `favorites` | 收藏记录 | `UNIQUE(question_id, session_id)`；`UNIQUE(user_id, question_id) WHERE user_id IS NOT NULL` |
| 5 | `users` | 用户账号 | `student_id UNIQUE`；`role CHECK IN ('student', 'admin')` |
| 6 | `question_banks` | 题库元数据 | `visibility CHECK IN ('private','public','unlisted')`；`status CHECK IN ('active','hidden','deleted','reviewing')` |
| 7 | `bank_subscriptions` | 订阅关系 | `PK(user_id, bank_id)` 防重复 |
| 8 | `reports` | 题目举报 | `UNIQUE(reporter_id, question_id) WHERE reporter_id IS NOT NULL` 防重复举报 |
| 9 | `rate_limits` | 限流计数 | `PK(key, window_start)` |
| 10 | `exam_sessions` | 考试会话（预留） | 当前未使用 |
| 11 | `settings` | 系统设置（KV） | 当前未使用 |

### 7.3 数据库迁移历史

`database.py` 的 `_init_db()` 包含 4 步迁移，每次启动自动执行（幂等）：

| 步骤 | 方法 | 作用 |
|------|------|------|
| Step 0 | `_pre_migrate()` | 为旧版 answer_records/mistakes/favorites 添加 `session_id` 列 |
| Step 1 | `executescript()` | 创建所有表（IF NOT EXISTS） |
| Step 2 | `_post_migrate()` | 重建 mistakes/favorites 表，更新 UNIQUE 约束为 `(question_id, session_id)` |
| Step 3 | `_migrate_to_banks()` | questions 表重建为 bank_id 架构，创建 question_banks 表，插入官方题库记录 |
| Step 4 | `_migrate_user_bank_columns()` | 为 answer_records/mistakes/favorites 添加 `user_id` 和 `bank_id` 列，创建复合索引 |

---

## 8. 已知架构债务

### 8.1 双身份模型 (session_id + user_id)

**问题**：系统同时维护匿名 `session_id` 和登录 `user_id` 两种身份标识，几乎所有数据查询都需要 if-else 分支：

```python
# database.py 中大量此类分支
if user_id:
    rows = conn.execute("... WHERE user_id = ?", (user_id,))
else:
    rows = conn.execute("... WHERE session_id = ?", (session_id,))
```

**影响**：
- `get_stats()`、`get_mistakes()`、`get_favorites()` 等方法因双身份分支导致代码量翻倍
- 数据迁移逻辑（`migrate_session_data`）复杂，需处理去重和清理
- 匿名用户的 POST 请求不受 CSRF 保护（安全债务）

**缓解措施**：
- `migrate_session_data()` 幂等设计，可重复执行
- 迁移时去重（已有同题记录不重复迁移）+ 清理（删除残留匿名记录）

### 8.2 app.py 胖控制器 (781 行)

**问题**：`app.py` 承担了路由定义、请求处理、判分逻辑、权限校验、CSRF 中间件、安全响应头等过多职责，所有 32 个路由集中在单文件中。

**影响**：
- 文件过大，难以导航和维护
- 路由间缺乏模块边界，职责混杂
- 判分逻辑 `_check_answer()` 与路由耦合
- `_check_bank_access()` 既做权限判断又生成错误响应，职责不单一

**缓解措施**：
- 权限逻辑已抽取到 `permissions.py`
- CSV 解析已抽取到 `csv_importer.py`
- 认证逻辑已抽取到 `auth.py`

### 8.3 database.py 过载 (884 行)

**问题**：`QuizDatabase` 类承担了所有表的 CRUD、数据库迁移、数据导出等职责，单类方法数过多。

**影响**：
- 单类职责过重，违反单一职责原则
- 数据库迁移逻辑（4 步）与业务 CRUD 混杂
- 双身份查询分支导致方法膨胀
- 缺乏 Repository 模式的抽象

**缓解措施**：
- 迁移逻辑已分离为独立方法（`_pre_migrate` / `_post_migrate` / `_migrate_to_banks` / `_migrate_user_bank_columns`）
- 使用 `connection()` 上下文管理器统一事务管理

### 8.4 其他技术债

| 债务项 | 说明 | 影响 |
|--------|------|------|
| 长连接 + 线程锁 | `sqlite3.connect(check_same_thread=False)` + `threading.Lock()` | 高并发下锁竞争，但 PythonAnywhere 单进程可接受 |
| `exam_sessions` / `settings` 表未使用 | 预留功能未实现 | 无实际影响，但增加迁移复杂度 |
| `_check_answer` 在 app.py 中 | 判分逻辑应在业务层 | 难以独立测试和复用 |
| 管理员 API 无 Blueprint | 8 个管理路由散落在 app.py | 难以独立维护和权限管理 |
| `GET /api/questions/<qid>` 无题库权限校验 | 单题获取端点未校验 bank_id | 可通过 ID 枚举访问私有题库题目 |

---

## 9. 未来重构目标

### 9.1 Blueprint 拆分

将 `app.py` 的 32 个路由按业务域拆分为 Flask Blueprint：

```
backend/
├── blueprints/
│   ├── __init__.py
│   ├── pages.py          # 页面路由 (3): /, /lite, /sw.js
│   ├── questions.py      # 题目路由 (5): /api/questions/*
│   ├── answers.py        # 答题路由 (3): /api/submit, /api/stats, /api/reset_stats
│   ├── favorites.py      # 错题/收藏 (3): /api/mistakes, /api/favorites/*
│   ├── auth.py           # 认证路由 (4): /api/auth/*
│   ├── banks.py          # 题库路由 (7): /api/banks/*
│   ├── admin.py          # 管理路由 (8): /api/admin/*
│   └── reports.py        # 举报路由 (1): /api/questions/<id>/report
├── services/
│   ├── scoring.py        # 判分逻辑 (_check_answer)
│   └── ...
└── app.py                # Flask app 工厂 + Blueprint 注册
```

**预期收益**：
- 每个 Blueprint 文件 50-150 行，可维护性大幅提升
- 路由按域隔离，便于独立测试
- 中间件可按 Blueprint 粒度配置

### 9.2 Repository 模式

将 `database.py` 的 CRUD 按实体拆分为 Repository：

```
backend/
├── repositories/
│   ├── __init__.py
│   ├── base.py           # BaseRepository (connection, 基础查询)
│   ├── question_repo.py  # QuestionRepository
│   ├── bank_repo.py      # BankRepository
│   ├── user_repo.py      # UserRepository
│   ├── answer_repo.py    # AnswerRepository (answer_records, mistakes, favorites)
│   ├── report_repo.py    # ReportRepository
│   └── rate_limit_repo.py # RateLimitRepository
├── migrations/
│   ├── __init__.py
│   └── schema.py         # 数据库 schema 定义和迁移
└── ...
```

**预期收益**：
- 每个 Repository 职责单一，100-200 行
- 数据库迁移逻辑独立管理
- 双身份查询可在 Repository 层统一封装

### 9.3 身份统一

将匿名 `session_id` 和登录 `user_id` 统一为单一身份模型：

**方案**：所有用户（含匿名）在首次访问时创建 `users` 表记录（`role='anonymous'`），`session_id` 映射为 `user.id`。

**预期收益**：
- 消除所有 `if user_id / else session_id` 分支
- `migrate_session_data` 逻辑简化为 `UPDATE user_id` 单步操作
- 匿名用户 POST 请求可纳入 CSRF 保护
- 统一的数据隔离查询逻辑

**风险**：
- 需要数据库迁移脚本
- 匿名用户数据量可能膨胀（需定期清理策略）
- 前端需调整 session_id 生成和传递逻辑

### 9.4 其他改进项

| 改进项 | 优先级 | 说明 |
|--------|--------|------|
| 判分逻辑抽取到 `services/scoring.py` | 高 | 独立可测试，复用性提升 |
| `GET /api/questions/<qid>` 增加题库权限校验 | 高 | 安全修复 |
| 添加 API 版本前缀 `/api/v1/` | 中 | 为未来 API 变更留余地 |
| 引入 Pydantic 请求模型校验 | 中 | 替代手动 `data.get()` 校验 |
| SQLite → PostgreSQL 迁移评估 | 低 | 高并发场景考虑 |
| 前端 Vue 3 CDN → 本地构建 | 低 | 消除 `unsafe-eval` CSP 依赖 |
