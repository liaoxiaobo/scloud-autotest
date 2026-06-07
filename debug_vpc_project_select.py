#!/usr/bin/env python3
"""验证VPC页面是否需要先选择项目"""
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

    # 先检查是否有默认选中的项目
    # 尝试点击"默认组织"
    try:
        default_org = page.get_by_text('默认组织', exact=False)
        if default_org.count() > 0:
            print(f"找到'默认组织'元素: {default_org.count()} 个")
            default_org.first.click()
            page.wait_for_timeout(2000)
            print(f"点击默认组织后 URL: {page.url}")
    except Exception as e:
        print(f"点击默认组织失败: {e}")

    # 然后goto /vpc
    page.goto(f'{BASE_URL}/vpc', wait_until='domcontentloaded')
    print(f"goto /vpc 后 URL: {page.url}")

    # 等待
    for i in range(60):
        url = page.url
        spinners = page.locator('.el-loading-spinner:visible').count()
        print(f"  t={i*0.5:.1f}s URL={url} spinners={spinners}")
        if spinners == 0:
            break
        page.wait_for_timeout(500)

    print(f"\n最终 URL: {page.url}")
    page.screenshot(path='screenshots/vpc_after_project_select.png')

    # 检查body文本
    body_text = page.evaluate("""() => document.body.innerText.substring(0, 300)""")
    print(f"Body文本: {body_text}")

    # 查找"新建"
    has_new = '新建' in body_text or '创建' in body_text
    print(f"包含'新建/创建': {has_new}")

    # 所有按钮
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
        })).filter(b => b.visible && b.text);
    }""")
    print(f"\n可见按钮 ({len(buttons)} 个):")
    for b in buttons:
        print(f"  '{b['text']}'")

    browser.close()
