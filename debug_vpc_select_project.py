#!/usr/bin/env python3
"""验证选择项目后VPC页面是否正常"""
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

    # goto VPC
    page.goto(f'{BASE_URL}/vpc/#/vpc-network-list', wait_until='domcontentloaded')
    page.wait_for_timeout(5000)
    print(f"goto VPC 后 URL: {page.url}")

    # 检查是否需要选择项目
    body_text = page.evaluate("""() => document.body.innerText.substring(0, 200)""")
    print(f"Body文本: {body_text}")

    if '请选择项目' in body_text or '项目选择' in body_text:
        print("\n检测到项目选择界面，尝试点击第一个组织...")
        # 尝试点击第一个组织
        orgs = page.evaluate("""() => {
            var all = document.querySelectorAll('*');
            var results = [];
            for (var i = 0; i < all.length; i++) {
                var text = (all[i].innerText || all[i].textContent || '').trim();
                var s = window.getComputedStyle(all[i]);
                if (s.display !== 'none' && s.visibility !== 'hidden' && text && text.length < 50) {
                    results.push({tag: all[i].tagName, text: text, class: all[i].className});
                }
            }
            return results.slice(0, 30);
        }""")
        print("页面上可见元素:")
        for o in orgs:
            print(f"  [{o['tag']}] '{o['text']}' class='{o['class'][:40]}'")

        # 尝试点击第一个看起来像组织的元素
        try:
            # 先尝试点击"默认组织"
            default_org = page.get_by_text('默认组织', exact=False)
            if default_org.count() > 0:
                default_org.first.click()
                print("点击了'默认组织'")
                page.wait_for_timeout(5000)
                print(f"点击后 URL: {page.url}")
            else:
                # 尝试JS点击包含"autotest-org"的元素
                result = page.evaluate("""() => {
                    var all = document.querySelectorAll('div, span, a, li');
                    for (var i = 0; i < all.length; i++) {
                        var text = (all[i].innerText || all[i].textContent || '').trim();
                        if (text.includes('autotest-org') || text.includes('默认组织')) {
                            all[i].click();
                            return 'clicked: ' + text;
                        }
                    }
                    return 'not_found';
                }""")
                print(f"JS点击结果: {result}")
                page.wait_for_timeout(5000)
                print(f"点击后 URL: {page.url}")
        except Exception as e:
            print(f"点击失败: {e}")

    # 再次检查
    body_text2 = page.evaluate("""() => document.body.innerText.substring(0, 300)""")
    print(f"\n最终body文本: {body_text2}")

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

    # 查找"新建"
    has_new = any('新建' in b['text'] or '创建' in b['text'] for b in buttons)
    print(f"包含'新建/创建': {has_new}")

    page.screenshot(path='screenshots/vpc_after_project.png')

    browser.close()
