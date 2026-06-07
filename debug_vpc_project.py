#!/usr/bin/env python3
"""检查VPC overview页面上的项目选择弹窗"""
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

    # 先检查首页是否有项目选择弹窗
    has_project_select = page.locator('.el-dialog__wrapper:visible, .el-message-box__wrapper:visible').count()
    print(f"首页弹窗数量: {has_project_select}")

    # 直接goto /vpc/#/vpc-network-list
    print("\n=== 尝试直接访问 /vpc/#/vpc-network-list ===")
    page.goto(f'{BASE_URL}/vpc/#/vpc-network-list', wait_until='domcontentloaded')
    page.wait_for_timeout(10000)
    print(f"URL: {page.url}")

    # 检查弹窗
    dialogs = page.locator('.el-dialog__wrapper:visible, .el-message-box__wrapper:visible').count()
    print(f"弹窗数量: {dialogs}")

    # body文本
    body_text = page.evaluate("""() => document.body.innerText.substring(0, 500)""")
    print(f"Body文本: {body_text}")

    # 检查#cloud-menu-left
    menu_left = page.locator('#cloud-menu-left').count()
    print(f"#cloud-menu-left 存在: {menu_left > 0}")

    # 所有按钮
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
        })).filter(b => b.visible && b.text);
    }""")
    print(f"可见按钮 ({len(buttons)} 个):")
    for b in buttons:
        print(f"  '{b['text']}'")

    page.screenshot(path='screenshots/vpc_network_list.png')

    browser.close()
