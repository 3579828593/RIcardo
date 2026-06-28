# -*- coding: utf-8 -*-
"""页面冒烟测试：检查 Vue 页面是否渲染、console 是否有错误。"""
from playwright.sync_api import sync_playwright


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        page.on("pageerror", lambda exc: errors.append(str(exc)))
        page.goto("http://127.0.0.1:5010", wait_until="networkidle")
        page.wait_for_selector("text=期末冲刺刷题系统 v2.1", timeout=10000)
        question_count = page.locator(".card.question").count()
        print({"question_count": question_count, "errors": errors[:5]})
        browser.close()
        if errors:
            raise SystemExit("页面存在错误: " + " | ".join(errors[:5]))
        if question_count < 1:
            raise SystemExit("页面没有渲染题目")


if __name__ == "__main__":
    main()
