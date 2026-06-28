#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render 部署初始化脚本：检查数据库是否存在，不存在则从 quiz-data.js 导入"""
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(BASE_DIR))

from config import load_config
from database import QuizDatabase


def ensure_database():
    cfg = load_config()
    db_path = cfg["storage"]["db_path"]
    db = QuizDatabase(db_path, cfg["storage"]["backup_dir"])
    stats = db.get_stats()
    if stats["total_questions"] == 0:
        print("[init] 数据库为空，尝试从 quiz-data.js 导入题库...")
        js_path = BASE_DIR.parent / "quiz-data.js"
        if js_path.exists():
            sys.path.insert(0, str(BASE_DIR))
            import data_migration
            data_migration.import_js(str(js_path), db_path)
            print("[init] 题库导入完成")
        else:
            print(f"[init] 警告: quiz-data.js 不存在于 {js_path}")
            print("[init] 数据库将为空，请通过 API 或管理界面导入题目")
    else:
        print(f"[init] 数据库已有 {stats['total_questions']} 题，跳过导入")


if __name__ == "__main__":
    ensure_database()
