# -*- coding: utf-8 -*-
"""CSV 题目导入解析器 — 纯函数模块，易于测试"""
import csv
import io

REQUIRED_FIELDS = ['course', 'chapter', 'type', 'stem', 'answer']
OPTIONAL_FIELDS = ['explanation', 'knowledge']
VALID_TYPES = ['single', 'multiple', 'true_false', 'fill_blank', 'short_answer']
OPTION_KEYS = ['A', 'B', 'C', 'D', 'E', 'F']


def parse_csv(content: str) -> dict:
    """解析 CSV 文本，返回 {questions: [...], errors: [...]}

    Args:
        content: CSV 文本字符串（可含 BOM 头）

    Returns:
        {
            questions: [ {course, chapter, type, stem, options, answer, explanation, knowledge}, ... ],
            errors: [ {row: int, error: str}, ... ]
        }
    """
    if not content or not content.strip():
        return {'questions': [], 'errors': [{'row': 0, 'error': 'CSV 内容为空'}]}

    # 处理 BOM 头 (Excel 导出的 CSV 常带 \ufeff)
    if content.startswith('\ufeff'):
        content = content[1:]

    reader = csv.DictReader(io.StringIO(content))

    # 校验表头
    fieldnames = reader.fieldnames or []
    field_lower = {f.strip().lower(): f for f in fieldnames}
    missing_headers = [f for f in REQUIRED_FIELDS if f not in field_lower]
    if missing_headers:
        return {
            'questions': [],
            'errors': [{'row': 1, 'error': f'CSV 表头缺少必填列: {", ".join(missing_headers)}'}]
        }

    questions = []
    errors = []

    for line_no, row in enumerate(reader, start=2):  # 第1行是表头，数据从第2行开始
        # 跳过空行
        if not row or all(not (v and v.strip()) for v in row.values()):
            continue

        # 统一 key（处理大小写和空格）
        normalized = {}
        for k, v in row.items():
            if k:
                normalized[k.strip().lower()] = (v or '').strip()

        # 校验必填字段
        missing = [f for f in REQUIRED_FIELDS if not normalized.get(f)]
        if missing:
            errors.append({'row': line_no, 'error': f'缺少必填字段: {", ".join(missing)}'})
            continue

        # 校验题型
        qtype = normalized.get('type', '')
        if qtype not in VALID_TYPES:
            errors.append({
                'row': line_no,
                'error': f'无效题型 "{qtype}"，支持: {", ".join(VALID_TYPES)}'
            })
            continue

        # 校验章节号
        chapter_str = normalized.get('chapter', '')
        try:
            chapter = int(chapter_str)
            if chapter < 1:
                raise ValueError
        except (ValueError, TypeError):
            errors.append({'row': line_no, 'error': f'章节号必须为正整数，得到: "{chapter_str}"'})
            continue

        # 构建选项
        options = {}
        for key in OPTION_KEYS:
            val = normalized.get(f'option_{key.lower()}', '')
            if val:
                options[key] = val

        # 解析答案
        answer_str = normalized.get('answer', '')
        if not answer_str:
            errors.append({'row': line_no, 'error': '答案不能为空'})
            continue

        if qtype == 'multiple':
            # 多选：逗号分隔
            answer = [a.strip() for a in answer_str.split(',') if a.strip()]
            if not answer:
                errors.append({'row': line_no, 'error': '多选题答案解析失败'})
                continue
        elif qtype == 'fill_blank':
            # 填空：管道符分隔多空
            if '|' in answer_str:
                answer = [a.strip() for a in answer_str.split('|')]
            else:
                answer = [answer_str]
        elif qtype == 'true_false':
            # 判断题：标准化答案
            answer = [answer_str]
        else:
            # 单选/简答
            answer = [answer_str]

        # 构建题目对象
        q = {
            'course': normalized.get('course', ''),
            'chapter': chapter,
            'type': qtype,
            'stem': normalized.get('stem', ''),
            'options': options,
            'answer': answer,
            'explanation': normalized.get('explanation', ''),
            'knowledge': normalized.get('knowledge', ''),
        }
        questions.append(q)

    return {'questions': questions, 'errors': errors}


def generate_template() -> str:
    """生成 CSV 模板内容"""
    lines = ['course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge']
    lines.append('weather,1,single,这是一道单选题示例,选项A内容,选项B内容,选项C内容,选项D内容,A,解析内容,知识点')
    lines.append('weather,1,multiple,这是一道多选题示例,选项A,选项B,选项C,选项D,"A,C",解析,知识点')
    lines.append('weather,1,true_false,这是一道判断题,对,错,,,对,解析,知识点')
    lines.append('weather,1,fill_blank,这是一个填空题答案是_____,,,,,答案,解析,知识点')
    lines.append('english,1,short_answer,请简述英语语法规则,,,,,答案文本,解析,知识点')
    return '\n'.join(lines) + '\n'
