# -*- coding: utf-8 -*-
"""身份模型统一测试 — TDD: 先写测试，再实现

测试目标:
1. 匿名用户自动创建（首次访问时）
2. session_id → user_id 映射持久化
3. 同一 session_id 复用匿名用户
4. 匿名答题/错题/收藏按 user_id 查询
5. 登录时匿名数据合并到正式用户
6. 合并后无重复记录
7. 统计查询统一为 user_id
8. 重置进度按 user_id
"""
import pytest


class TestAnonymousUserCreation:
    """测试匿名用户自动创建"""

    def test_create_anonymous_user(self, db):
        """首次访问时创建匿名用户记录"""
        uid = db.create_anonymous_user('test-session-001')
        assert uid is not None
        assert uid > 0

        user = db.get_user_by_id(uid)
        assert user is not None
        assert user['role'] == 'anonymous'

    def test_create_anonymous_user_idempotent(self, db):
        """同一 session_id 不会创建重复匿名用户"""
        uid1 = db.create_anonymous_user('test-session-002')
        uid2 = db.create_anonymous_user('test-session-002')
        assert uid1 == uid2

    def test_get_user_id_by_session(self, db):
        """通过 session_id 查询映射的 user_id"""
        uid = db.create_anonymous_user('test-session-003')
        found = db.get_user_id_by_session('test-session-003')
        assert found == uid

    def test_get_user_id_by_session_not_found(self, db):
        """未映射的 session_id 返回 None"""
        found = db.get_user_id_by_session('nonexistent-session')
        assert found is None

    def test_different_sessions_different_users(self, db):
        """不同 session_id 创建不同匿名用户"""
        uid1 = db.create_anonymous_user('session-A')
        uid2 = db.create_anonymous_user('session-B')
        assert uid1 != uid2


class TestAnonymousDataByUserId:
    """测试匿名用户数据按 user_id 查询"""

    def test_anonymous_answer_recorded_with_user_id(self, db):
        """匿名答题记录写入 user_id"""
        uid = db.create_anonymous_user('anon-quiz-001')
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '匿名答题测试', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['A']},
            bank_id=1
        )
        db.record_answer(qid, 'A', True, session_id='anon-quiz-001', user_id=uid)
        stats = db.get_stats(user_id=uid)
        assert stats['answered_questions'] >= 1

    def test_anonymous_mistakes_by_user_id(self, db):
        """匿名错题本按 user_id 查询"""
        uid = db.create_anonymous_user('anon-mistake-001')
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '匿名错题测试', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['B']},
            bank_id=1
        )
        db.record_answer(qid, 'A', False, session_id='anon-mistake-001', user_id=uid)
        mistakes = db.get_mistakes(user_id=uid)
        assert mistakes['total'] >= 1

    def test_anonymous_favorites_by_user_id(self, db):
        """匿名收藏按 user_id 查询"""
        uid = db.create_anonymous_user('anon-fav-001')
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '匿名收藏测试', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['A']},
            bank_id=1
        )
        added = db.toggle_favorite(qid, tag=None, session_id='anon-fav-001', user_id=uid)
        assert added is True
        favs = db.get_favorites(user_id=uid)
        assert favs['total'] >= 1

    def test_reset_progress_by_user_id(self, db):
        """按 user_id 重置进度"""
        uid = db.create_anonymous_user('anon-reset-001')
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '重置测试', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['A']},
            bank_id=1
        )
        db.record_answer(qid, 'A', True, session_id='anon-reset-001', user_id=uid)
        db.reset_progress(user_id=uid)
        stats = db.get_stats(user_id=uid)
        assert stats['answered_questions'] == 0


class TestDataMergeOnLogin:
    """测试登录时匿名数据合并"""

    def test_merge_anonymous_to_user_answer_records(self, db):
        """登录后匿名答题记录合并到正式用户"""
        # 1. 创建匿名用户并答题
        anon_uid = db.create_anonymous_user('merge-test-001')
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '合并测试题', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['A']},
            bank_id=1
        )
        db.record_answer(qid, 'A', True, session_id='merge-test-001', user_id=anon_uid)

        # 2. 创建正式用户
        real_uid = db.create_user('merge_student_001', 'hash_placeholder', '合并学生')

        # 3. 合并
        db.merge_anonymous_to_user(anon_uid, real_uid)

        # 4. 验证数据已转移到正式用户
        stats = db.get_stats(user_id=real_uid)
        assert stats['answered_questions'] >= 1

    def test_merge_no_duplicate_mistakes(self, db):
        """合并后错题本无重复"""
        anon_uid = db.create_anonymous_user('merge-dup-001')
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '去重测试题', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['B']},
            bank_id=1
        )
        db.record_answer(qid, 'A', False, session_id='merge-dup-001', user_id=anon_uid)

        real_uid = db.create_user('merge_student_002', 'hash_placeholder', '去重学生')
        db.merge_anonymous_to_user(anon_uid, real_uid)

        mistakes = db.get_mistakes(user_id=real_uid)
        assert mistakes['total'] == 1  # 不应重复

    def test_merge_updates_session_map(self, db):
        """合并后 session_user_map 指向正式用户"""
        anon_uid = db.create_anonymous_user('merge-map-001')
        real_uid = db.create_user('merge_student_003', 'hash_placeholder', '映射学生')
        db.merge_anonymous_to_user(anon_uid, real_uid)

        mapped = db.get_user_id_by_session('merge-map-001')
        assert mapped == real_uid


class TestSessionUserMapTable:
    """测试 session_user_map 表"""

    def test_table_exists(self, db):
        """session_user_map 表已创建"""
        with db.connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='session_user_map'"
            ).fetchall()
            assert len(tables) == 1

    def test_users_table_supports_anonymous_role(self, db):
        """users 表 role 列支持 'anonymous' 值"""
        uid = db.create_anonymous_user('role-test-001')
        with db.connection() as conn:
            row = conn.execute(
                "SELECT role FROM users WHERE id = ?", (uid,)
            ).fetchone()
            assert row[0] == 'anonymous'
