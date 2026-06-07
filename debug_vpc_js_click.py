#!/usr/bin/env python3
"""验证JS点击后的VPC页面状态"""
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

    print(f"登录后 URL: {page.url}")

    # 直接goto /vpc
    page.goto(f'{BASE_URL}/vpc', wait_until='domcontentloaded')
    page.wait_for_timeout(3000)
    print(f"goto /vpc 后 URL: {page.url}")

    # JS点击虚拟私有云VPC
    result = page.evaluate("""() => {
        var all = document.querySelectorAll('a');
        for (var i = 0; i < all.length; i++) {
            var text = (all[i].innerText || all[i].textContent || '').trim();
            if (text.includes('虚拟私有云 VPC')) {
                all[i].click();
                return 'clicked: ' + text;
            }
        }
        return 'not_found';
    }""")
    print(f"JS点击结果: {result}")

    # 轮询等待页面加载
    for i in range(60):
        url = page.url
        spinners = page.locator('.el-loading-spinner:visible').count()
        btns = page.locator('button').count()
        print(f"  t={i*0.5:.1f}s URL={url} spinners={spinners} buttons={btns}")
        if spinners == 0 and btns > 0:
            break
        page.wait_for_timeout(500)

    print(f"\n页面稳定后 URL: {page.url}")
    page.screenshot(path='screenshots/vpc_after_js_click.png')

    # 查找包含"新"的按钮
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
        })).filter(b => b.visible && b.text && ('新建' in b.text || '创建' in b.text));
    }""")
    print(f"包含'新建'的可见按钮 ({len(buttons)} 个):")
    for b in buttons:
        print(f"  >>> '{b['text']}'")

    browser.close()
