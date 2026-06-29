# -*- coding: utf-8 -*-
"""CSV 导入解析器单元测试"""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from csv_importer import parse_csv, generate_template, REQUIRED_FIELDS, VALID_TYPES


class TestParseCSV:
    """CSV 解析核心功能"""

    def test_single_choice(self):
        """单选题正常解析"""
        csv_text = "course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge\n"
        csv_text += "weather,1,single,什么是晴天？,阳光明媚,阴云密布,大雨倾盆,狂风大作,A,晴天就是阳光明媚,天气基础\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 1
        q = result['questions'][0]
        assert q['course'] == 'weather'
        assert q['chapter'] == 1
        assert q['type'] == 'single'
        assert q['stem'] == '什么是晴天？'
        assert q['options']['A'] == '阳光明媚'
        assert q['answer'] == ['A']
        assert q['explanation'] == '晴天就是阳光明媚'
        assert q['knowledge'] == '天气基础'

    def test_multiple_choice(self):
        """多选题逗号分隔答案"""
        csv_text = "course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge\n"
        csv_text += 'weather,1,multiple,哪些是降水形式？,雨,雪,晴天,冰雹,"A,B,D",多种降水,降水分类\n'
        result = parse_csv(csv_text)
        assert len(result['questions']) == 1
        q = result['questions'][0]
        assert q['type'] == 'multiple'
        assert q['answer'] == ['A', 'B', 'D']

    def test_true_false(self):
        """判断题正常解析"""
        csv_text = "course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge\n"
        csv_text += "weather,1,true_false,下雨天需要带伞,对,错,,,对,防雨常识,生活常识\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 1
        q = result['questions'][0]
        assert q['type'] == 'true_false'
        assert q['answer'] == ['对']

    def test_fill_blank(self):
        """填空题管道分隔多空"""
        csv_text = "course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge\n"
        csv_text += "weather,1,fill_blank,气温的单位是____和____,,,,,摄氏度|华氏度,温度单位,气象基础\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 1
        q = result['questions'][0]
        assert q['type'] == 'fill_blank'
        assert q['answer'] == ['摄氏度', '华氏度']

    def test_fill_blank_single(self):
        """填空题单空"""
        csv_text = "course,chapter,type,stem,answer\n"
        csv_text += "weather,1,fill_blank,1+1=____,2\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 1
        assert result['questions'][0]['answer'] == ['2']

    def test_short_answer(self):
        """简答题正常解析"""
        csv_text = "course,chapter,type,stem,answer\n"
        csv_text += "english,1,short_answer,请简述英语语法,主谓宾结构\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 1
        assert result['questions'][0]['type'] == 'short_answer'

    def test_multiple_rows(self):
        """多行混合题型"""
        csv_text = "course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge\n"
        csv_text += "weather,1,single,题1,A,B,C,D,A,解析1,知识1\n"
        csv_text += "weather,2,multiple,题2,A,B,C,D,\"A,C\",解析2,知识2\n"
        csv_text += "english,1,true_false,题3,对,错,,,对,解析3,知识3\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 3
        assert result['questions'][0]['chapter'] == 1
        assert result['questions'][1]['chapter'] == 2
        assert result['questions'][2]['course'] == 'english'


class TestParseCSVErrors:
    """CSV 解析错误处理"""

    def test_empty_content(self):
        """空内容"""
        result = parse_csv("")
        assert len(result['questions']) == 0
        assert len(result['errors']) == 1
        assert '空' in result['errors'][0]['error']

    def test_empty_whitespace(self):
        """纯空白内容"""
        result = parse_csv("   \n\n   ")
        assert len(result['questions']) == 0
        assert len(result['errors']) >= 1

    def test_missing_header(self):
        """表头缺少必填列"""
        csv_text = "course,chapter,stem\nweather,1,题干\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 0
        assert len(result['errors']) == 1
        assert '表头' in result['errors'][0]['error']

    def test_missing_required_field(self):
        """数据行缺少必填字段"""
        csv_text = "course,chapter,type,stem,answer\n"
        csv_text += "weather,1,single,,A\n"  # stem 为空
        result = parse_csv(csv_text)
        assert len(result['questions']) == 0
        assert len(result['errors']) == 1
        assert '缺少必填字段' in result['errors'][0]['error']
        assert result['errors'][0]['row'] == 2

    def test_invalid_type(self):
        """无效题型"""
        csv_text = "course,chapter,type,stem,answer\n"
        csv_text += "weather,1,unknown_type,题干,A\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 0
        assert len(result['errors']) == 1
        assert '无效题型' in result['errors'][0]['error']

    def test_invalid_chapter(self):
        """章节号非正整数"""
        csv_text = "course,chapter,type,stem,answer\n"
        csv_text += "weather,abc,single,题干,A\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 0
        assert len(result['errors']) == 1
        assert '正整数' in result['errors'][0]['error']

    def test_empty_answer(self):
        """答案为空"""
        csv_text = "course,chapter,type,stem,answer\n"
        csv_text += "weather,1,single,题干,\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 0
        assert len(result['errors']) == 1

    def test_partial_errors(self):
        """部分行有错误，部分行正常"""
        csv_text = "course,chapter,type,stem,answer\n"
        csv_text += "weather,1,single,正常题,A\n"
        csv_text += "weather,abc,single,错误题,A\n"  # chapter 无效
        csv_text += "weather,1,single,另一正常题,B\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 2
        assert len(result['errors']) == 1
        assert result['errors'][0]['row'] == 3  # 第3行（数据行第2行）

    def test_bom_header(self):
        """BOM 头处理"""
        csv_text = "\ufeffcourse,chapter,type,stem,answer\nweather,1,single,题干,A\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 1
        assert result['questions'][0]['course'] == 'weather'

    def test_skip_empty_rows(self):
        """跳过空行"""
        csv_text = "course,chapter,type,stem,answer\n"
        csv_text += "weather,1,single,题1,A\n"
        csv_text += "\n"  # 空行
        csv_text += "weather,2,single,题2,B\n"
        result = parse_csv(csv_text)
        assert len(result['questions']) == 2
        assert len(result['errors']) == 0


class TestGenerateTemplate:
    """模板生成"""

    def test_template_has_header(self):
        """模板包含表头"""
        template = generate_template()
        lines = template.strip().split('\n')
        header = lines[0]
        for field in REQUIRED_FIELDS:
            assert field in header

    def test_template_has_examples(self):
        """模板包含各题型示例"""
        template = generate_template()
        for qtype in VALID_TYPES:
            assert qtype in template

    def test_template_is_csv(self):
        """模板是有效的 CSV"""
        template = generate_template()
        result = parse_csv(template)
        assert len(result['questions']) >= 4  # 至少4种题型示例
        assert len(result['errors']) == 0
