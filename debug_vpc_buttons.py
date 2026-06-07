#!/usr/bin/env python3
"""调试 VPC 页面按钮结构"""
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

    page.goto(f'{BASE_URL}/#/vpc', wait_until='domcontentloaded')
    page.wait_for_timeout(5000)
    print(f'VPC page URL: {page.url}')

    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, a, .el-button')).map(el => ({
            tag: el.tagName,
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            class: el.className
        })).filter(b => b.text.includes('新') || b.text.includes('建') || b.text.includes('创'));
    }""")
    print(f'Buttons with 新/建/创: {buttons}')

    all_btns = page.locator('button, .el-button').all()
    print(f'Total buttons: {len(all_btns)}')
    for i, btn in enumerate(all_btns[:15]):
        try:
            text = btn.inner_text()
            visible = btn.is_visible()
            if text.strip():
                print(f'  [{i}] text="{text[:40]}" visible={visible}')
        except:
            pass

    page.screenshot(path='screenshots/vpc_page_debug.png')
    print('Screenshot saved')
    browser.close()
