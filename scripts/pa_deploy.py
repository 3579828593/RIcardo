#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PythonAnywhere 运维自动化脚本

用法:
  python pa_deploy.py status          # 查看应用状态
  python pa_deploy.py update          # 拉取最新代码 + 重载应用
  python pa_deploy.py deploy          # 完整部署（首次或重装）
  python pa_deploy.py reload          # 仅重载应用
  python pa_deploy.py logs            # 查看错误日志
  python pa_deploy.py console <cmd>   # 在远程控制台执行命令
  python pa_deploy.py backup          # 备份远程数据库到本地
  python pa_deploy.py restart         # 强制重启（删除临时文件+重载）

前置条件:
  - PythonAnywhere 账户已注册
  - API Token 已创建（https://www.pythonanywhere.com/account/#api_token）
  - 本地文件 ~/.pa_token 存储了 token，或设置环境变量 PA_TOKEN
  - 本地文件 ~/.pa_username 存储了用户名，或设置环境变量 PA_USERNAME

首次配置:
  python pa_deploy.py setup <username> <token>
"""
import os
import sys
import json
import time
import urllib.request
import urllib.error

# ============================================================
# 配置区
# ============================================================
HOME = os.path.expanduser("~")
TOKEN_FILE = os.path.join(HOME, ".pa_token")
USERNAME_FILE = os.path.join(HOME, ".pa_username")
HOST = "www.pythonanywhere.com"
DOMAIN_SUFFIX = "pythonanywhere.com"

# 部署常量（一般无需修改）
PROJECT_REPO = "https://github.com/3579828593/RIcardo.git"
PROJECT_DIR = "~/RIcardo"
BACKEND_DIR = "~/RIcardo/backend"
PYTHON_VERSION = "3.10"
WSGI_PATH = "/var/www/{username}_pythonanywhere_com_wsgi.py"


def load_config():
    """从文件或环境变量加载 token 和 username"""
    token = os.environ.get("PA_TOKEN", "")
    username = os.environ.get("PA_USERNAME", "")
    if not token and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            token = f.read().strip()
    if not username and os.path.exists(USERNAME_FILE):
        with open(USERNAME_FILE, "r") as f:
            username = f.read().strip()
    if not token or not username:
        print("[ERROR] 未找到 API Token 或用户名。")
        print("        请运行: python pa_deploy.py setup <username> <token>")
        sys.exit(1)
    return token, username


def save_config(username, token):
    """保存配置到本地文件"""
    with open(USERNAME_FILE, "w") as f:
        f.write(username.strip())
    with open(TOKEN_FILE, "w") as f:
        f.write(token.strip())
    print(f"[OK] 配置已保存: username={username}, token={token[:8]}...")


def api_call(token, username, method, path, data=None, expect_json=True):
    """调用 PythonAnywhere API"""
    url = f"https://{HOST}/api/v0/user/{username}/{path}"
    headers = {"Authorization": f"Token {token}"}
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            text = resp.read().decode("utf-8")
            if expect_json:
                return json.loads(text) if text else {}
            return text
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        print(f"[API ERROR] {e.code} {e.reason}: {error_body[:200]}")
        return None
    except Exception as e:
        print(f"[ERROR] {e}")
        return None


def get_console_id(token, username):
    """获取或创建 Bash 控制台 ID"""
    consoles = api_call(token, username, "GET", "consoles/")
    if not consoles:
        print("[WARN] 没有活跃的控制台，正在创建...")
        result = api_call(token, username, "POST", "consoles/", {
            "executable": "bash",
            "arguments": "",
            "working_directory": None
        })
        if result:
            return result.get("id")
        return None
    # 返回第一个控制台
    return consoles[0]["id"]


def send_command(token, username, cmd, wait=3):
    """向控制台发送命令并获取输出"""
    console_id = get_console_id(token, username)
    if not console_id:
        print("[ERROR] 无法获取控制台")
        return None
    # 发送命令
    api_call(token, username, "POST", f"consoles/{console_id}/send_input/",
             {"input": cmd + "\n"}, expect_json=False)
    # 等待执行
    time.sleep(wait)
    # 获取输出
    result = api_call(token, username, "GET", f"consoles/{console_id}/get_latest_output/")
    if result:
        # 清理 ANSI 转义码
        import re
        output = result.get("output", "")
        output = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', output)
        output = re.sub(r'\x1b\[\?[0-9]*[hl]', '', output)
        return output
    return None


def get_domain(username):
    return f"{username}.{DOMAIN_SUFFIX}"


def cmd_setup(args):
    """保存用户名和 token"""
    if len(args) < 2:
        print("用法: python pa_deploy.py setup <username> <token>")
        sys.exit(1)
    save_config(args[0], args[1])


def cmd_status(args):
    """查看应用状态"""
    token, username = load_config()
    domain = get_domain(username)
    print(f"=== PythonAnywhere 应用状态 ===")
    print(f"用户名: {username}")
    print(f"域名: https://{domain}")
    # Web 应用信息
    info = api_call(token, username, "GET", f"webapps/{domain}/")
    if info:
        print(f"Python 版本: {info.get('python_version')}")
        print(f"源代码目录: {info.get('source_directory')}")
        print(f"虚拟环境: {info.get('virtualenv_path') or '(无)'}")
        print(f"启用状态: {'运行中' if info.get('enabled') else '已停用'}")
        print(f"到期时间: {info.get('expiry')}")
        print(f"HTTPS 强制: {'是' if info.get('force_https') else '否'}")
    # CPU 使用
    cpu = api_call(token, username, "GET", "cpu/")
    if cpu:
        print(f"CPU 用量: {cpu.get('daily_cpu_total_usage_seconds', 0):.1f}s / {cpu.get('daily_cpu_limit_seconds', 0)}s")
    # 验证网站可访问
    try:
        req = urllib.request.Request(f"https://{domain}/api/questions?page=1&page_size=1")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"题库总数: {data.get('total', '?')} 题")
            print(f"网站状态: 正常 (HTTP {resp.status})")
    except Exception as e:
        print(f"网站状态: 异常 ({e})")


def cmd_update(args):
    """拉取最新代码并重载"""
    token, username = load_config()
    domain = get_domain(username)
    print("=== 更新应用 ===")
    # 1. Git pull
    print("[1/3] 拉取最新代码...")
    output = send_command(token, username, f"cd {BACKEND_DIR} && git pull", wait=5)
    if output:
        # 只显示最后几行
        lines = [l for l in output.split('\n') if l.strip() and '$' not in l]
        for line in lines[-5:]:
            print(f"  {line}")
    # 2. 安装依赖（如果有变更）
    print("[2/3] 检查依赖...")
    output = send_command(token, username, f"pip3.{PYTHON_VERSION} install --user -r {BACKEND_DIR}/requirements.txt", wait=10)
    if output and "Successfully installed" in output:
        print("  依赖已更新")
    else:
        print("  依赖无变更")
    # 3. 重载应用
    print("[3/3] 重载 Web 应用...")
    result = api_call(token, username, "POST", f"webapps/{domain}/reload/", expect_json=False)
    if result is not None:
        print("  [OK] 应用已重载")
    # 验证
    time.sleep(3)
    try:
        req = urllib.request.Request(f"https://{domain}/api/questions?page=1&page_size=1")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"\n[验证] 网站正常，题库 {data.get('total', '?')} 题")
            print(f"访问: https://{domain}")
    except Exception as e:
        print(f"\n[验证失败] {e}")


def cmd_deploy(args):
    """完整部署流程"""
    token, username = load_config()
    domain = get_domain(username)
    print("=== 完整部署 ===")
    print("此操作将: 克隆代码 → 安装依赖 → 初始化数据库 → 配置 WSGI → 重载")
    confirm = input("确认继续? (y/N): ")
    if confirm.lower() != 'y':
        print("已取消")
        return
    # 1. 克隆仓库
    print("[1/6] 克隆 GitHub 仓库...")
    output = send_command(token, username, f"rm -rf {PROJECT_DIR} && git clone {PROJECT_REPO} {PROJECT_DIR}", wait=15)
    print("  仓库已克隆")
    # 2. 安装依赖
    print(f"[2/6] 安装 Python {PYTHON_VERSION} 依赖...")
    output = send_command(token, username, f"pip3.{PYTHON_VERSION} install --user -r {BACKEND_DIR}/requirements.txt", wait=20)
    if output and "Successfully installed" in output:
        print("  依赖安装成功")
    # 3. 初始化数据库
    print("[3/6] 初始化题库数据库...")
    output = send_command(token, username, f"cd {BACKEND_DIR} && DATA_DIR={BACKEND_DIR} python3.{PYTHON_VERSION} render_init.py", wait=10)
    if output:
        import re
        match = re.search(r'(\d+)\s*题', output)
        if match:
            print(f"  数据库已初始化: {match.group(1)} 题")
    # 4. 配置 WSGI
    print("[4/6] 配置 WSGI 文件...")
    wsgi_content = f'''import os, sys
project_path = os.path.expanduser("{BACKEND_DIR}")
if project_path not in sys.path:
    sys.path.insert(0, project_path)
os.environ.setdefault("DATA_DIR", os.path.expanduser("{BACKEND_DIR}"))
from app import app as application
'''
    wsgi_remote_path = WSGI_PATH.format(username=username)
    # 用 API 上传 WSGI 文件
    import io
    import mimetypes
    boundary = "----pa_deploy_boundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="content"; filename="wsgi.py"\r\n'
        f"Content-Type: text/x-python\r\n\r\n"
        f"{wsgi_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    url = f"https://{HOST}/api/v0/user/{username}/files/path{wsgi_remote_path}"
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Token {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"  WSGI 文件已上传: {wsgi_remote_path}")
    except urllib.error.HTTPError as e:
        print(f"  [WARN] WSGI 上传失败: {e.code}")
    # 5. 更新源代码目录
    print("[5/6] 配置 Web 应用源目录...")
    api_call(token, username, "PATCH", f"webapps/{domain}/", {
        "source_directory": BACKEND_DIR,
        "python_version": PYTHON_VERSION,
    })
    print("  源目录已设置")
    # 6. 重载
    print("[6/6] 重载 Web 应用...")
    api_call(token, username, "POST", f"webapps/{domain}/reload/", expect_json=False)
    time.sleep(5)
    # 验证
    try:
        req = urllib.request.Request(f"https://{domain}/api/questions?page=1&page_size=1")
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"\n=== 部署成功 ===")
            print(f"访问: https://{domain}")
            print(f"题库: {data.get('total', '?')} 题")
    except Exception as e:
        print(f"\n[验证失败] {e}")
        print(f"请查看日志: python pa_deploy.py logs")


def cmd_reload(args):
    """仅重载应用"""
    token, username = load_config()
    domain = get_domain(username)
    print("=== 重载 Web 应用 ===")
    result = api_call(token, username, "POST", f"webapps/{domain}/reload/", expect_json=False)
    if result is not None:
        print("[OK] 应用已重载")
        print(f"访问: https://{domain}")
    else:
        print("[FAIL] 重载失败")


def cmd_logs(args):
    """查看错误日志"""
    token, username = load_config()
    domain = get_domain(username)
    log_file = f"{username}.{DOMAIN_SUFFIX}.error.log"
    print(f"=== 错误日志 (最后 30 行) ===")
    output = send_command(token, username, f"tail -30 /var/log/{log_file}", wait=3)
    if output:
        lines = output.split('\n')
        for line in lines:
            if line.strip() and '$' not in line and 'tail' not in line:
                print(line)


def cmd_console(args):
    """在远程控制台执行命令"""
    if not args:
        print("用法: python pa_deploy.py console <command>")
        sys.exit(1)
    token, username = load_config()
    cmd = " ".join(args)
    print(f"=== 执行: {cmd} ===")
    output = send_command(token, username, cmd, wait=5)
    if output:
        lines = output.split('\n')
        for line in lines:
            if line.strip() and '$' not in line:
                print(line)


def cmd_backup(args):
    """备份远程数据库到本地"""
    token, username = load_config()
    domain = get_domain(username)
    print("=== 备份数据库 ===")
    # 在远程创建备份
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    remote_backup = f"{BACKEND_DIR}/data/backup_{timestamp}.db"
    send_command(token, username, f"cp {BACKEND_DIR}/data/quiz.db {remote_backup}", wait=3)
    # 通过 API 下载
    url = f"https://{HOST}/api/v0/user/{username}/files/path{remote_backup}"
    req = urllib.request.Request(url, headers={"Authorization": f"Token {token}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            local_path = os.path.join("backups", f"quiz_{timestamp}.db")
            os.makedirs("backups", exist_ok=True)
            with open(local_path, "wb") as f:
                f.write(resp.read())
            print(f"[OK] 数据库已备份到本地: {local_path}")
    except Exception as e:
        print(f"[FAIL] 备份失败: {e}")


def cmd_restart(args):
    """强制重启"""
    token, username = load_config()
    domain = get_domain(username)
    print("=== 强制重启 ===")
    # 清理临时文件
    send_command(token, username, f"find {BACKEND_DIR}/__pycache__ -name '*.pyc' -delete 2>/dev/null", wait=2)
    send_command(token, username, f"rm -f {BACKEND_DIR}/data/quiz.db-wal {BACKEND_DIR}/data/quiz.db-shm 2>/dev/null", wait=2)
    # 重载
    result = api_call(token, username, "POST", f"webapps/{domain}/reload/", expect_json=False)
    if result is not None:
        print("[OK] 已强制重启")
        print(f"访问: https://{domain}")
    else:
        print("[FAIL] 重启失败")


COMMANDS = {
    "setup": cmd_setup,
    "status": cmd_status,
    "update": cmd_update,
    "deploy": cmd_deploy,
    "reload": cmd_reload,
    "logs": cmd_logs,
    "console": cmd_console,
    "backup": cmd_backup,
    "restart": cmd_restart,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__)
        print(f"可用命令: {', '.join(COMMANDS.keys())}")
        sys.exit(1)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    COMMANDS[cmd](args)


if __name__ == "__main__":
    main()
