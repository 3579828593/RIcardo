# -*- coding: utf-8 -*-
"""测试题库 CRUD + 权限"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def _make_bank(owner_id=None, visibility='private', status='active'):
    """构造一个 bank dict（模拟 sqlite3.Row）"""
    return {
        'id': 1, 'owner_id': owner_id, 'name': '测试题库', 'course': 'test',
        'visibility': visibility, 'status': status, 'question_count': 0,
    }


def _make_user(user_id=None, role='student'):
    return {'id': user_id, 'role': role, 'nickname': 'test', 'student_id': 'test'}


def test_can_read_official_bank():
    """官方题库任何人可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=None, visibility='public')
    assert can_read_bank(None, bank) is True
    assert can_read_bank(_make_user(1), bank) is True


def test_can_read_private_bank_owner():
    """私有题库 owner 可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=5, visibility='private')
    assert can_read_bank(_make_user(5), bank) is True


def test_can_read_private_bank_non_owner():
    """私有题库非 owner 不可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=5, visibility='private')
    assert can_read_bank(_make_user(3), bank) is False
    assert can_read_bank(None, bank) is False


def test_can_read_public_bank():
    """公开题库任何人可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=5, visibility='public')
    assert can_read_bank(None, bank) is True
    assert can_read_bank(_make_user(3), bank) is True


def test_can_read_hidden_bank_admin_only():
    """hidden 状态仅 admin 可读"""
    from permissions import can_read_bank
    bank = _make_bank(owner_id=5, visibility='public', status='hidden')
    assert can_read_bank(None, bank) is False
    assert can_read_bank(_make_user(5), bank) is False
    assert can_read_bank(_make_user(1, 'admin'), bank) is True


def test_can_write_bank_owner():
    """owner 可写"""
    from permissions import can_write_bank
    bank = _make_bank(owner_id=5)
    assert can_write_bank(_make_user(5), bank) is True


def test_can_write_bank_non_owner():
    """非 owner 不可写"""
    from permissions import can_write_bank
    bank = _make_bank(owner_id=5)
    assert can_write_bank(_make_user(3), bank) is False
    assert can_write_bank(None, bank) is False


def test_can_write_official_bank_admin():
    """官方题库仅 admin 可写"""
    from permissions import can_write_bank
    bank = _make_bank(owner_id=None)
    assert can_write_bank(_make_user(1, 'admin'), bank) is True
    assert can_write_bank(_make_user(1, 'student'), bank) is False


def test_can_import_same_as_write():
    """can_import_to_bank 等同 can_write_bank"""
    from permissions import can_import_to_bank, can_write_bank
    bank = _make_bank(owner_id=5)
    user = _make_user(5)
    assert can_import_to_bank(user, bank) == can_write_bank(user, bank)


def test_create_bank():
    """创建题库"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("bank001", "hash", "Bank用户")
        bank_id = db.create_bank(owner_id=uid, name="我的题库", course="test")
        assert bank_id is not None and bank_id > 1
        bank = db.get_bank(bank_id)
        assert bank['name'] == '我的题库'
        assert bank['owner_id'] == uid
        assert bank['visibility'] == 'private'
        db.close()


def test_list_banks_by_owner():
    """列出用户自己的题库"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("list001", "hash", "List用户")
        db.create_bank(owner_id=uid, name="题库A", course="test")
        db.create_bank(owner_id=uid, name="题库B", course="english")
        banks = db.list_banks(owner_id=uid, scope="mine")
        assert len(banks) == 2
        db.close()


def test_list_official_banks():
    """列出官方题库"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        banks = db.list_banks(scope="official")
        assert len(banks) == 1
        assert banks[0]['name'] == '官方题库'
        db.close()


def test_delete_bank():
    """删除题库（软删除：status=deleted）"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("del001", "hash", "Del用户")
        bank_id = db.create_bank(owner_id=uid, name="待删除", course="test")
        ok = db.delete_bank(bank_id)
        assert ok is True
        bank = db.get_bank(bank_id)
        assert bank['status'] == 'deleted'
        db.close()


def test_update_bank_question_count():
    """更新题库题目计数"""
    from database import QuizDatabase
    import tempfile, os
    with tempfile.TemporaryDirectory() as tmpdir:
        db = QuizDatabase(os.path.join(tmpdir, "test.db"))
        uid = db.create_user("count001", "hash", "Count用户")
        bank_id = db.create_bank(owner_id=uid, name="计数题库", course="test")
        db.add_question({"course": "test", "chapter": 1, "type": "single",
                         "stem": "count_test_1", "options": {}, "answer": ["A"]}, bank_id=bank_id)
        db.update_bank_question_count(bank_id)
        bank = db.get_bank(bank_id)
        assert bank['question_count'] == 1
        db.close()
