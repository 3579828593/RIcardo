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
