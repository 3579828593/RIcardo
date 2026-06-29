# E2E 测试 conftest
import pytest
from playwright.sync_api import sync_playwright

@pytest.fixture(scope="module")
def browser():
    """启动浏览器实例"""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        yield browser
        browser.close()
