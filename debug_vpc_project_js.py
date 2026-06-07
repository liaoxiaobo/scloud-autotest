#!/usr/bin/env python3
"""用JS强制点击选择项目"""
import re
from playwright.sync_api import sync_playwright

BASE_URL = 'https://172.22.1.190:30000'
USERNAME = 'admin'
PASSWORD = 'keystone_sugon'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    page.goto(BASE_URL, wait_until='domcontentloaded')
    page.wait_for_timeout(3000)
    page.get_by_placeholder('请输入登录账号').fill(USERNAME)
    page.get_by_placeholder('请输入登录密码').fill(PASSWORD)
    page.get_by_text('登 录').click()
    page.wait_for_url(re.compile(r'.*#/(index|console-page)$'), timeout=20000)
    page.wait_for_timeout(2000)

    if 'console-page' in page.url:
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(3000)

    # goto VPC
    page.goto(f'{BASE_URL}/vpc/#/vpc-network-list', wait_until='domcontentloaded')
    page.wait_for_timeout(5000)
    print(f"goto VPC 后 URL: {page.url}")

    # 检查是否需要选择项目
    body_text = page.evaluate("""() => document.body.innerText.substring(0, 200)""")
    if '请选择项目' in body_text:
        print("检测到项目选择界面")

        # 策略1: 点击"请选择项目"按钮
        try:
            project_btn = page.locator('.project_btn')
            if project_btn.count() > 0:
                print("点击'请选择项目'按钮...")
                project_btn.first.evaluate("el => el.click()")
                page.wait_for_timeout(2000)
        except Exception as e:
            print(f"点击project_btn失败: {e}")

        # 策略2: JS点击第一个组织
        print("尝试JS点击第一个组织...")
        result = page.evaluate("""() => {
            // 先找到所有 one-tree-msg-text 元素
            var msgs = document.querySelectorAll('.one-tree-msg-text');
            for (var i = 0; i < msgs.length; i++) {
                var text = msgs[i].innerText.trim();
                if (text && text.length > 0) {
                    // 触发点击事件
                    var event = new MouseEvent('click', { bubbles: true });
                    msgs[i].dispatchEvent(event);
                    return 'clicked: ' + text;
                }
            }
            return 'not_found';
        }""")
        print(f"JS点击结果: {result}")
        page.wait_for_timeout(5000)
        print(f"点击后 URL: {page.url}")

        # 再次检查
        body_text2 = page.evaluate("""() => document.body.innerText.substring(0, 300)""")
        print(f"最终body文本: {body_text2}")

        # 检查按钮
        buttons = page.evaluate("""() => {
            return Array.from(document.querySelectorAll('button, .el-button')).map(el => ({
                text: (el.innerText || el.textContent || '').trim().substring(0, 50),
                visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
            })).filter(b => b.visible && b.text);
        }""")
        print(f"可见按钮 ({len(buttons)} 个):")
        for b in buttons:
            print(f"  '{b['text']}'")

        has_new = any('新建' in b['text'] or '创建' in b['text'] for b in buttons)
        print(f"包含'新建/创建': {has_new}")

    page.screenshot(path='screenshots/vpc_after_js_project.png')
    browser.close()
