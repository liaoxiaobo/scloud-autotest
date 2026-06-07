#!/usr/bin/env python3
"""查看VPC overview页面的所有按钮"""
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

    # 直接goto /vpc/#/vpc-overview
    page.goto(f'{BASE_URL}/vpc/#/vpc-overview', wait_until='domcontentloaded')
    print(f"goto /vpc/#/vpc-overview 后 URL: {page.url}")

    # 等待loading消失
    for i in range(60):
        spinners = page.locator('.el-loading-spinner:visible').count()
        if spinners == 0:
            break
        page.wait_for_timeout(500)
    print(f"等待后 URL: {page.url}")
    page.screenshot(path='screenshots/vpc_overview.png')

    # 所有可见按钮
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button, [role="button"]')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            class: el.className,
            visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
        })).filter(b => b.visible && b.text);
    }""")
    print(f"\n所有可见按钮 ({len(buttons)} 个):")
    for b in buttons:
        print(f"  text='{b['text']}' class='{b['class'][:60]}'")

    # 查找所有交互元素
    all_elements = page.evaluate("""() => {
        var all = document.querySelectorAll('button, a, .el-dropdown, [role="button"]');
        var results = [];
        for (var i = 0; i < all.length; i++) {
            var text = (all[i].innerText || all[i].textContent || '').trim();
            var s = window.getComputedStyle(all[i]);
            if (s.display !== 'none' && s.visibility !== 'hidden' && text) {
                results.push({tag: all[i].tagName, text: text.substring(0, 50)});
            }
        }
        return results;
    }""")
    print(f"\n所有可见交互元素 ({len(all_elements)} 个):")
    for el in all_elements:
        print(f"  [{el['tag']}] '{el['text']}'")

    browser.close()
