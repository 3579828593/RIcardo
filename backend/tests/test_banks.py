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
