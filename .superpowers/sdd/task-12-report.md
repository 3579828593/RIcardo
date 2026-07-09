# Task 12 报告：Step 2 — csv_importer.py 新增 sanitize_question

## 状态
**DONE**

## 提交 hash
`524fbfed3bbf7ccf7a500ca34f4ae82072bac6f4`

提交信息：`feat: Step 2 — sanitize_question 先检测后转义 + 长度限制`

## 测试数量
- 新增测试：9 个（`backend/tests/test_sanitize.py`）
- 回归测试总计：142 个通过（133 原有 + 9 新增）
- 测试运行命令：`cd d:\期末冲刺刷题系统\backend && python -m pytest -v --ignore=tests/e2e`
- 结果：`142 passed, 8 subtests passed in 28.76s`

## TDD 流程执行记录
1. **创建失败测试**：创建 `backend/tests/test_sanitize.py`，包含 9 个测试用例，覆盖：
   - 正常题目不标记
   - `<script>` 标签检测
   - `javascript:` URL 检测
   - `onerror` 事件检测
   - 检测后 HTML 转义
   - 先检测后转义（关键顺序验证）
   - 选项转义
   - 题干超长（>2000 字符）
   - 选项超长（>500 字符）
2. **验证失败**：运行测试，9 个全部 FAILED（ImportError: cannot import name 'sanitize_question'），符合预期。
3. **添加实现**：在 `backend/csv_importer.py` 中：
   - 顶部新增 `import html`
   - `OPTION_KEYS` 之后新增 4 个常量：`SENSITIVE_WORDS`、`MAX_STEM_LENGTH`、`MAX_OPTION_LENGTH`、`MAX_QUESTIONS_PER_IMPORT`
   - 文件末尾新增 `sanitize_question(q: dict) -> dict` 函数，实现"先检测敏感词（在原始文本上）→ 后 HTML 转义"的核心逻辑，并包含长度校验。
4. **验证通过**：运行 `tests/test_sanitize.py`，9 个全部 PASSED。
5. **完整回归**：运行 `python -m pytest -v --ignore=tests/e2e`，142 passed。
6. **提交**：仅提交 `backend/csv_importer.py` 和 `backend/tests/test_sanitize.py` 两个文件（2 files changed, 162 insertions）。

## 实现摘要
```python
import html

SENSITIVE_WORDS = ['<script', 'javascript:', 'onerror', 'onload', 'onclick']
MAX_STEM_LENGTH = 2000
MAX_OPTION_LENGTH = 500
MAX_QUESTIONS_PER_IMPORT = 500

def sanitize_question(q: dict) -> dict:
    """过滤题目中的危险内容。先检测敏感词，后 HTML 转义。"""
    # 0. 长度校验（题干 / 选项）
    # 1. 在原始文本上检测敏感词（combined.lower() 与 SENSITIVE_WORDS 匹配）
    # 2. HTML 转义 stem / explanation / knowledge / options
```

## 顾虑或偏差
- **e2e 测试目录**：`backend/tests/e2e/` 依赖 `playwright` 模块，当前环境未安装，导致 `python -m pytest -v`（不忽略 e2e）会在收集阶段报错 `ModuleNotFoundError: No module named 'playwright'`。这是**预先存在的环境问题**，与本任务无关。为完成回归验证，使用 `--ignore=tests/e2e` 参数运行，得到 142 个测试通过（与简报预期的 133 + 9 = 142 完全一致）。`MAX_QUESTIONS_PER_IMPORT` 常量已按简报要求添加，但本任务未在 `sanitize_question` 中使用，将在后续 Task 中接入。
- **数据库文件变更**：`backend/data/quiz.db` 因运行测试产生变更，已按简报要求在提交时排除（仅 `git add` 指定的两个文件）。

## 涉及文件
- 修改：`backend/csv_importer.py`（+41 行：1 个 import、4 个常量、1 个函数）
- 新增：`backend/tests/test_sanitize.py`（123 行，9 个测试）
