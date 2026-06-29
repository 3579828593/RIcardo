# -*- coding: utf-8 -*-
"""Pytest 全局配置 — 在所有测试导入 app 之前设置环境变量"""
import os

# 测试环境使用固定 admin token
os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")
