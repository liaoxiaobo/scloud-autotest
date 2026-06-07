#!/usr/bin/env python3
"""调试VPC导航后的页面状态"""
import re
from playwright.sync_api import sync_playwright

BASE_URL = 'https://172.22.1.190:30000'
USERNAME = 'admin'
PASSWORD = 'keystone_sugon'

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    context = browser.new_context(ignore_https_errors=True)
    page = context.new_page()

    # 登录
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
    print(f"goto /vpc 后 URL: {page.url}")

    # 等待前端路由设置hash并加载页面内容
    for i in range(60):
        url = page.url
        spinners = page.locator('.el-loading-spinner:visible').count()
        has_hash = '#' in url
        print(f"  t={i*0.5:.1f}s URL={url} hash={has_hash} spinners={spinners}")
        if has_hash and spinners == 0:
            break
        page.wait_for_timeout(500)

    print(f"\n页面稳定后 URL: {page.url}")

    # 截图
    page.screenshot(path='screenshots/vpc_after_goto.png')

    # 查找所有可见按钮
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button, [role="button"]')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            class: el.className,
            visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
        })).filter(b => b.visible && b.text);
    }""")
    print(f"\n可见按钮 ({len(buttons)} 个):")
    for b in buttons:
        print(f"  text='{b['text']}' class='{b['class'][:50]}'")

    # 查找包含"新"的元素
    print("\n包含'新'的可见元素:")
    for b in buttons:
        if '新' in b['text'] or '建' in b['text'] or '创' in b['text']:
            print(f"  >>> '{b['text']}'")

    # 检查页面标题/头部
    header = page.evaluate("""() => {
        var h = document.querySelector('.el-page-header__title, .page-title, h1, h2');
        return h ? h.innerText.trim() : 'no header found';
    }""")
    print(f"\n页面标题: {header}")

    # 检查是否有loading状态
    loading = page.locator('.el-loading-spinner').count()
    print(f"Loading spinners: {loading}")

    # 查看body所有可见文本
    all_text = page.evaluate("""() => {
        var all = document.querySelectorAll('*');
        var texts = [];
        for (var i = 0; i < all.length; i++) {
            var text = (all[i].innerText || all[i].textContent || '').trim();
            var s = window.getComputedStyle(all[i]);
            if (s.display !== 'none' && s.visibility !== 'hidden' && text && text.length < 200) {
                texts.push(text.substring(0, 100));
            }
        }
        return texts.slice(0, 30);
    }""")
    print(f"\n页面上前30个可见文本片段:")
    for t in all_text:
        print(f"  '{t}'")

    # 尝试JS点击导航链接
    print("\n尝试JS点击虚拟私有云VPC...")
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
    page.wait_for_timeout(5000)
    print(f"JS点击后 URL: {page.url}")

    # 再次检查按钮
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button, [role="button"]')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
        })).filter(b => b.visible && b.text);
    }""")
    print(f"JS点击后可见按钮 ({len(buttons)} 个):")
    for b in buttons:
        if '新' in b['text'] or '建' in b['text'] or '创' in b['text']:
            print(f"  >>> '{b['text']}'")

    browser.close()
