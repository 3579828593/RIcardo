# -*- coding: utf-8 -*-
"""数据库层单元测试 — 使用独立临时数据库"""
import json


class TestQuizDatabase:
    def test_init_db_creates_tables(self, db):
        with db.connection() as conn:
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
            table_names = [t[0] for t in tables]
            assert 'questions' in table_names
            assert 'question_banks' in table_names
            assert 'users' in table_names
            assert 'mistakes' in table_names
            assert 'favorites' in table_names

    def test_create_and_get_question(self, db):
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '测试题干', 'options': {'A': '选项A', 'B': '选项B'},
             'answer': ['A'], 'explanation': '解析', 'knowledge': '知识点'},
            bank_id=1
        )
        assert qid > 0
        q = db.get_question(qid)
        assert q['stem'] == '测试题干'
        assert q['course'] == 'weather'

    def test_search_questions(self, db):
        db.add_question(
            {'course': 'english', 'chapter': 2, 'type': 'single',
             'stem': '搜索测试题', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['A']},
            bank_id=1
        )
        result = db.search_questions(course='english', page=1, page_size=10)
        assert result['total'] >= 1
        assert result['items'][0]['stem'] == '搜索测试题'

    def test_record_answer_and_stats(self, db):
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '答题测试', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['A']},
            bank_id=1
        )
        db.record_answer(qid, 'A', True, session_id='test-session')
        stats = db.get_stats(session_id='test-session')
        assert stats['answered_questions'] >= 1
        assert stats['correct_answers'] >= 1

    def test_mistake_tracking(self, db):
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '错题测试', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['B']},
            bank_id=1
        )
        db.record_answer(qid, 'A', False, session_id='test-session')
        mistakes = db.get_mistakes(session_id='test-session')
        assert mistakes['total'] >= 1
        assert mistakes['items'][0]['id'] == qid

    def test_favorite_toggle(self, db):
        qid = db.add_question(
            {'course': 'weather', 'chapter': 1, 'type': 'single',
             'stem': '收藏测试', 'options': {'A': 'A', 'B': 'B'},
             'answer': ['A']},
            bank_id=1
        )
        added = db.toggle_favorite(qid, tag=None, session_id='test-session')
        assert added is True
        removed = db.remove_favorite(qid, session_id='test-session')
        assert removed is True
