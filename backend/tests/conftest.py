# -*- coding: utf-8 -*-
"""Pytest 全局配置 — 在所有测试导入 app 之前设置环境变量"""
import os

# 测试环境使用固定 admin token
os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")

import pytest


@pytest.fixture(autouse=True)
def _clear_auth_test_data():
    """每个测试前清空 rate_limits 和 users 表，避免限流累积和重复用户影响测试。"""
    try:
        from app import db
        with db.connection() as conn:
            conn.execute("DELETE FROM rate_limits")
            conn.execute("DELETE FROM users")
    except Exception:
        pass
    yield
