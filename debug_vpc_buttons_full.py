#!/usr/bin/env python3
"""全面检查 VPC 页面上的所有按钮"""
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

    # 导航到VPC
    page.evaluate("""() => {
        var links = document.querySelectorAll('a.tag');
        for (var i = 0; i < links.length; i++) {
            var text = (links[i].innerText || links[i].textContent || '').trim();
            if (text.includes('虚拟私有云 VPC')) {
                links[i].click();
                return 'clicked';
            }
        }
        return 'not_found';
    }""")
    page.wait_for_timeout(5000)
    print(f"URL: {page.url}")

    # 查找所有按钮和可点击元素
    all_elements = page.evaluate("""() => {
        var all = document.querySelectorAll('button, .el-button, a, [role="button"], .el-dropdown, .el-menu-item');
        var results = [];
        for (var i = 0; i < all.length; i++) {
            var text = (all[i].innerText || all[i].textContent || '').trim();
            var s = window.getComputedStyle(all[i]);
            if (s.display !== 'none' && s.visibility !== 'hidden') {
                results.push({
                    tag: all[i].tagName,
                    text: text.substring(0, 80),
                    class: all[i].className,
                    id: all[i].id
                });
            }
        }
        return results;
    }""")

    print(f"\n所有可见交互元素 ({len(all_elements)} 个):")
    for i, el in enumerate(all_elements):
        print(f"  [{i}] {el['tag']} id='{el['id']}' class='{el['class'][:60]}' text='{el['text']}'")

    # 特别查找包含"新"的元素
    print("\n包含'新'的元素:")
    for el in all_elements:
        if '新' in el['text'] or '建' in el['text'] or '创' in el['text']:
            print(f"  >>> {el['tag']} text='{el['text']}' class='{el['class'][:60]}'")

    # 查找工具栏区域的按钮
    print("\n工具栏/操作区域按钮:")
    toolbar = page.evaluate("""() => {
        var toolbars = document.querySelectorAll('.el-page-header__left, .operation-bar, .toolbar, .el-card__header, .table-toolbar, .page-header');
        var results = [];
        for (var j = 0; j < toolbars.length; j++) {
            var btns = toolbars[j].querySelectorAll('button, .el-button, a');
            for (var i = 0; i < btns.length; i++) {
                var text = (btns[i].innerText || btns[i].textContent || '').trim();
                if (text) {
                    results.push({
                        toolbar_class: toolbars[j].className,
                        tag: btns[i].tagName,
                        text: text.substring(0, 50)
                    });
                }
            }
        }
        return results;
    }""")
    for t in toolbar:
        print(f"  toolbar='{t['toolbar_class'][:40]}' {t['tag']} text='{t['text']}'")

    page.screenshot(path='screenshots/vpc_full.png')
    print('\nScreenshot saved')
    browser.close()
