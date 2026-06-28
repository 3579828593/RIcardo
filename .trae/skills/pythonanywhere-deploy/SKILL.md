---
name: "pythonanywhere-deploy"
description: "Manage PythonAnywhere web app deployment: update code, reload, check status, view logs, backup database. Invoke when user asks to update/deploy/reload the quiz system or any PythonAnywhere app, or mentions 3579828593.pythonanywhere.com."
---

# PythonAnywhere 部署运维技能

## 适用场景

当用户提到以下任何一种需求时，自动调用此技能：
- 更新线上刷题系统代码
- 部署/重载 PythonAnywhere 应用
- 查看应用状态或日志
- 备份数据库
- 任何涉及 `3579828593.pythonanywhere.com` 的操作

## 核心信息

| 项目 | 值 |
|------|-----|
| 线上地址 | https://3579828593.pythonanywhere.com |
| GitHub 仓库 | https://github.com/3579828593/RIcardo.git |
| PythonAnywhere 用户名 | 3579828593 |
| Python 版本 | 3.10 |
| 项目路径（远程） | ~/RIcardo/backend |
| WSGI 文件 | /var/www/3579828593_pythonanywhere_com_wsgi.py |
| 运维脚本 | d:\期末冲刺刷题系统\scripts\pa_deploy.py |
| API Token 文件 | ~/.pa_token |
| 用户名文件 | ~/.pa_username |

## 标准工作流

### 1. 更新代码（最常用）

当用户说"更新应用"、"推送代码到线上"时：

```bash
# 步骤 1: 本地提交并推送
cd d:\期末冲刺刷题系统
git add -A
git commit -m "描述变更内容"
git push origin main

# 步骤 2: 远程更新
python scripts\pa_deploy.py update
```

`pa_deploy.py update` 会自动完成：git pull → 检查依赖 → 重载应用 → 验证

### 2. 查看状态

当用户说"看看网站状态"、"网站正常吗"时：

```bash
python scripts\pa_deploy.py status
```

会显示：应用状态、CPU 用量、题库总数、网站可访问性

### 3. 完整重部署

当用户说"重新部署"、"重装"时：

```bash
python scripts\pa_deploy.py deploy
```

会完成：克隆仓库 → 安装依赖 → 初始化数据库 → 配置 WSGI → 重载

### 4. 查看错误日志

当用户说"看看日志"、"网站报错了"时：

```bash
python scripts\pa_deploy.py logs
```

### 5. 仅重载（不拉代码）

当用户说"重载一下"、"重启"时：

```bash
python scripts\pa_deploy.py reload    # 普通重载
python scripts\pa_deploy.py restart   # 强制重启（清理缓存）
```

### 6. 备份数据库

当用户说"备份数据库"时：

```bash
python scripts\pa_deploy.py backup
```

### 7. 执行远程命令

当用户需要在 PythonAnywhere 上执行特定命令时：

```bash
python scripts\pa_deploy.py console "ls ~/RIcardo/backend/data/"
```

## 首次配置（已完成则跳过）

如果 `~/.pa_token` 或 `~/.pa_username` 不存在：

```bash
python scripts\pa_deploy.py setup 3579828593 <API_TOKEN>
```

API Token 获取地址：https://www.pythonanywhere.com/account/#api_token

## 注意事项

- **免费账户限制**：每天 100 CPU 秒，512MB 存储
- **3 个月续期**：免费 Web 应用每 3 个月需在网页上点击"Run until 1 month from today"
- **Python 版本**：Web 应用使用 3.10，安装依赖必须用 `pip3.10`
- **数据库锁定**：SQLite 在高并发时可能锁定，出现 500 错误时执行 `restart`
- **git push 前测试**：推送前建议运行 `python -m pytest backend/tests/test_regression.py`

## 故障排除

| 症状 | 原因 | 解决方案 |
|------|------|----------|
| 500 错误 | SQLite 锁定 | `python scripts\pa_deploy.py restart` |
| 模块导入错误 | 依赖未装到 3.10 | `pa_deploy.py console "pip3.10 install --user -r ~/RIcardo/backend/requirements.txt"` |
| 502 错误 | 应用未启动 | `python scripts\pa_deploy.py reload` |
| 页面空白 | WSGI 配置错误 | `python scripts\pa_deploy.py deploy` |
| git pull 冲突 | 远程有手动修改 | `pa_deploy.py console "cd ~/RIcardo && git stash && git pull"` |

## Agent 执行指引

当 Agent 收到与此技能相关的请求时：

1. **先判断操作类型**：更新 / 状态查询 / 重载 / 日志 / 备份 / 重部署
2. **检查前置条件**：`~/.pa_token` 和 `~/.pa_username` 是否存在
3. **执行对应命令**：使用 RunCommand 工具运行 `pa_deploy.py`
4. **验证结果**：检查输出是否包含 `[OK]` 或 `[验证]`
5. **如果失败**：查看日志 `pa_deploy.py logs`，按故障排除表处理
6. **报告结果**：告知用户线上地址和操作结果
