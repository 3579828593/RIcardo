#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PythonAnywhere WSGI 入口文件

PythonAnywhere 使用 WSGI 而非 gunicorn，
此文件将 Flask app 暴露为 `application` 变量。

部署时把此文件内容复制到 PythonAnywhere 的 /var/www/<用户名>_pythonanywhere_com_wsgi.py
"""
import os
import sys

# 项目路径（PythonAnywhere 上通常在 /home/<用户名>/RIcardo/backend）
project_path = os.path.expanduser("~/RIcardo/backend")
if project_path not in sys.path:
    sys.path.insert(0, project_path)

# 设置数据目录（PythonAnywhere 上用 home 目录存储数据）
os.environ.setdefault("DATA_DIR", os.path.expanduser("~/RIcardo/backend"))

# 从服务器文件读取 admin token（不在代码仓库中硬编码）
_token_file = os.path.expanduser("~/.pa_admin_token")
if os.path.exists(_token_file):
    with open(_token_file, "r") as f:
        os.environ.setdefault("QUIZ_ADMIN_TOKEN", f.read().strip())

from app import app as application  # noqa: E402,F401
