#!/usr/bin/env python3
"""调试 VPC 页面上的按钮结构"""
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

    # 使用JS点击导航到VPC - 点击<a class="tag">元素
    result = page.evaluate("""() => {
        var links = document.querySelectorAll('a.tag');
        for (var i = 0; i < links.length; i++) {
            var text = (links[i].innerText || links[i].textContent || '').trim();
            if (text.includes('虚拟私有云 VPC')) {
                links[i].click();
                return 'clicked: ' + text;
            }
        }
        // 备选：查找所有包含文本的<a>
        var allLinks = document.querySelectorAll('a');
        for (var i = 0; i < allLinks.length; i++) {
            var text = (allLinks[i].innerText || allLinks[i].textContent || '').trim();
            if (text === '虚拟私有云 VPC') {
                allLinks[i].click();
                return 'clicked exact: ' + text;
            }
        }
        return 'not_found';
    }""")
    print(f"JS click result: {result}")
    page.wait_for_timeout(5000)
    print(f"VPC page URL: {page.url}")

    # 查找所有按钮
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button, a')).map(el => ({
            tag: el.tagName,
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            class: el.className
        })).filter(b => b.text.includes('新') || b.text.includes('建') || b.text.includes('创') || b.text.includes('添'));
    }""")
    print(f'Buttons: {buttons}')

    # 查找所有可见的按钮
    all_btns = page.locator('button, .el-button, a').all()
    print(f'Total interactive elements: {len(all_btns)}')
    for i, btn in enumerate(all_btns[:20]):
        try:
            text = btn.inner_text()
            visible = btn.is_visible()
            if text.strip() and visible:
                print(f'  [{i}] text="{text[:40]}" visible={visible}')
        except:
            pass

    page.screenshot(path='screenshots/vpc_real_page.png')
    print('Screenshot saved')
    browser.close()
