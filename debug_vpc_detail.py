#!/usr/bin/env python3
"""详细检查goto /vpc后自动跳转的页面内容"""
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

    # 直接goto /vpc
    page.goto(f'{BASE_URL}/vpc', wait_until='domcontentloaded')
    print(f"goto /vpc 后 URL: {page.url}")

    # 等待自动跳转和loading消失
    for i in range(60):
        url = page.url
        spinners = page.locator('.el-loading-spinner:visible').count()
        btns = page.locator('button').count()
        print(f"  t={i*0.5:.1f}s URL={url} spinners={spinners} buttons={btns}")
        if spinners == 0 and btns > 0:
            break
        page.wait_for_timeout(500)

    print(f"\n最终 URL: {page.url}")
    page.screenshot(path='screenshots/vpc_final.png')

    # 所有可见元素（包括没有文本的）
    all_btns = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button, [role="button"]')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            class: el.className,
            tag: el.tagName,
            visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
        })).filter(b => b.visible);
    }""")
    print(f"\n所有可见按钮类元素 ({len(all_btns)} 个):")
    for b in all_btns:
        print(f"  [{b['tag']}] text='{b['text']}' class='{b['class'][:50]}'")

    # 所有可见链接
    all_links = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            href: el.href || '',
            visible: window.getComputedStyle(el).display !== 'none' && window.getComputedStyle(el).visibility !== 'hidden'
        })).filter(b => b.visible && b.text);
    }""")
    print(f"\n所有可见链接 ({len(all_links)} 个):")
    for l in all_links:
        print(f"  text='{l['text']}' href='{l['href'][:60]}'")

    # 页面所有可见文本
    body_text = page.evaluate("""() => {
        return document.body.innerText.substring(0, 500);
    }""")
    print(f"\n页面body文本(前500字符):\n{body_text}")

    browser.close()
