# Task 12: Step 2 — csv_importer.py 新增 sanitize_question

## Context
This is Task 12 of 17 in a UGC question bank system implementation plan. The project is a Flask + Vue + SQLite quiz system at `d:\期末冲刺刷题系统`. Tasks 1-11 are complete (133 tests pass). This task adds a `sanitize_question()` function to the existing CSV importer module.

## Files
- Modify: `backend/csv_importer.py` — 新增 `sanitize_question()` 函数 + 常量
- Test: `backend/tests/test_sanitize.py` (new file)

## Current State of csv_importer.py
The file currently has:
- Imports: `import csv`, `import io`
- Constants: `REQUIRED_FIELDS`, `OPTIONAL_FIELDS`, `VALID_TYPES`, `OPTION_KEYS`
- Functions: `parse_csv(content)`, `generate_template()`
- The file is 138 lines, ends at `generate_template()`

## Step 1: Write the failing test

Create `backend/tests/test_sanitize.py`:

```python
# -*- coding: utf-8 -*-
"""测试 sanitize_question：先检测敏感词，后 HTML 转义"""
import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def test_clean_question_not_flagged():
    """正常题目不被标记"""
    from csv_importer import sanitize_question
    q = {
        'stem': '什么是天气?',
        'options': {'A': '晴', 'B': '雨'},
        'answer': ['A'],
        'explanation': '天气是大气状态',
        'knowledge': '基础',
    }
    result = sanitize_question(q)
    assert result.get('_flagged') is False or result.get('_flagged') == 0


def test_script_tag_detected():
    """<script> 标签被检测"""
    from csv_importer import sanitize_question
    q = {
        'stem': '<script>alert(1)</script>',
        'options': {},
        'answer': ['A'],
    }
    result = sanitize_question(q)
    assert result['_flagged'] is True


def test_javascript_url_detected():
    """javascript: URL 被检测"""
    from csv_importer import sanitize_question
    q = {
        'stem': '点击 <a href="javascript:alert(1)">这里</a>',
        'options': {},
        'answer': ['A'],
    }
    result = sanitize_question(q)
    assert result['_flagged'] is True


def test_onerror_detected():
    """onerror 事件被检测"""
    from csv_importer import sanitize_question
    q = {
        'stem': '<img src=x onerror=alert(1)>',
        'options': {},
        'answer': ['A'],
    }
    result = sanitize_question(q)
    assert result['_flagged'] is True


def test_html_escaped_after_detection():
    """检测后 HTML 转义"""
    from csv_importer import sanitize_question
    q = {
        'stem': '<b>加粗文本</b>',
        'options': {},
        'answer': ['A'],
    }
    result = sanitize_question(q)
    assert '<b>' not in result['stem']
    assert '&lt;b&gt;' in result['stem']


def test_detection_before_escape():
    """关键：先检测后转义——转义后 <script 变成 &lt;script 不影响检测"""
    from csv_importer import sanitize_question
    q = {
        'stem': '<script>alert("xss")</script>',
        'options': {},
        'answer': ['A'],
    }
    result = sanitize_question(q)
    # 必须被标记（检测在转义之前）
    assert result['_flagged'] is True
    # 转义后不应包含原始 <script>
    assert '<script>' not in result['stem']


def test_options_escaped():
    """选项也被转义"""
    from csv_importer import sanitize_question
    q = {
        'stem': '正常题',
        'options': {'A': '<img src=x>', 'B': '正常'},
        'answer': ['A'],
    }
    result = sanitize_question(q)
    assert '<img' not in result['options']['A']
    assert '&lt;img' in result['options']['A']


def test_stem_too_long():
    """题干超过 2000 字符"""
    from csv_importer import sanitize_question
    q = {
        'stem': 'A' * 2001,
        'options': {},
        'answer': ['A'],
    }
    result = sanitize_question(q)
    assert result.get('_error') is not None


def test_option_too_long():
    """选项超过 500 字符"""
    from csv_importer import sanitize_question
    q = {
        'stem': '正常',
        'options': {'A': 'B' * 501},
        'answer': ['A'],
    }
    result = sanitize_question(q)
    assert result.get('_error') is not None
```

## Step 2: Run test to verify it fails

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/test_sanitize.py -v`
Expected: FAIL — `sanitize_question` 不存在 (ImportError)

## Step 3: Add `sanitize_question` to `csv_importer.py`

Add `import html` at the top (after existing imports).

Add these constants after the existing constants (after `OPTION_KEYS`):

```python
SENSITIVE_WORDS = ['<script', 'javascript:', 'onerror', 'onload', 'onclick']
MAX_STEM_LENGTH = 2000
MAX_OPTION_LENGTH = 500
MAX_QUESTIONS_PER_IMPORT = 500
```

Add the function (after `generate_template`, at the end of the file):

```python
def sanitize_question(q: dict) -> dict:
    """过滤题目中的危险内容。先检测敏感词，后 HTML 转义。
    返回处理后的 dict，新增 _flagged 和可能的 _error 字段。"""
    # 0. 长度校验
    stem = q.get('stem', '')
    if len(stem) > MAX_STEM_LENGTH:
        q['_flagged'] = True
        q['_error'] = f"题干超过 {MAX_STEM_LENGTH} 字符"
        return q
    for key, val in q.get('options', {}).items():
        if len(str(val)) > MAX_OPTION_LENGTH:
            q['_flagged'] = True
            q['_error'] = f"选项 {key} 超过 {MAX_OPTION_LENGTH} 字符"
            return q

    # 1. 先在原始文本上检测敏感词
    raw_texts = []
    for field in ['stem', 'explanation', 'knowledge']:
        if q.get(field):
            raw_texts.append(str(q[field]))
    for value in q.get('options', {}).values():
        raw_texts.append(str(value))
    combined = '\n'.join(raw_texts).lower()
    q['_flagged'] = any(word in combined for word in SENSITIVE_WORDS)

    # 2. 后 HTML 转义
    for field in ['stem', 'explanation', 'knowledge']:
        if q.get(field):
            q[field] = html.escape(str(q[field]))
    for key in q.get('options', {}):
        q['options'][key] = html.escape(str(q['options'][key]))

    return q
```

## Step 4: Run test to verify it passes

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest tests/test_sanitize.py -v`
Expected: PASS — all 9 tests pass

## Step 5: Run full regression

Run: `cd d:\期末冲刺刷题系统\backend && python -m pytest -v`
Expected: 142 tests pass (133 existing + 9 new)

## Step 6: Commit

```bash
cd d:\期末冲刺刷题系统
git add backend/csv_importer.py backend/tests/test_sanitize.py
git commit -m "feat: Step 2 — sanitize_question 先检测后转义 + 长度限制"
```
