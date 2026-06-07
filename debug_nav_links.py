#!/usr/bin/env python3
"""调试 console-page 上的导航链接选择器"""
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

    service = "虚拟私有云"

    # 策略1: get_by_role("link")
    try:
        links = page.get_by_role("link").filter(has_text=re.compile(service))
        print(f"策略1 - get_by_role('link').filter: count={links.count()}")
    except Exception as e:
        print(f"策略1 失败: {e}")

    # 策略2: locator("a")
    try:
        all_a = page.locator("a")
        print(f"策略2 - 所有a标签: count={all_a.count()}")
        for i in range(min(all_a.count(), 20)):
            try:
                text = all_a.nth(i).inner_text()
                visible = all_a.nth(i).is_visible()
                if service in text and visible:
                    print(f"  [匹配] [{i}] text='{text[:50]}' visible={visible}")
            except:
                pass
    except Exception as e:
        print(f"策略2 失败: {e}")

    # 策略3: get_by_text
    try:
        els = page.get_by_text(f"{service} VPC", exact=False)
        print(f"策略3 - get_by_text('{service} VPC'): count={els.count()}")
        for i in range(min(els.count(), 5)):
            try:
                tag = els.nth(i).evaluate("el => el.tagName")
                visible = els.nth(i).is_visible()
                print(f"  [{i}] tag={tag} visible={visible}")
            except:
                pass
    except Exception as e:
        print(f"策略3 失败: {e}")

    # 策略4: 通过JS查找
    try:
        result = page.evaluate("""() => {
            var links = Array.from(document.querySelectorAll('a'));
            return links.filter(el => {
                var text = (el.innerText || el.textContent || '').trim();
                return text.includes('虚拟私有云');
            }).map(el => ({
                tag: el.tagName,
                text: (el.innerText || el.textContent || '').trim().substring(0, 50),
                class: el.className,
                role: el.getAttribute('role')
            }));
        }""")
        print(f"策略4 - JS查找: {result}")
    except Exception as e:
        print(f"策略4 失败: {e}")

    # 策略5: 尝试点击
    try:
        result = page.evaluate("""() => {
            var links = Array.from(document.querySelectorAll('a'));
            var target = links.find(el => {
                var text = (el.innerText || el.textContent || '').trim();
                return text.includes('虚拟私有云 VPC');
            });
            if (target) {
                target.click();
                return 'clicked';
            }
            return 'not_found';
        }""")
        print(f"策略5 - JS点击: {result}")
        page.wait_for_timeout(3000)
        print(f"点击后 URL: {page.url}")
    except Exception as e:
        print(f"策略5 失败: {e}")

    browser.close()
