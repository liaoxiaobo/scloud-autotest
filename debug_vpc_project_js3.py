#!/usr/bin/env python3
"""尝试多种方式选择项目"""
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

    # goto VPC
    page.goto(f'{BASE_URL}/vpc/#/vpc-network-list', wait_until='domcontentloaded')

    # 等待项目选择界面出现
    for i in range(60):
        body_text = page.evaluate("""() => document.body.innerText.substring(0, 100)""")
        if '请选择项目' in body_text:
            break
        page.wait_for_timeout(500)

    print(f"URL: {page.url}")
    print(f"Body: {body_text}")

    # 策略1: 点击 .one-tree-msg（包含文本的容器）
    print("\n策略1: 点击 .one-tree-msg...")
    result = page.evaluate("""() => {
        var msgs = document.querySelectorAll('.one-tree-msg');
        for (var i = 0; i < msgs.length; i++) {
            var text = msgs[i].innerText.trim();
            if (text && text.length > 0) {
                msgs[i].click();
                return 'clicked msg: ' + text;
            }
        }
        return 'not_found';
    }""")
    print(f"结果: {result}")
    page.wait_for_timeout(5000)

    body1 = page.evaluate("""() => document.body.innerText.substring(0, 100)""")
    print(f"点击后body: {body1}")
    if '请选择项目' not in body1:
        print("成功！项目选择界面消失")
    else:
        print("仍然显示项目选择界面")

    # 策略2: 点击 .one-tree-li
    print("\n策略2: 点击 .one-tree-li...")
    result = page.evaluate("""() => {
        var items = document.querySelectorAll('.one-tree-li');
        for (var i = 0; i < items.length; i++) {
            var text = items[i].innerText.trim();
            if (text && text.length > 0) {
                items[i].click();
                return 'clicked li: ' + text;
            }
        }
        return 'not_found';
    }""")
    print(f"结果: {result}")
    page.wait_for_timeout(5000)

    body2 = page.evaluate("""() => document.body.innerText.substring(0, 100)""")
    print(f"点击后body: {body2}")

    # 策略3: 查找并点击 radio/checkbox
    print("\n策略3: 查找 radio/checkbox...")
    result = page.evaluate("""() => {
        var radios = document.querySelectorAll('input[type="radio"], input[type="checkbox"]');
        if (radios.length > 0) {
            radios[0].click();
            return 'clicked radio/checkbox: ' + radios.length + ' found';
        }
        return 'no_radio_found';
    }""")
    print(f"结果: {result}")
    page.wait_for_timeout(5000)

    body3 = page.evaluate("""() => document.body.innerText.substring(0, 100)""")
    print(f"点击后body: {body3}")

    # 策略4: 查找确定/确认按钮
    print("\n策略4: 查找确认按钮...")
    buttons = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('button, .el-button, a')).map(el => ({
            text: (el.innerText || el.textContent || '').trim().substring(0, 50),
            class: el.className
        })).filter(b => b.text.includes('确定') || b.text.includes('确认') || b.text.includes('选择'));
    }""")
    print(f"找到按钮: {buttons}")

    page.screenshot(path='screenshots/vpc_project_attempts.png')
    browser.close()
