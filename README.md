# 期末冲刺刷题系统

> Flask 3.0 + Vue 3 + SQLite 轻量刷题平台 · 支持桌面 exe、移动 PWA、Docker 三端部署

## 快速开始

```bash
# 1. 安装依赖
cd backend
pip install -r requirements.txt

# 2. 导入题库（首次）
python data_migration.py --db data/quiz.db import-js ../quiz-data.js

# 3. 启动服务
python app.py
# 访问 http://127.0.0.1:5000
```

## 功能

- 5 种题型：单选 / 多选 / 判断 / 填空 / 简答
- 顺序刷题 / 随机刷题 / 课程·题型·章节·关键词筛选
- 答题判分 · 错题本 · 收藏夹 · 学习统计
- 深色模式 · PWA 离线使用
- 桌面 exe（pywebview + PyInstaller）
- Docker 一键部署

## 项目结构

```
backend/          Flask 后端（app.py, config.py, database.py）
  templates/      Vue 3 SPA 模板
  static/         前端资源 + PWA（manifest, sw.js, icons）
  data/           SQLite 数据库
  tests/          回归测试 + UI 冒烟测试
desktop_app.py    桌面启动器
build.spec        PyInstaller 打包配置
config.yaml       全局配置
Dockerfile        Docker 镜像构建
```

## 部署

| 方式 | 命令 |
|------|------|
| 开发模式 | `cd backend && python app.py` |
| 桌面 exe | 双击 `dist\期末冲刺刷题系统.exe` |
| Docker | `docker-compose up -d` |

## 技术栈

Flask 3.0.3 · Werkzeug 3.0.3 · SQLite · Vue 3 · pywebview 6.2.1 · PyInstaller 6.21.0

## License

MIT
