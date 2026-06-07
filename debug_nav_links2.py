#!/usr/bin/env python3
"""调试 console-page 上的导航链接选择器 - 增加等待时间"""
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
    page.wait_for_timeout(5000)  # 增加等待时间

    if 'console-page' in page.url:
        page.reload(wait_until='domcontentloaded')
        page.wait_for_timeout(5000)  # 增加等待时间

    print(f"当前 URL: {page.url}")
    print(f"弹窗存在: {page.locator('.el-message-box').count() > 0}")

    # 检查 iframe
    frames = page.frames
    print(f"总帧数: {len(frames)}")
    for i, f in enumerate(frames):
        print(f"  Frame[{i}]: {f.url[:80]}")

    # 检查 body 内容
    body_text = page.evaluate("() => document.body.innerText.substring(0, 300)")
    print(f"Body text: {body_text}")

    # 尝试查找所有可见元素
    all_visible = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('*')).filter(el => {
            var s = window.getComputedStyle(el);
            return s.display !== 'none' && s.visibility !== 'hidden';
        }).length;
    }""")
    print(f"可见元素数: {all_visible}")

    # JS查找虚拟私有云
    result = page.evaluate("""() => {
        var all = document.querySelectorAll('*');
        var matches = [];
        for (var i = 0; i < all.length; i++) {
            var text = (all[i].innerText || all[i].textContent || '').trim();
            if (text.includes('虚拟私有云') && text.length < 100) {
                matches.push({
                    tag: all[i].tagName,
                    class: all[i].className,
                    text: text.substring(0, 50),
                    clickable: all[i].tagName === 'A' || all[i].tagName === 'BUTTON' || all[i].onclick !== null
                });
            }
        }
        return matches;
    }""")
    print(f"包含'虚拟私有云'的元素: {result}")

    # 尝试直接点击第一个匹配的元素
    if result:
        first_match = result[0]
        print(f"尝试点击: {first_match}")
        page.evaluate("""() => {
            var all = document.querySelectorAll('*');
            for (var i = 0; i < all.length; i++) {
                var text = (all[i].innerText || all[i].textContent || '').trim();
                if (text.includes('虚拟私有云 VPC')) {
                    all[i].click();
                    return 'clicked: ' + all[i].tagName;
                }
            }
            return 'not_found';
        }""")
        page.wait_for_timeout(3000)
        print(f"点击后 URL: {page.url}")

    browser.close()
