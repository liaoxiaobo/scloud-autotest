#!/usr/bin/env python3
"""用JS强制点击选择项目 - 增加等待时间"""
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
    print(f"goto VPC 后 URL: {page.url}")

    # 轮询等待页面加载
    for i in range(60):
        url = page.url
        body_text = page.evaluate("""() => document.body.innerText.substring(0, 100)""")
        print(f"  t={i*0.5:.1f}s URL={url} body='{body_text}'")
        if '请选择项目' in body_text or '虚拟私有云' in body_text or '新建' in body_text:
            break
        page.wait_for_timeout(500)

    print(f"\n最终 URL: {page.url}")

    # 检查是否需要选择项目
    body_text = page.evaluate("""() => document.body.innerText.substring(0, 200)""")
    print(f"Body文本: {body_text}")

    if '请选择项目' in body_text:
        print("\n检测到项目选择界面，尝试JS点击...")
        result = page.evaluate("""() => {
            // 找到第一个可点击的组织
            var msgs = document.querySelectorAll('.one-tree-msg-text');
            for (var i = 0; i < msgs.length; i++) {
                var text = msgs[i].innerText.trim();
                if (text && text.length > 0) {
                    msgs[i].click();
                    return 'clicked: ' + text;
                }
            }
            // 备选：点击任何包含autotest-org的元素
            var all = document.querySelectorAll('*');
            for (var i = 0; i < all.length; i++) {
                var text = (all[i].innerText || all[i].textContent || '').trim();
                if (text.includes('autotest-org') || text.includes('默认组织')) {
                    all[i].click();
                    return 'clicked2: ' + text;
                }
            }
            return 'not_found';
        }""")
        print(f"JS点击结果: {result}")
        page.wait_for_timeout(10000)
        print(f"点击后 URL: {page.url}")

    # 最终检查
    body_text2 = page.evaluate("""() => document.body.innerText.substring(0, 300)""")
    print(f"\n最终body文本: {body_text2}")

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

    page.screenshot(path='screenshots/vpc_final_project.png')
    browser.close()
