# -*- coding: utf-8 -*-
"""期末冲刺刷题系统 — 全面自动化 API 测试

运行方式 (两种均可):
    cd backend
    python -m pytest tests/test_api.py -v
    python tests/test_api.py
"""
import json
import os
import re
import sys
import unittest

# 确保能 import 顶层 app 模块
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app import app


# ---------------------------------------------------------------------------
# ANSI 彩色输出
# ---------------------------------------------------------------------------
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


class TestQuizAPI(unittest.TestCase):
    """12 个 API 端点测试 + 3 个前端 HTML 内容检查"""

    def setUp(self):
        self.client = app.test_client()

    # =======================================================================
    # 1. GET / — 首页 HTML
    # =======================================================================
    def test_homepage(self):
        """验证首页返回 200，包含 Vue CDN、21th CSS 变量、底部导航等关键标记"""
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        html = resp.data.decode("utf-8")

        # Vue CDN
        self.assertIn("vue.global.prod.js", html)

        # 21th CSS 变量 (至少在亮色主题中定义)
        self.assertIn("--background:", html)
        self.assertIn("--card:", html)
        self.assertIn("--foreground:", html)

        # 底部导航
        self.assertIn("bottom-nav", html)
        self.assertIn("nav-tab", html)

        # 关键页面区域
        self.assertIn("filter-bar", html)
        self.assertIn("question-card", html)

    # =======================================================================
    # 2. GET /api/questions?page=1&page_size=5 — 分页查询
    # =======================================================================
    def test_questions_pagination(self):
        """验证分页参数 items / total / page"""
        resp = self.client.get("/api/questions?page=1&page_size=5")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertIn("page", data)
        self.assertIn("page_size", data)
        self.assertEqual(data["page"], 1)
        self.assertEqual(data["page_size"], 5)
        self.assertTrue(isinstance(data["items"], list))

    # =======================================================================
    # 3. GET /api/chapters — 全部课程章节
    # =======================================================================
    def test_chapters_all(self):
        """验证返回 dict，包含 weather 和 english"""
        resp = self.client.get("/api/chapters")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertTrue(isinstance(data, dict))
        self.assertIn("weather", data)
        self.assertIn("english", data)

    # =======================================================================
    # 4. GET /api/chapters?course=weather — 单课程章节
    # =======================================================================
    def test_chapters_by_course(self):
        """验证指定课程返回 sorted list"""
        resp = self.client.get("/api/chapters?course=weather")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertIn("course", data)
        self.assertEqual(data["course"], "weather")
        self.assertIn("chapters", data)
        chapters = data["chapters"]
        self.assertTrue(isinstance(chapters, list))
        # 验证已排序
        self.assertEqual(chapters, sorted(chapters))

    # =======================================================================
    # 5. GET /api/questions/random?limit=3 — 随机抽题
    # =======================================================================
    def test_random_questions(self):
        """验证返回恰好 3 题"""
        resp = self.client.get("/api/questions/random?limit=3")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 3)
        # 每题有 id / stem / type 等关键字段
        for q in data["items"]:
            self.assertIn("id", q)
            self.assertIn("stem", q)
            self.assertIn("type", q)

    # =======================================================================
    # 6. GET /api/stats — 学习统计
    # =======================================================================
    def test_stats(self):
        """验证 total_questions > 0, accuracy >= 0, type_distribution 存在"""
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertIn("total_questions", data)
        self.assertGreater(data["total_questions"], 0)
        self.assertIn("accuracy", data)
        self.assertGreaterEqual(data["accuracy"], 0)
        self.assertIn("type_distribution", data)

    def test_stats_answered_question_ids(self):
        """验证 /api/stats 返回 answered_question_ids 数组"""
        # 先答一道题
        resp = self.client.post("/api/submit",
            data=json.dumps({"question_id": 1, "answer": "test"}),
            content_type="application/json",
            headers={"X-Session-Id": "test_doneset_sync"})
        self.assertEqual(resp.status_code, 200)

        # 查询 stats
        resp = self.client.get("/api/stats",
            headers={"X-Session-Id": "test_doneset_sync"})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertIn("answered_question_ids", data)
        self.assertIsInstance(data["answered_question_ids"], list)
        self.assertIn(1, data["answered_question_ids"])
        self.assertEqual(data["answered_questions"], len(data["answered_question_ids"]))

    def test_stats_empty_session_has_empty_ids(self):
        """验证新会话 answered_question_ids 为空数组"""
        resp = self.client.get("/api/stats",
            headers={"X-Session-Id": "fresh_empty_session"})
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertIn("answered_question_ids", data)
        self.assertEqual(data["answered_question_ids"], [])
        self.assertEqual(data["answered_questions"], 0)

    # =======================================================================
    # 7. GET /api/mistakes?page=1&page_size=5 — 错题分页
    # =======================================================================
    def test_mistakes_pagination(self):
        """验证 items / total"""
        resp = self.client.get("/api/mistakes?page=1&page_size=5")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertTrue(isinstance(data["items"], list))

    # =======================================================================
    # 8. GET /api/favorites?page=1&page_size=5 — 收藏分页
    # =======================================================================
    def test_favorites_pagination(self):
        """验证 items / total"""
        resp = self.client.get("/api/favorites?page=1&page_size=5")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertIn("items", data)
        self.assertIn("total", data)
        self.assertTrue(isinstance(data["items"], list))

    # =======================================================================
    # 9. POST /api/submit — 提交正确答案
    # =======================================================================
    def test_submit_correct_answer(self):
        """获取一道单选题，提交正确答案，验证 correct=true"""
        # 先获取一道单选题
        resp = self.client.get("/api/questions?type=single&page=1&page_size=1")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())
        self.assertGreater(len(data["items"]), 0, "数据库中无单选题")

        q = data["items"][0]
        qid = q["id"]
        answer = q["answer"]
        # answer 是 list，取第一个元素
        correct_choice = answer[0] if answer else None
        self.assertIsNotNone(correct_choice, "题目无正确答案")

        # 提交正确答案
        resp = self.client.post(
            "/api/submit",
            data=json.dumps({"question_id": qid, "answer": correct_choice}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        result = json.loads(resp.data.decode())

        self.assertIn("correct", result)
        self.assertTrue(result["correct"])
        self.assertIn("correct_answer", result)

    # =======================================================================
    # 10. POST /api/favorites/<qid> + GET /api/favorites — 收藏
    # =======================================================================
    def test_toggle_favorite(self):
        """收藏后验证 total 增加"""
        # 先获取一道题
        resp = self.client.get("/api/questions?page=1&page_size=1")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())
        self.assertGreater(len(data["items"]), 0)

        qid = data["items"][0]["id"]

        # 获取收藏前 total
        resp = self.client.get("/api/favorites")
        data = json.loads(resp.data.decode())
        total_before = data["total"]

        # 取消收藏 (确保初始未收藏)
        self.client.delete(f"/api/favorites/{qid}")

        # 再次确认 total
        resp = self.client.get("/api/favorites")
        data = json.loads(resp.data.decode())
        total_before = data["total"]

        # 收藏
        resp = self.client.post(
            f"/api/favorites/{qid}",
            data=json.dumps({}),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        fav_data = json.loads(resp.data.decode())
        self.assertIn("favorited", fav_data)

        # 验证 total 增加
        resp = self.client.get("/api/favorites")
        data = json.loads(resp.data.decode())
        total_after = data["total"]
        self.assertEqual(total_after, total_before + 1)

        # 清理：取消收藏
        self.client.delete(f"/api/favorites/{qid}")

    # =======================================================================
    # 11. GET /api/questions?keyword=%25 — LIKE 注入测试
    # =======================================================================
    def test_like_injection(self):
        """验证 % 通配符被正确转义，返回 total=0"""
        resp = self.client.get("/api/questions?keyword=%25")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertEqual(data["total"], 0)
        self.assertEqual(len(data["items"]), 0)

    # =======================================================================
    # 12. GET /api/questions/1 — 单题详情
    # =======================================================================
    def test_single_question(self):
        """验证 id=1, 有 stem"""
        resp = self.client.get("/api/questions/1")
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.data.decode())

        self.assertEqual(data["id"], 1)
        self.assertIn("stem", data)
        self.assertTrue(len(data["stem"]) > 0)

    # =======================================================================
    # 前端 HTML 内容检查
    # =======================================================================

    def _get_homepage_html(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        return resp.data.decode("utf-8")

    # 13. CSS 变量 — 亮色模式
    def test_light_theme_background(self):
        """CSS 变量 --background: #f0f0f0 存在（现代像素风亮色）"""
        html = self._get_homepage_html()
        self.assertIn("--background: #f0f0f0", html)

    # 14. CSS 变量 — 暗色模式
    def test_dark_theme_background(self):
        """CSS 变量 --background: #0a0a1a 存在（现代像素风暗色）"""
        html = self._get_homepage_html()
        self.assertIn("--background: #0a0a1a", html)

    # 15. 所有 var(--xxx) 引用的变量都在 :root 中有定义
    def test_css_variables_defined(self):
        """提取 HTML 中所有 var(--xxx) 引用，与 :root 定义交叉比对"""
        html = self._get_homepage_html()

        def extract_block(html_text, selector):
            """提取 CSS 选择器对应 { ... } 块的完整内容（支持嵌套括号）"""
            pattern = re.escape(selector) + r"\s*\{"
            m = re.search(pattern, html_text)
            if not m:
                return None
            start = m.end()
            depth = 1
            i = start
            while i < len(html_text) and depth > 0:
                if html_text[i] == "{":
                    depth += 1
                elif html_text[i] == "}":
                    depth -= 1
                i += 1
            return html_text[start : i - 1]

        # 1) 提取 :root { ... } 中的所有自定义属性
        root_block = extract_block(html, ":root")
        self.assertIsNotNone(root_block, ":root 块未找到")
        defined_vars = set(re.findall(r"(--[a-zA-Z][\w-]*)\s*:", root_block))

        # 2) 提取 CSS 中所有 var(--xxx) 引用
        #    匹配 var(--xxx)、var(--xxx, ...) 等模式
        referenced = set(re.findall(r"var\(\s*(--[a-zA-Z][\w-]*)\s*[,\)]", html))

        # 3) 暗色主题 [data-theme="dark"] 中也定义了变量
        dark_block = extract_block(html, '[data-theme="dark"]')
        dark_vars = set()
        if dark_block:
            dark_vars = set(re.findall(r"(--[a-zA-Z][\w-]*)\s*:", dark_block))

        all_defined = defined_vars | dark_vars
        undefined = referenced - all_defined

        if undefined:
            self.fail(
                f"以下 CSS 变量在 var() 中引用但未在 :root 或 [data-theme=dark] 中定义: "
                f"{', '.join(sorted(undefined))}"
            )


# ---------------------------------------------------------------------------
# 自定义运行器：彩色 PASS / FAIL 输出
# ---------------------------------------------------------------------------
class _ColorTestResult(unittest.TextTestResult):
    """使用 ANSI 转义码输出彩色结果"""

    def addSuccess(self, test):
        super().addSuccess(test)
        desc = self._describe(test)
        sys.stdout.write(f"  {GREEN}PASS{RESET}  {desc}\n")
        sys.stdout.flush()

    def addFailure(self, test, err):
        super().addFailure(test, err)
        desc = self._describe(test)
        sys.stdout.write(f"  {RED}FAIL{RESET}  {desc}\n")
        sys.stdout.flush()

    def addError(self, test, err):
        super().addError(test, err)
        desc = self._describe(test)
        sys.stdout.write(f"  {RED}ERROR{RESET} {desc}\n")
        sys.stdout.flush()

    @staticmethod
    def _describe(test):
        return test._testMethodName.replace("test_", "")

    def printSummary(self):
        total = self.testsRun
        passed = total - len(self.failures) - len(self.errors)
        if self.failures or self.errors:
            sys.stdout.write(
                f"\n{BOLD}{RED}{passed}/{total} passed{RESET} "
                f"({len(self.failures)} failed, {len(self.errors)} errors)\n"
            )
        else:
            sys.stdout.write(
                f"\n{BOLD}{GREEN}{passed}/{total} passed{RESET} — all green\n"
            )
        sys.stdout.flush()


def run_tests():
    """直接运行: python tests/test_api.py"""
    suite = unittest.TestLoader().loadTestsFromTestCase(TestQuizAPI)
    runner = unittest.TextTestRunner(verbosity=0, resultclass=_ColorTestResult)
    result = runner.run(suite)

    # 使用自定义汇总
    total = result.testsRun
    passed = total - len(result.failures) - len(result.errors)
    if result.failures or result.errors:
        sys.stdout.write(
            f"\n{BOLD}{RED}{passed}/{total} passed{RESET} "
            f"({len(result.failures)} failed, {len(result.errors)} errors)\n"
        )
    else:
        sys.stdout.write(
            f"\n{BOLD}{GREEN}{passed}/{total} passed{RESET} — all green\n"
        )
    sys.stdout.flush()

    # pytest 兼容：若有失败返回非零退出码
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    print(f"\n{CYAN}{BOLD}期末冲刺刷题系统 — API 测试{RESET}\n")
    run_tests()
