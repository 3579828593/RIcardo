# -*- coding: utf-8 -*-
"""Pytest 全局配置 — 在所有测试导入 app 之前设置环境变量"""
import os
import tempfile
import shutil

# 测试环境使用固定 admin token
os.environ.setdefault("QUIZ_ADMIN_TOKEN", "test-admin-token")

import pytest


@pytest.fixture(autouse=True)
def _clear_auth_test_data():
    """每个测试前清空 rate_limits、users 和 session_user_map 表，避免累积。"""
    try:
        from app import db
        with db.connection() as conn:
            conn.execute("DELETE FROM rate_limits")
            conn.execute("DELETE FROM session_user_map")
            conn.execute("DELETE FROM users")
    except Exception:
        pass
    yield


@pytest.fixture
def db_path(tmp_path):
    """提供临时数据库路径，测试后自动清理"""
    return str(tmp_path / "test_quiz.db")


@pytest.fixture
def db(db_path):
    """提供干净的 QuizDatabase 实例，测试后自动关闭"""
    from database import QuizDatabase
    backup_dir = str(tmp_path / "backups") if False else os.path.dirname(db_path)
    instance = QuizDatabase(db_path, backup_dir)
    yield instance
    instance.close()
