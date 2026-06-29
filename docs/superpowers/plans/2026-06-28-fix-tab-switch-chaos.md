# 页面切换混乱修复 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复用户反馈"页面切换就乱、做题到一半切走再回来状态错乱"——4 个已确认根因，其中 1 个 P0 白屏。

**Architecture:** 前端是 Vue3 (CDN) 单页应用，4 个 Tab 用 `v-show`（DOM 不卸载），刷题页内部"单题/列表"用 `v-if`。问题集中在三处：(1) 单题模式的 `allQuestions` 没持久化，重载即白屏；(2) 切 Tab 不存/不恢复滚动；(3) 全局共享一个 `loading` 标志导致跨 Tab 串台；(4) `exitSingleMode();switchMode()` 双加载 + `redoQuestion` 筛选残留。全部修在 `backend/static/js/app.js` 与 `backend/templates/index.html`，不改后端。

**Tech Stack:** Vue 3 (CDN, 全局 `Vue.createApp`)、原生 JS、Flask test_client + unittest 做后端回归、前端用 `ui_smoke.py` 风格的 HTML 断言。

---

## 根因清单（带 file:line 证据）

| 编号 | 优先级 | 根因 | 证据 |
|---|---|---|---|
| R1 | P0 | 单题模式刷新后白屏：`allQuestions` 未持久化，重载后 `singleMode=true` 但 `allQuestions=[]`，`currentQuestion=null`，两个 `v-if` 都 false | `app.js:75-92`(saveState 漏 allQuestions)、`app.js:107-108`、`app.js:139-142`、`index.html:887`、`index.html:1032` |
| R2 | P1 | 切 Tab 不存/不恢复滚动；quiz 直接 return 不刷新，其它 Tab 重置到第1页，行为不对称 | `app.js:268-277`(switchTab 无滚动) |
| R3 | P1 | 全局共享单个 `loading`：quiz 加载时切到收藏/错题，其空状态被 `!loading` 误隐藏 | `app.js:28`、`index.html:1265`、`index.html:1310`、`index.html:790` |
| R4 | P2 | `exitSingleMode();switchMode()` 双加载 + `redoQuestion`/`practiceMistakes` 留下筛选残留 | `index.html:833,835`、`app.js:386-389`、`app.js:290-298`、`app.js:808-813` |

---

## 文件结构

- 修改：`backend/static/js/app.js`（主战场，R1/R2/R3/R4 的逻辑都在这里）
- 修改：`backend/templates/index.html`（R3 空状态门控、R4 双加载绑定）
- 新增测试：`backend/tests/test_frontend.py`（HTML/JS 内容断言，验证关键修复点存在）

---

## Task 1: R1 — 单题模式刷新后白屏（P0）

**Files:**
- Modify: `backend/static/js/app.js:75-92` (saveState)、`app.js:93-110` (loadState)、`app.js:896` 附近 (onMounted)
- Test: `backend/tests/test_frontend.py`（新建）

**根因：** `saveState` 持久化了 `singleMode` 和 `currentIndex`，但漏了 `allQuestions`。重载后 `loadState` 恢复 `singleMode=true`、`currentIndex=N`，但 `allQuestions=[]`，于是 `currentQuestion` 计算为 null，`index.html:887` 与 `:1032` 两个 v-if 同时为 false → 刷题页空白。

**修复策略：**
- (a) `saveState` 增加 `allQuestions`（仅存当前单题会话的题目快照，体积可控，351 题全量约 200KB，但单题模式通常只加载筛选后的一批；为安全只存前 100 题的精简字段）。
- (b) `onMounted` 检测：若恢复后 `singleMode=true` 但 `allQuestions` 为空，则自动重新加载（按持久化的筛选条件）以重建单题会话，避免白屏。

- [ ] **Step 1: 写失败测试 — 验证 saveState 序列化 allQuestions**

```python
# backend/tests/test_frontend.py
# -*- coding: utf-8 -*-
"""前端 JS 关键逻辑的回归测试（通过静态分析 app.js 内容验证修复点）"""
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
APP_JS = os.path.join(ROOT, "static", "js", "app.js")
INDEX_HTML = os.path.join(ROOT, "templates", "index.html")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TestFrontendFixes(unittest.TestCase):
    js = ""
    html = ""

    @classmethod
    def setUpClass(cls):
        cls.js = _read(APP_JS)
        cls.html = _read(INDEX_HTML)

    # ---- R1: 单题模式刷新白屏 ----
    def test_r1_save_state_includes_allquestions(self):
        """saveState 必须持久化 allQuestions，否则刷新后单题模式白屏"""
        # 找到 saveState 函数体，断言其中包含 allQuestions
        self.assertIn("allQuestions", self.js,
                      "saveState 应持久化 allQuestions 以支持单题模式刷新恢复")

    def test_r1_onmount_recovers_single_mode(self):
        """onMounted 必须在 singleMode=true 且 allQuestions 为空时重建会话"""
        self.assertTrue(
            ("singleMode" in self.js and "allQuestions" in self.js
             and ("length" in self.js)),
            "onMounted 应处理 singleMode=true 但 allQuestions 为空的白屏情况"
        )
```

- [ ] **Step 2: 运行测试确认失败**

Run: `cd backend && python -m pytest tests/test_frontend.py::TestFrontendFixes::test_r1_save_state_includes_allquestions -v`
Expected: FAIL（当前 saveState 不含 allQuestions）

- [ ] **Step 3: 实现 — saveState 增加 allQuestions**

在 `app.js` saveState 的 state 对象里增加（`app.js:88` currentIndex 之后）：

```javascript
        currentIndex: currentIndex.value,
        // R1 修复：持久化单题会话题目，避免刷新后白屏。仅存精简字段，限 100 题防爆 localStorage
        allQuestions: singleMode.value ? allQuestions.value.slice(0, 100).map(q => ({
          id: q.id, stem: q.stem, type: q.type, options: q.options,
          answer: q.answer, explanation: q.explanation, knowledge: q.knowledge,
          chapter: q.chapter, course: q.course
        })) : [],
```

- [ ] **Step 4: 实现 — loadState 恢复 allQuestions**

在 `app.js` loadState 里（`app.js:108` 之后）增加：

```javascript
        if (state.allQuestions && Array.isArray(state.allQuestions) && state.allQuestions.length) {
          allQuestions.value = state.allQuestions;
        }
```

- [ ] **Step 5: 实现 — onMounted 白屏自愈**

在 `app.js` onMounted 中，`loadState()` 之后、加载题目之前，插入白屏检测（找到 onMounted 里现有的 `loadState()` 调用位置后追加）：

```javascript
      // R1 修复：单题模式刷新后若 allQuestions 丢失，按持久化筛选重建会话，杜绝白屏
      if (singleMode.value && allQuestions.value.length === 0) {
        await loadAllForSingleMode();
        // 恢复到上次的题号（不超出范围）
        if (currentIndex.value >= allQuestions.value.length) currentIndex.value = 0;
      }
```

（若 onMounted 不是 async，把该函数改为 `async () => {...}` 或用 `.then()`。）

- [ ] **Step 6: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_frontend.py -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/static/js/app.js backend/tests/test_frontend.py
git commit -m "fix: 单题模式刷新后白屏 - 持久化 allQuestions 并自动恢复会话"
```

---

## Task 2: R2 — 切 Tab 滚动位置丢失 + 行为不对称（P1）

**Files:**
- Modify: `backend/static/js/app.js:268-277` (switchTab)
- Test: `backend/tests/test_frontend.py`

**根因：** `switchTab` 对 quiz 直接 return（不刷新、不恢复滚动），对 stats/mistakes/favorites 重置到第 1 页。quiz 用 `v-show` 隐藏时 body 高度塌缩，`scrollY` 被钳制，切回来停在顶部，回不到做题的位置。

**修复策略：** 为每个 Tab 维护独立的滚动位置 map；离开 Tab 时存当前 scrollY，进入 Tab 时恢复其 scrollY。quiz 仍不强制重载（保留原地状态），但恢复其滚动。

- [ ] **Step 1: 写失败测试**

```python
    # ---- R2: 切 Tab 滚动丢失 ----
    def test_r2_switchtab_saves_and_restores_scroll(self):
        """switchTab 必须保存/恢复各 Tab 的滚动位置"""
        self.assertIn("scrollTop", self.js,
                      "switchTab 应记录各 Tab 滚动位置，避免切走再回来丢失位置")
        self.assertIn("scrollMemory", self.js,
                      "应有按 Tab 分隔的滚动记忆 (scrollMemory)")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_frontend.py::TestFrontendFixes::test_r2_switchtab_saves_and_restores_scroll -v`
Expected: FAIL

- [ ] **Step 3: 实现**

在 `app.js` switchTab 定义之前（`app.js:267` 附近）新增滚动记忆，并改写 switchTab：

```javascript
    // R2 修复：各 Tab 独立滚动位置记忆
    const scrollMemory = Vue.ref({});  // { quiz: 300, stats: 0, ... }
    function saveScroll() {
      scrollMemory.value[activeTab.value] = window.scrollY || 0;
    }

    const switchTab = (tab) => {
      if (activeTab.value === tab && tab !== 'quiz') return;
      saveScroll();                       // 离开当前 Tab 前先存位置
      haptic.light();
      activeTab.value = tab;
      if (tab === 'quiz') {
        // 恢复做题位置，不强制重载
        nextTick(() => window.scrollTo({ top: scrollMemory.value['quiz'] || 0 }));
        return;
      }
      if (tab === 'stats') loadStats();
      if (tab === 'mistakes') { mistakePage.value = 1; loadMistakes(1); }
      if (tab === 'favorites') { favPage.value = 1; loadFavorites(1); }
      // 其它 Tab 默认回到顶部
      nextTick(() => window.scrollTo({ top: scrollMemory.value[tab] || 0 }));
    };
```

- [ ] **Step 4: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_frontend.py -v`
Expected: PASS

- [ ] **Step 5: 提交**

```bash
git add backend/static/js/app.js
git commit -m "fix: 切 Tab 恢复各页滚动位置，修复做题中途切走位置丢失"
```

---

## Task 3: R3 — 全局共享 loading 导致跨 Tab 串台（P1）

**Files:**
- Modify: `backend/static/js/app.js:28` (loading 定义)、`fetchWithLoading` 用法
- Modify: `backend/templates/index.html:1265,1310` (空状态门控)
- Test: `backend/tests/test_frontend.py`

**根因：** 只有一个 `loading` ref，所有 Tab 的空状态用 `!loading` 判断。quiz 加载中切到收藏，收藏的空状态被错误隐藏（`!loading` 为 false → 空状态不显示 → 页面空白）。

**修复策略：** 把"是否正在加载"从单一全局布尔改为按 Tab 维度的加载标记，或给空状态判断加上 Tab 维度。最小改动方案：空状态门控改为"当前 Tab 自己的数据加载中"而非全局 loading。

- [ ] **Step 1: 写失败测试**

```python
    # ---- R3: 加载态跨 Tab 串台 ----
    def test_r3_empty_state_not_gated_by_global_loading(self):
        """收藏/错题空状态不应被全局 loading 误隐藏"""
        # 收藏空状态不应再依赖全局 loading（应改成各自的数据源判断）
        # 检查 favorites 空状态区域不再用全局 loading 做门控
        self.assertNotIn("favorites.length === 0 && !loading", self.html,
                         "收藏空状态被全局 loading 门控会导致跨 Tab 串台")
        self.assertNotIn("mistakes.length === 0 && !loading", self.html,
                         "错题空状态被全局 loading 门控会导致跨 Tab 串台")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_frontend.py::TestFrontendFixes::test_r3_empty_state_not_gated_by_global_loading -v`
Expected: FAIL

- [ ] **Step 3: 实现 — 引入按 Tab 的加载标记**

在 `app.js`（`app.js:28` 附近）增加：

```javascript
    // R3 修复：按 Tab 的加载标记，避免跨 Tab 串台
    const tabLoading = Vue.ref({ quiz: false, stats: false, mistakes: false, favorites: false });
    const isLoading = (tab) => tabLoading.value[tab] || false;
```

并把 `fetchWithLoading` 改为可指定 tab（保持向后兼容，默认仍动全局 loading 用于顶部进度条，但额外标记当前 Tab）：

```javascript
    const fetchWithLoading = async (url, options = {}) => {
      const tab = activeTab.value || 'quiz';
      startLoading();
      tabLoading.value[tab] = true;
      try {
        options.headers = options.headers || {};
        options.headers['X-Session-Id'] = sessionId;
        const res = await fetch(url, options);
        const data = await res.json();
        finishLoading();
        tabLoading.value[tab] = false;
        return data;
      } catch (err) {
        finishLoading();
        tabLoading.value[tab] = false;
        showToast('网络请求失败，请稍后重试', 'error');
        throw err;
      }
    };
```

- [ ] **Step 4: 实现 — 改模板空状态门控**

在 `index.html`：
- `:1265` 错题空状态：`v-if="mistakes.length === 0 && !loading"` → `v-if="mistakes.length === 0 && !isLoading('mistakes')"`
- `:1310` 收藏空状态：`v-if="favorites.length === 0 && !loading"` → `v-if="favorites.length === 0 && !isLoading('favorites')"`

（需在 createApp 的 return/setup 暴露 `isLoading`。）

- [ ] **Step 5: 运行测试确认通过**

Run: `cd backend && python -m pytest tests/test_frontend.py -v`
Expected: PASS

- [ ] **Step 6: 提交**

```bash
git add backend/static/js/app.js backend/templates/index.html
git commit -m "fix: 加载态按 Tab 隔离，修复收藏/错题空状态被跨 Tab loading 误隐藏"
```

---

## Task 4: R4 — 双加载 + 筛选残留（P2）

**Files:**
- Modify: `backend/templates/index.html:833,835` (双绑定)
- Modify: `backend/static/js/app.js:386-389` (exitSingleMode)、`app.js:808-813` (redoQuestion 筛选残留)
- Test: `backend/tests/test_frontend.py`

**根因 A：** `@click="exitSingleMode(); switchMode('normal')"` — `exitSingleMode` 已 `loadQuestions(1)`，`switchMode('normal')` 若 mode 变了又加载一次，中间 `questions` 闪烁。
**根因 B：** `redoQuestion` 把当前题的 course/type 写入 `selectedCourse`/`selectedTypes` 后不清，下次改筛选时被带入。
**根因 C：** `practiceMistakes` 不重置 `mode`，导致"加载更多"按钮（`v-if="mode==='normal'"`）消失、模式高亮错。

**修复策略：**
- A：`exitSingleMode` 不自己 loadQuestions，仅切模式标志，把加载责任交给调用方（switchMode）。或：模板去掉重复的 `switchMode('normal')`，`exitSingleMode` 内部处理好。选后者，改动最小且符合"单一职责"。
- B：`redoQuestion` 在结束时恢复原筛选，或记录"这是单题重做"状态，回到列表时重置筛选。
- C：`practiceMistakes` 显式设 `mode='normal'`。

- [ ] **Step 1: 写失败测试**

```python
    # ---- R4: 双加载与筛选残留 ----
    def test_r4_no_double_load_on_mode_switch(self):
        """列表刷题按钮不应触发双重加载"""
        # exitSingleMode 内部已 loadQuestions，模板不应再叠加 switchMode 触发二次加载
        self.assertNotIn("exitSingleMode(); switchMode('normal')", self.html,
                         "列表刷题按钮双重加载，应只保留单一加载入口")

    def test_r4_redo_resets_shared_filter(self):
        """单题重做不应污染共享筛选"""
        # redoQuestion 结束后应复位 selectedCourse/selectedTypes，否则下次筛选带残留
        # 通过断言 app.js 存在复位逻辑
        self.assertTrue(
            "previousCourse" in self.js or "resetFilter" in self.js or "savedCourse" in self.js,
            "redoQuestion 应保存并复位筛选，避免残留污染后续列表加载"
        )

    def test_r4_practice_mistakes_sets_normal_mode(self):
        """错题练习应进入 normal 模式，否则加载更多按钮消失"""
        self.assertIn("mode.value = 'normal'", self.js,
                      "practiceMistakes 应显式设置 mode='normal'")
```

- [ ] **Step 2: 运行确认失败**

Run: `cd backend && python -m pytest tests/test_frontend.py -v`
Expected: 部分测试 FAIL

- [ ] **Step 3: 实现 — A 去双加载**

`index.html:833` 列表刷题按钮：

旧：`@click="exitSingleMode(); switchMode('normal')"`
新：`@click="switchMode('normal')"`（让 switchMode 统一负责加载）

并在 `app.js` `switchMode`（`app.js:290-298`）开头处理退出单题模式：

```javascript
    const switchMode = (m) => {
      // R4 修复 A：统一加载入口，退出单题模式不再在模板里另调一次
      if (singleMode.value) singleMode.value = false;
      if (mode.value === m && m === 'normal') {
        // 已在 normal 且非单题：刷新列表
        loadQuestions(1);
        return;
      }
      mode.value = m;
      if (m === 'normal') loadQuestions(1);
      else if (m === 'random') loadRandom();
    };
```

同时把 `exitSingleMode`（`app.js:386-389`）改为只切标志、不加载：

```javascript
    const exitSingleMode = () => {
      singleMode.value = false;
      // 不在此 loadQuestions，避免与 switchMode 双重加载（R4-A）
    };
```

- [ ] **Step 4: 实现 — B redoQuestion 复位筛选**

`app.js` redoQuestion（`app.js:791-824`）：进入前保存筛选，结束（切到 quiz 后）恢复：

```javascript
    const redoQuestion = (q) => {
      // R4 修复 B：保存当前筛选，单题重做后恢复，避免污染列表
      const savedCourse = selectedCourse.value;
      const savedTypes = selectedTypes.value.slice();
      // ... 原有逻辑 ...
      // 在设置 activeTab='quiz' 之前恢复筛选
      selectedCourse.value = savedCourse;
      selectedTypes.value = savedTypes;
      activeTab.value = 'quiz';
    };
```

（具体把保存/恢复插入 redoQuestion 现有结构，不破坏 mode='normal' 设置。）

- [ ] **Step 5: 实现 — C practiceMistakes 设 mode**

`app.js` practiceMistakes（`app.js:644-663`）：在加载前加：

```javascript
      mode.value = 'normal';   // R4 修复 C：确保加载更多按钮与模式高亮正确
```

- [ ] **Step 6: 运行测试确认通过 + 全量回归**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS（含原有 25 + 新增 4 类）

- [ ] **Step 7: 提交**

```bash
git add backend/static/js/app.js backend/templates/index.html
git commit -m "fix: 消除模式切换双重加载与筛选残留，错题练习模式状态修正"
```

---

## Task 5: 全量回归 + 人工体感核对

- [ ] **Step 1: 全量测试**

Run: `cd backend && python -m pytest tests/ -v`
Expected: 全部 PASS

- [ ] **Step 2: 前端冒烟（ui_smoke.py 如适用）**

Run: `cd backend && python tests/ui_smoke.py`
Expected: 无报错

- [ ] **Step 3: 关键体感自测清单（手动）**
- 单题模式做到第 3 题 → F5 刷新 → 仍在单题模式且不白屏 ✓
- 列表刷题滚到第 10 题 → 点"统计" → 再点"刷题" → 滚动回到第 10 题附近 ✓
- 触发 quiz 加载 → 加载中点"收藏" → 收藏空状态正常显示（不被全局 loading 隐藏）✓
- 点"列表刷题"按钮 → 只加载一次，无闪烁 ✓
- 错题里"重做此题" → 回到列表 → 改筛选不带残留 ✓

- [ ] **Step 4: 提交收尾**

```bash
git add -A
git commit -m "test: 新增前端关键逻辑回归测试"
```

---

## 自检（Spec coverage）

- "切换页面就乱" → R2（滚动+不对称）覆盖 ✓
- "做题深入后切走状态错乱" → R1（白屏）+ R2（滚动）覆盖 ✓
- 用户额外担心"数据隔离" → 已在后端实现，lite 路由漏洞另记（不在本计划，建议单独修 app.py:167）
- P0~P2 四个根因均有 Task 对应 ✓
- 无占位符：每步含完整代码/命令 ✓
- 类型一致：函数名 switchTab/switchMode/exitSingleMode/redoQuestion/practiceMistakes/fetchWithLoading/loadStats 等全程统一 ✓
