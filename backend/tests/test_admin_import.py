# -*- coding: utf-8 -*-
"""CSV 导入接口和管理后台 API 测试"""
import sys
import os
import json
import pytest
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import app, db
from config import load_config


@pytest.fixture
def client():
    app.config['TESTING'] = True
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024
    with app.test_client() as client:
        yield client


@pytest.fixture
def admin_headers():
    cfg = load_config()
    return {'X-Admin-Token': cfg["security"]["admin_token"]}


@pytest.fixture
def no_admin_headers():
    return {'X-Admin-Token': 'wrong_token'}


VALID_CSV = """course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge
test_course,99,single,测试单选题,选项A,选项B,选项C,选项D,A,解析,知识点
test_course,99,multiple,测试多选题,选项A,选项B,选项C,选项D,"A,C",解析,知识点
test_course,99,true_false,测试判断题,对,错,,,对,解析,知识点
"""

INVALID_CSV = """course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge
test_course,99,single,正常题,选项A,选项B,选项C,选项D,A,解析,知识点
test_course,abc,single,章节错误题,选项A,选项B,选项C,选项D,A,解析,知识点
test_course,99,invalid_type,题型错误题,选项A,选项B,选项C,选项D,A,解析,知识点
"""

EMPTY_CSV = ""

HEADER_ONLY_CSV = "course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge\n"


class TestAdminAuth:
    """管理接口认证测试"""

    def test_no_token_returns_401(self, client):
        """无 token 返回 401"""
        res = client.get('/api/admin/questions')
        assert res.status_code == 401

    def test_wrong_token_returns_401(self, client, no_admin_headers):
        """错误 token 返回 401"""
        res = client.get('/api/admin/questions', headers=no_admin_headers)
        assert res.status_code == 401

    def test_correct_token_returns_200(self, client, admin_headers):
        """正确 token 返回 200"""
        res = client.get('/api/admin/questions?page=1&page_size=5', headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert 'items' in data
        assert 'total' in data


class TestAdminListQuestions:
    """题目列表接口测试"""

    def test_list_default_pagination(self, client, admin_headers):
        """默认分页"""
        res = client.get('/api/admin/questions', headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        assert 'items' in data
        assert 'total' in data
        assert 'page' in data
        assert 'page_size' in data
        assert len(data['items']) <= data['page_size']

    def test_list_with_course_filter(self, client, admin_headers):
        """课程筛选"""
        res = client.get('/api/admin/questions?course=weather', headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        for item in data.get('items', []):
            assert item['course'] == 'weather'

    def test_list_with_type_filter(self, client, admin_headers):
        """题型筛选"""
        res = client.get('/api/admin/questions?type=single', headers=admin_headers)
        assert res.status_code == 200
        data = res.get_json()
        for item in data.get('items', []):
            assert item['type'] == 'single'

    def test_list_with_keyword(self, client, admin_headers):
        """关键词搜索"""
        res = client.get('/api/admin/questions?keyword=天气', headers=admin_headers)
        assert res.status_code == 200


class TestCSVImport:
    """CSV 导入接口测试"""

    def test_import_valid_csv(self, client, admin_headers):
        """导入有效 CSV"""
        res = client.post(
            '/api/admin/import/csv',
            data={'file': (io.BytesIO(VALID_CSV.encode('utf-8')), 'test.csv')},
            content_type='multipart/form-data',
            headers=admin_headers
        )
        assert res.status_code == 201
        data = res.get_json()
        assert 'added' in data
        assert 'skipped' in data
        assert 'total' in data
        assert data['total'] == 3

    def test_import_no_token(self, client):
        """无 token 导入"""
        res = client.post(
            '/api/admin/import/csv',
            data={'file': (io.BytesIO(VALID_CSV.encode('utf-8')), 'test.csv')},
            content_type='multipart/form-data'
        )
        assert res.status_code == 401

    def test_import_empty_csv(self, client, admin_headers):
        """导入空 CSV"""
        res = client.post(
            '/api/admin/import/csv',
            data={'file': (io.BytesIO(EMPTY_CSV.encode('utf-8')), 'empty.csv')},
            content_type='multipart/form-data',
            headers=admin_headers
        )
        assert res.status_code == 400

    def test_import_header_only(self, client, admin_headers):
        """导入仅表头 CSV"""
        res = client.post(
            '/api/admin/import/csv',
            data={'file': (io.BytesIO(HEADER_ONLY_CSV.encode('utf-8')), 'header.csv')},
            content_type='multipart/form-data',
            headers=admin_headers
        )
        assert res.status_code == 400

    def test_import_partial_errors(self, client, admin_headers):
        """导入部分错误 CSV — 有效行仍导入"""
        import time
        uid = str(int(time.time()))
        csv_content = f"""course,chapter,type,stem,option_A,option_B,option_C,option_D,answer,explanation,knowledge
test_partial_{uid},99,single,正常题_{uid},选项A,选项B,选项C,选项D,A,解析,知识点
test_partial_{uid},abc,single,章节错误题_{uid},选项A,选项B,选项C,选项D,A,解析,知识点
test_partial_{uid},99,invalid_type,题型错误题_{uid},选项A,选项B,选项C,选项D,A,解析,知识点
"""
        res = client.post(
            '/api/admin/import/csv',
            data={'file': (io.BytesIO(csv_content.encode('utf-8')), 'partial.csv')},
            content_type='multipart/form-data',
            headers=admin_headers
        )
        assert res.status_code == 201
        data = res.get_json()
        assert data['added'] >= 1  # 至少1题成功
        assert 'parse_errors' in data
        assert len(data['parse_errors']) == 2  # 2行有错误

    def test_import_json_body(self, client, admin_headers):
        """通过 JSON body 导入"""
        res = client.post(
            '/api/admin/import/csv',
            json={'content': VALID_CSV},
            headers=admin_headers
        )
        assert res.status_code == 201
        data = res.get_json()
        assert data['total'] == 3

    def test_import_duplicate_skipped(self, client, admin_headers):
        """重复导入跳过"""
        # 第一次导入
        res1 = client.post(
            '/api/admin/import/csv',
            data={'file': (io.BytesIO(VALID_CSV.encode('utf-8')), 'dup1.csv')},
            content_type='multipart/form-data',
            headers=admin_headers
        )
        assert res1.status_code == 201

        # 第二次导入相同内容 — 应全部跳过
        res2 = client.post(
            '/api/admin/import/csv',
            data={'file': (io.BytesIO(VALID_CSV.encode('utf-8')), 'dup2.csv')},
            content_type='multipart/form-data',
            headers=admin_headers
        )
        assert res2.status_code == 201
        data2 = res2.get_json()
        assert data2['added'] == 0
        assert data2['skipped'] == 3


class TestTemplateDownload:
    """模板下载测试"""

    def test_download_template(self, client, admin_headers):
        """下载模板"""
        res = client.get('/api/admin/template', headers=admin_headers)
        assert res.status_code == 200
        assert 'text/csv' in res.content_type
        content = res.data.decode('utf-8')
        assert 'course' in content
        assert 'chapter' in content
        assert 'single' in content
        assert 'multiple' in content

    def test_download_template_no_token(self, client):
        """无 token 下载模板"""
        res = client.get('/api/admin/template')
        assert res.status_code == 401

    def test_template_content_disposition(self, client, admin_headers):
        """Content-Disposition 头"""
        res = client.get('/api/admin/template', headers=admin_headers)
        cd = res.headers.get('Content-Disposition', '')
        assert 'attachment' in cd
        assert 'quiz_template.csv' in cd


class TestBatchAddQuestions:
    """数据库批量导入测试"""

    def test_batch_add_new_questions(self):
        """批量添加新题目"""
        import time
        uid = str(int(time.time()))
        questions = [
            {
                'course': f'test_batch_{uid}',
                'chapter': 1,
                'type': 'single',
                'stem': f'批量测试题1_{uid}',
                'options': {'A': '选项A', 'B': '选项B'},
                'answer': ['A'],
                'explanation': '',
                'knowledge': '',
            },
            {
                'course': f'test_batch_{uid}',
                'chapter': 1,
                'type': 'true_false',
                'stem': f'批量测试题2_{uid}',
                'options': {'A': '对', 'B': '错'},
                'answer': ['对'],
                'explanation': '',
                'knowledge': '',
            },
        ]
        result = db.batch_add_questions(questions)
        assert result['added'] == 2
        assert result['skipped'] == 0

    def test_batch_add_duplicate_skipped(self):
        """重复题目跳过"""
        import time
        uid = str(int(time.time())) + '_dup'
        questions = [
            {
                'course': f'test_batch_{uid}',
                'chapter': 1,
                'type': 'single',
                'stem': f'批量测试题1_{uid}',
                'options': {},
                'answer': ['A'],
                'explanation': '',
                'knowledge': '',
            },
        ]
        # 第一次添加
        db.batch_add_questions(questions)
        # 第二次添加相同内容 — 应跳过
        result = db.batch_add_questions(questions)
        assert result['added'] == 0
        assert result['skipped'] == 1

    def test_batch_add_empty_list(self):
        """空列表"""
        result = db.batch_add_questions([])
        assert result['added'] == 0
        assert result['skipped'] == 0
