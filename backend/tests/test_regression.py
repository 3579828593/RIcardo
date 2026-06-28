# -*- coding: utf-8 -*-
"""刷题系统回归测试：先复现关键 Bug，再修复。"""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, ROOT)

import app as app_module
import data_migration
from database import QuizDatabase


class ScoringRegressionTest(unittest.TestCase):
    def test_multiple_choice_order_does_not_affect_scoring(self):
        self.assertTrue(app_module._check_answer("multiple", ["D", "B", "A", "C"], ["A", "B", "C", "D"]))

    def test_true_false_accepts_common_false_aliases(self):
        for alias in ["B", "错", "错误", "false", "False", "0"]:
            with self.subTest(alias=alias):
                self.assertTrue(app_module._check_answer("true_false", alias, ["错"]))

    def test_true_false_rejects_wrong_alias(self):
        self.assertFalse(app_module._check_answer("true_false", "A", ["错"]))


class ApiRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.tmp.name, "quiz.db")
        backup_dir = os.path.join(self.tmp.name, "backups")
        self.db = QuizDatabase(db_path, backup_dir)
        self.db.add_question({
            "id": 1,
            "course": "test",
            "chapter": 1,
            "type": "single",
            "stem": "测试题",
            "options": {"A": "对", "B": "错"},
            "answer": ["A"],
            "explanation": "测试解析",
            "knowledge": "测试知识点",
        })
        self.old_db = app_module.db
        app_module.db = self.db
        app_module.app.config["TESTING"] = True
        self.client = app_module.app.test_client()

    def tearDown(self):
        app_module.db = self.old_db
        self.db.close()
        self.tmp.cleanup()

    def test_questions_api_uses_new_schema_without_legacy_wrapper(self):
        resp = self.client.get("/api/questions?page_size=1")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertNotIn("code", data)
        self.assertNotIn("msg", data)

    def test_questions_api_rejects_negative_pagination_limits(self):
        for query in ["page=-1&page_size=1", "page=1&page_size=-1"]:
            with self.subTest(query=query):
                resp = self.client.get(f"/api/questions?{query}")
                self.assertEqual(resp.status_code, 400)

    def test_security_headers_are_set_on_responses(self):
        resp = self.client.get("/api/questions?page_size=1")
        self.assertEqual(resp.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(resp.headers.get("X-Frame-Options"), "SAMEORIGIN")
        self.assertEqual(resp.headers.get("Referrer-Policy"), "strict-origin-when-cross-origin")

    def test_index_page_renders_vue_template_without_jinja_conflict(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.get_data(as_text=True)
        self.assertIn("期末冲刺刷题系统", html)
        # Vue mustache 语法应保留（未被 Jinja 解析）
        self.assertIn("{{ q.stem }}", html)

    def test_export_json_supports_filename_without_parent_directory(self):
        cwd = os.getcwd()
        os.chdir(self.tmp.name)
        try:
            data_migration.export_json(self.db.db_path, "questions.json")
            self.assertTrue(os.path.exists(os.path.join(self.tmp.name, "questions.json")))
        finally:
            os.chdir(cwd)

    def test_delete_favorite_is_idempotent_and_does_not_create_favorite(self):
        resp = self.client.delete("/api/favorites/1")
        self.assertEqual(resp.status_code, 200)
        data = self.db.get_favorites()
        self.assertEqual(data["total"], 0)

    def test_admin_write_requires_token(self):
        resp = self.client.delete("/api/admin/questions/1")
        self.assertEqual(resp.status_code, 401)


if __name__ == "__main__":
    unittest.main()
