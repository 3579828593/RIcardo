# -*- coding: utf-8 -*-
"""测试 questions 表迁移到 bank_id 架构"""
import pytest
import sys
from pathlib import Path

# 确保能导入 backend 模块
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_questions_table_has_bank_id():
    """questions 表必须有 bank_id 列，默认值为 1"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db.connection() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()]
        assert 'bank_id' in cols, f"questions 表缺少 bank_id 列，现有列: {cols}"
        db.close()


def test_questions_table_has_flagged():
    """questions 表必须有 flagged 列"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db.connection() as conn:
            cols = [r[1] for r in conn.execute("PRAGMA table_info(questions)").fetchall()]
        assert 'flagged' in cols, f"questions 表缺少 flagged 列，现有列: {cols}"
        db.close()


def test_question_banks_table_exists():
    """question_banks 表必须存在"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db.connection() as conn:
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
        assert 'question_banks' in tables, f"缺少 question_banks 表，现有表: {tables}"
        db.close()


def test_official_bank_auto_created():
    """迁移后自动创建官方题库 (id=1, owner_id=NULL)"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db.connection() as conn:
            row = conn.execute("SELECT * FROM question_banks WHERE id = 1").fetchone()
        assert row is not None, "官方题库未自动创建"
        assert row['owner_id'] is None, "官方题库 owner_id 应为 NULL"
        assert row['name'] == '官方题库'
        assert row['visibility'] == 'public'
        assert row['status'] == 'active'
        db.close()


def test_questions_unique_constraint_is_bank_stem():
    """UNIQUE 约束应为 UNIQUE(bank_id, stem) 而非 UNIQUE(course, stem)"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db.connection() as conn:
            schema = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='questions'"
            ).fetchone()
        assert 'UNIQUE(bank_id, stem)' in schema[0], f"UNIQUE 约束不正确: {schema[0]}"
        assert 'UNIQUE(course, stem)' not in schema[0], "旧约束 UNIQUE(course, stem) 仍存在"
        db.close()


def test_existing_questions_get_bank_id_1():
    """已有题目迁移后 bank_id 应为 1"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        # 插入测试题目（在迁移前模拟旧数据）
        db.add_question({"course": "test", "chapter": 1, "type": "single",
                         "stem": "测试题", "options": {"A": "a"}, "answer": ["A"]})
        # 重新初始化触发迁移
        db2 = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db2.connection() as conn:
            row = conn.execute("SELECT bank_id FROM questions WHERE stem = '测试题'").fetchone()
        assert row is not None and row['bank_id'] == 1, f"已有题目 bank_id 应为 1，实际: {row}"
        db.close()
        db2.close()


def test_question_count_dynamic():
    """官方题库 question_count 应动态计算，不硬编码"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        # 插入 3 道题
        for i in range(3):
            db.add_question({"course": "test", "chapter": 1, "type": "single",
                             "stem": f"测试题{i}", "options": {"A": "a"}, "answer": ["A"]})
        # 重新初始化（触发 question_count 更新）
        db2 = QuizDatabase(os.path.join(tmpdir, "test.db"))
        with db2.connection() as conn:
            row = conn.execute("SELECT question_count FROM question_banks WHERE id = 1").fetchone()
        assert row['question_count'] == 3, f"question_count 应为 3，实际: {row['question_count']}"
        db.close()
        db2.close()
