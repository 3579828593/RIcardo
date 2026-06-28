# -*- coding: utf-8 -*-
"""前端 JS / HTML 关键逻辑的回归测试

通过静态分析 app.js 与 index.html 的内容，验证"页面切换就乱"系列修复点存在。
这些测试不是单元测试（前端无构建/无 JS 测试框架），而是"修复点存在性"断言——
一旦有人回退修复，测试立即变红。
"""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(ROOT, "static", "js", "app.js")
INDEX_HTML = os.path.join(ROOT, "templates", "index.html")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _extract_function(src, name):
    """提取 function name() { ... } 的函数体字符串（处理大括号配对）。"""
    m = re.search(r"function\s+" + re.escape(name) + r"\s*\([^)]*\)\s*\{", src)
    if not m:
        return ""
    start = m.end()  # 指向函数体第一个 {
    depth = 1
    i = start
    while i < len(src) and depth > 0:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[start:i]


def _extract_arrow(src, name):
    """提取 const name = (...)=>{...} 或 const name = ()=>{...} 的函数体。"""
    m = re.search(r"const\s+" + re.escape(name) + r"\s*=\s*(?:async\s*)?\([^)]*\)\s*=>\s*\{", src)
    if not m:
        return ""
    start = m.end()
    depth = 1
    i = start
    while i < len(src) and depth > 0:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[start:i]


def _extract_onmounted(src):
    """提取 onMounted(() => { ... }) 回调体。"""
    m = re.search(r"onMounted\s*\(\s*(?:async\s*)?\(\s*\)\s*=>\s*\{", src)
    if not m:
        return ""
    start = m.end()
    depth = 1
    i = start
    while i < len(src) and depth > 0:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[start:i]


class TestFrontendFixes(unittest.TestCase):
    js = ""
    html = ""

    @classmethod
    def setUpClass(cls):
        cls.js = _read(APP_JS)
        cls.html = _read(INDEX_HTML)

    # ============================================================
    # R1: 单题模式刷新后白屏（P0）
    # ============================================================
    def test_r1_save_state_includes_allquestions(self):
        """saveState 的 state 对象必须含 allQuestions 键，否则刷新后单题模式白屏"""
        body = _extract_function(self.js, "saveState")
        self.assertTrue(body, "应存在 saveState 函数")
        self.assertIn("allQuestions", body,
                      "saveState 的 state 对象必须持久化 allQuestions")

    def test_r1_load_state_restores_allquestions(self):
        """loadState 必须把持久化的 allQuestions 写回 allQuestions.value"""
        body = _extract_function(self.js, "loadState")
        self.assertTrue(body, "应存在 loadState 函数")
        self.assertIn("allQuestions", body,
                      "loadState 必须从持久化数据恢复 allQuestions")

    def test_r1_onmount_recovers_single_mode(self):
        """onMounted 必须在 singleMode 且 allQuestions 为空时重建会话，杜绝白屏"""
        body = _extract_onmounted(self.js)
        self.assertTrue(body, "应存在 onMounted 钩子")
        # 必须同时出现 singleMode、allQuestions.length、loadAllForSingleMode 的自愈逻辑
        self.assertIn("singleMode", body)
        self.assertIn("allQuestions", body)
        self.assertIn("loadAllForSingleMode", body,
                      "onMounted 应在 singleMode=true 且 allQuestions 为空时调用 loadAllForSingleMode 重建会话")

    # ============================================================
    # R2: 切 Tab 滚动位置丢失 + 行为不对称（P1）
    # ============================================================
    def test_r2_switchtab_saves_scroll(self):
        """switchTab 离开当前页前应保存滚动位置"""
        self.assertIn("scrollMemory", self.js,
                      "应有按 Tab 分隔的滚动记忆 (scrollMemory)")

    def test_r2_switchtab_restores_scroll(self):
        """switchTab 进入页时应恢复其滚动位置"""
        self.assertIn("scrollTo", self.js,
                      "switchTab 应在切 Tab 时恢复滚动位置")

    # ============================================================
    # R3: 加载态跨 Tab 串台（P1）
    # ============================================================
    def test_r3_favorites_empty_not_gated_by_global_loading(self):
        """收藏空状态不应被全局 loading 误隐藏"""
        self.assertNotIn("favorites.length === 0 && !loading", self.html,
                         "收藏空状态被全局 loading 门控会导致跨 Tab 串台")

    def test_r3_mistakes_empty_not_gated_by_global_loading(self):
        """错题空状态不应被全局 loading 误隐藏"""
        self.assertNotIn("mistakes.length === 0 && !loading", self.html,
                         "错题空状态被全局 loading 门控会导致跨 Tab 串台")

    def test_r3_tab_loading_isolation(self):
        """应存在按 Tab 的加载标记，实现加载态隔离"""
        self.assertTrue(
            "tabLoading" in self.js,
            "应引入 tabLoading 按 Tab 隔离加载态"
        )

    # ============================================================
    # R4: 双加载 + 筛选残留（P2）
    # ============================================================
    def test_r4_no_double_load_on_mode_switch(self):
        """列表刷题按钮不应触发双重加载"""
        self.assertNotIn("exitSingleMode(); switchMode('normal')", self.html,
                         "列表刷题按钮双重加载，应只保留单一加载入口")

    def test_r4_practice_mistakes_sets_normal_mode(self):
        """错题练习应进入 normal 模式，否则加载更多按钮消失"""
        self.assertIn("mode.value = 'normal'", self.js,
                      "practiceMistakes 应显式设置 mode='normal'")


if __name__ == "__main__":
    unittest.main(verbosity=2)
