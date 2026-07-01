# -*- coding: utf-8 -*-
"""权限模型 — 集中封装题库读写权限"""


class Bank:
    """题库权限判断所需的信息（从 dict 构造）"""
    def __init__(self, data):
        self.owner_id = data.get('owner_id')
        self.visibility = data.get('visibility', 'private')
        self.status = data.get('status', 'active')


class User:
    """用户权限判断所需的信息"""
    def __init__(self, data):
        self.id = data.get('id') if data else None
        self.role = data.get('role', 'student') if data else 'student'


def _wrap_bank(bank):
    """将 dict/Row 统一包装为 Bank 对象"""
    if isinstance(bank, dict):
        return Bank(bank)
    return bank


def _wrap_user(user):
    """将 dict/Row/None 统一包装为 User 对象或 None"""
    if user is None:
        return None
    if isinstance(user, dict):
        return User(user)
    return user


def can_read_bank(user, bank) -> bool:
    """是否能查看题库内容"""
    b = _wrap_bank(bank)
    u = _wrap_user(user)

    if b.status in ('hidden', 'deleted'):
        return u is not None and u.role == 'admin'
    if b.owner_id is None:
        return True  # 官方题库
    if b.visibility == 'public':
        return True
    if u and u.role == 'admin':
        return True
    if u and b.owner_id == u.id:
        return True
    return False


def can_write_bank(user, bank) -> bool:
    """是否能编辑/删除题库"""
    if not user:
        return False
    b = _wrap_bank(bank)
    u = _wrap_user(user)

    if b.owner_id is None:
        return u.role == 'admin'  # 官方题库仅 admin
    return u.role == 'admin' or b.owner_id == u.id


def can_import_to_bank(user, bank) -> bool:
    """是否能导入题目"""
    return can_write_bank(user, bank)
