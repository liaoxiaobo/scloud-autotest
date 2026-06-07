#!/usr/bin/env python3
"""测试FIP连通性"""
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

    # goto FIP list
    page.goto(f'{BASE_URL}/vpc/#/vpc-floating-ip-list', wait_until='domcontentloaded')
    page.wait_for_timeout(5000)
    
    # 检查第一个FIP的状态
    rows = page.evaluate("""() => {
        var rows = document.querySelectorAll('table tr');
        var result = [];
        for (var i = 1; i < rows.length && i < 5; i++) {
            var cells = rows[i].querySelectorAll('td');
            if (cells.length > 5) {
                result.push({
                    ip: cells[1] ? cells[1].innerText.trim() : '',
                    project: cells[2] ? cells[2].innerText.trim() : '',
                    device: cells[3] ? cells[3].innerText.trim() : '',
                    mapped: cells[4] ? cells[4].innerText.trim() : '',
                    status: cells[5] ? cells[5].innerText.trim() : '',
                });
            }
        }
        return result;
    }""")
    
    print("FIP列表:")
    for r in rows:
        print(f"  IP={r['ip']} 项目={r['project']} 设备={r['device']} 映射={r['mapped']} 状态={r['status']}")

    # 查找操作按钮
    page.wait_for_timeout(2000)
    page.screenshot(path='screenshots/fip_list.png')
    browser.close()
