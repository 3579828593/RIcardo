#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PythonAnywhere 智能部署脚本

用法:
  python pa_smart_deploy.py              # 自动检测变更并部署
  python pa_smart_deploy.py file1.py f2  # 部署指定文件
  python pa_smart_deploy.py --all        # 全量部署所有关键文件
  python pa_smart_deploy.py --reload-only # 仅重载
  python pa_smart_deploy.py --status     # 查看状态
"""
import os
import sys
import json
import time
import subprocess
import urllib.request
import urllib.error

# ============================================================
# 配置
# ============================================================
HOME = os.path.expanduser("~")
TOKEN_FILE = os.path.join(HOME, ".pa_token")
USERNAME_FILE = os.path.join(HOME, ".pa_username")
HOST = "www.pythonanywhere.com"

LOCAL_BASE = r"d:\期末冲刺刷题系统"
REMOTE_BASE = "/home/{username}/RIcardo"

# 关键文件清单（用于 --all 和验证）
ALL_KEY_FILES = [
    "backend/database.py",
    "backend/auth.py",
    "backend/permissions.py",
    "backend/app.py",
    "backend/csv_importer.py",
    "backend/lite.py",
    "backend/config.py",
    "backend/templates/index.html",
    "backend/static/js/app.js",
    "backend/static/sw.js",
    "backend/requirements.txt",
]

# 可部署的文件扩展名
DEPLOYABLE_EXTS = {".py", ".html", ".js", ".css", ".txt", ".json", ".yaml", ".yml"}

# 不需要部署的路径
SKIP_PATTERNS = ["tests/", "test_", "__pycache__", ".superpowers/", "docs/", "memory-bank/", ".git/"]


def load_config():
    """加载 token 和 username"""
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


def get_domain(username):
    return f"{username}.pythonanywhere.com"


def upload_file(local_path, remote_path, token, username):
    """通过 API 上传单个文件"""
    if not os.path.exists(local_path):
        return False, f"本地文件不存在: {local_path}"

    with open(local_path, "rb") as f:
        content = f.read()

    boundary = "----pa_deploy_boundary"
    filename = os.path.basename(local_path)
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="content"; filename="{filename}"\r\n'
        f"Content-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")

    url = f"https://{HOST}/api/v0/user/{username}/files/path{remote_path}"
    req = urllib.request.Request(url, data=body, method="POST", headers={
        "Authorization": f"Token {token}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True, resp.status
    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8")
        return False, f"{e.code}: {error_body[:200]}"
    except Exception as e:
        return False, str(e)


def reload_webapp(token, username):
    """重载 Web 应用"""
    domain = get_domain(username)
    url = f"https://{HOST}/api/v0/user/{username}/webapps/{domain}/reload/"
    req = urllib.request.Request(url, data=b"", method="POST", headers={
        "Authorization": f"Token {token}",
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return True
    except Exception as e:
        print(f"  [ERROR] 重载失败: {e}")
        return False


def verify_site(username):
    """验证网站可访问性"""
    domain = get_domain(username)
    results = {}

    # 1. 题目 API
    try:
        url = f"https://{domain}/api/questions?page=1&per_page=1"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            results["questions"] = f"OK (total={data.get('total', '?')})"
    except Exception as e:
        results["questions"] = f"FAIL ({e})"

    # 2. 认证 API
    try:
        url = f"https://{domain}/api/auth/me"
        urllib.request.urlopen(url, timeout=15)
        results["auth"] = "FAIL (应返回401)"
    except urllib.error.HTTPError as e:
        if e.code == 401:
            results["auth"] = "OK (401)"
        else:
            results["auth"] = f"FAIL ({e.code})"
    except Exception as e:
        results["auth"] = f"FAIL ({e})"

    # 3. 题库 API
    try:
        url = f"https://{domain}/api/banks?scope=official"
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
            banks = data.get("banks", [])
            results["banks"] = f"OK ({len(banks)} 个)"
    except Exception as e:
        results["banks"] = f"FAIL ({e})"

    return results


def detect_changed_files():
    """通过 git diff 检测变更文件"""
    os.chdir(LOCAL_BASE)
    changed = set()

    # 检测已提交的变更（HEAD~1..HEAD）
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True, text=True, encoding="utf-8"
        )
        if result.stdout:
            changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    except Exception:
        pass

    # 检测未提交的变更
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only"],
            capture_output=True, text=True, encoding="utf-8"
        )
        if result.stdout:
            changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    except Exception:
        pass

    # 检测暂存区变更
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only"],
            capture_output=True, text=True, encoding="utf-8"
        )
        if result.stdout:
            changed.update(line.strip() for line in result.stdout.splitlines() if line.strip())
    except Exception:
        pass

    return changed


def filter_deployable(files):
    """过滤出可部署的文件"""
    deployable = []
    for f in files:
        # 跳过测试、文档等
        if any(skip in f for skip in SKIP_PATTERNS):
            continue
        # 检查扩展名
        ext = os.path.splitext(f)[1].lower()
        if ext in DEPLOYABLE_EXTS:
            deployable.append(f)
    return sorted(deployable)


def classify_files(files):
    """将文件分类，决定部署策略"""
    categories = {
        "python": [],      # 需要清 .pyc 缓存
        "static": [],      # 静态文件
        "template": [],    # 模板
        "config": [],      # 配置文件
        "other": [],
    }
    for f in files:
        if f.endswith(".py"):
            categories["python"].append(f)
        elif f.startswith("backend/static/"):
            categories["static"].append(f)
        elif f.startswith("backend/templates/"):
            categories["template"].append(f)
        elif f.endswith("requirements.txt"):
            categories["config"].append(f)
        else:
            categories["other"].append(f)
    return categories


def main():
    token, username = load_config()
    domain = get_domain(username)
    remote_base = REMOTE_BASE.format(username=username)

    print("=" * 60)
    print("  PythonAnywhere 智能部署")
    print(f"  用户: {username}")
    print(f"  域名: https://{domain}")
    print("=" * 60)

    # 解析命令行参数
    args = sys.argv[1:]

    if "--status" in args:
        print("\n[状态检查]")
        results = verify_site(username)
        for name, status in results.items():
            print(f"  {name}: {status}")
        return

    if "--reload-only" in args:
        print("\n[仅重载]")
        if reload_webapp(token, username):
            print("  [OK] 应用已重载")
            time.sleep(3)
            results = verify_site(username)
            for name, status in results.items():
                print(f"  {name}: {status}")
        return

    # 确定要部署的文件
    if "--all" in args:
        files_to_deploy = ALL_KEY_FILES[:]
        print(f"\n[全量部署] {len(files_to_deploy)} 个关键文件")
    elif args:
        files_to_deploy = args
        print(f"\n[指定文件] {len(files_to_deploy)} 个文件")
    else:
        # 自动检测变更
        changed = detect_changed_files()
        files_to_deploy = filter_deployable(changed)
        if not files_to_deploy:
            print("\n[自动检测] 未检测到可部署的变更文件")
            print("  使用 --all 全量部署，或 --reload-only 仅重载")
            return
        print(f"\n[自动检测] 发现 {len(files_to_deploy)} 个变更文件:")
        for f in files_to_deploy:
            print(f"  - {f}")

    # 分类文件
    categories = classify_files(files_to_deploy)
    has_python = len(categories["python"]) > 0
    has_static = len(categories["static"]) > 0
    has_template = len(categories["template"]) > 0
    has_config = len(categories["config"]) > 0

    # 上传文件
    print(f"\n[上传] 开始上传 {len(files_to_deploy)} 个文件...")
    success_count = 0
    fail_count = 0

    for i, rel_path in enumerate(files_to_deploy, 1):
        local_path = os.path.join(LOCAL_BASE, rel_path.replace("/", os.sep))
        remote_path = f"{remote_base}/{rel_path}"
        ok, result = upload_file(local_path, remote_path, token, username)
        size = os.path.getsize(local_path) if os.path.exists(local_path) else 0
        if ok:
            print(f"  [{i}/{len(files_to_deploy)}] OK ({size:,}B) {rel_path}")
            success_count += 1
        else:
            print(f"  [{i}/{len(files_to_deploy)}] FAIL {rel_path} — {result}")
            fail_count += 1

    print(f"\n[上传完成] {success_count} 成功, {fail_count} 失败")

    if success_count == 0:
        print("[ERROR] 没有文件上传成功，终止部署")
        return

    # 重载应用
    print("\n[重载] 正在重载 Web 应用...")
    if not reload_webapp(token, username):
        print("[FAIL] 重载失败，请查看日志")
        return
    print("  [OK] 应用已重载")

    # 验证
    print("\n[验证] 等待 5 秒后验证...")
    time.sleep(5)
    results = verify_site(username)
    all_ok = all("OK" in v for v in results.values())

    for name, status in results.items():
        print(f"  {name}: {status}")

    print(f"\n{'=' * 60}")
    if all_ok:
        print("  部署成功!")
    else:
        print("  部署完成，但部分验证失败")
        print("  建议查看日志: python scripts/pa_deploy.py logs")
    print(f"  访问: https://{domain}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
