#!/usr/bin/env python3
"""深入分析项目选择UI结构"""
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

    page.goto(f'{BASE_URL}/vpc/#/vpc-network-list', wait_until='domcontentloaded')

    # 等待项目选择界面出现
    for i in range(60):
        body_text = page.evaluate("""() => document.body.innerText.substring(0, 100)""")
        if '请选择项目' in body_text:
            break
        page.wait_for_timeout(500)

    print(f"URL: {page.url}")

    # 点击 .one-tree-msg 展开树
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
    print(f"点击结果: {result}")
    page.wait_for_timeout(3000)

    # 详细分析树结构
    tree_info = page.evaluate("""() => {
        var items = document.querySelectorAll('.one-tree-li');
        var result = [];
        for (var i = 0; i < items.length; i++) {
            var li = items[i];
            var msg = li.querySelector('.one-tree-msg');
            var msgText = li.querySelector('.one-tree-msg-text');
            var arrow = li.querySelector('.one-tree-arrow');
            var radio = li.querySelector('input[type="radio"], .el-radio');
            var checkbox = li.querySelector('input[type="checkbox"], .el-checkbox');
            var childUl = li.querySelector('ul');

            result.push({
                index: i,
                liText: li.innerText.trim().substring(0, 100),
                msgText: msg ? msg.innerText.trim().substring(0, 50) : null,
                msgTextText: msgText ? msgText.innerText.trim() : null,
                hasArrow: !!arrow,
                arrowClass: arrow ? arrow.className : null,
                hasRadio: !!radio,
                hasCheckbox: !!checkbox,
                hasChildUl: !!childUl,
                childCount: childUl ? childUl.children.length : 0,
                liClass: li.className
            });
        }
        return result;
    }""")

    print(f"\n树结构分析 ({len(tree_info)} 个节点):")
    for item in tree_info:
        print(f"  [{item['index']}] msgText='{item['msgText']}' msgTextText='{item['msgTextText']}'")
        print(f"       hasArrow={item['hasArrow']} arrowClass='{item['arrowClass']}'")
        print(f"       hasRadio={item['hasRadio']} hasCheckbox={item['hasCheckbox']}")
        print(f"       hasChildUl={item['hasChildUl']} childCount={item['childCount']}")
        print(f"       liClass='{item['liClass'][:60]}'")
        print()

    # 查找组织下的项目
    all_divs = page.evaluate("""() => {
        var all = document.querySelectorAll('div, span, li');
        var results = [];
        for (var i = 0; i < all.length; i++) {
            var text = (all[i].innerText || all[i].textContent || '').trim();
            var s = window.getComputedStyle(all[i]);
            if (s.display !== 'none' && s.visibility !== 'hidden' && text) {
                if (text.includes('autotest') || text.includes('默认') || text.includes('项目')) {
                    results.push({tag: all[i].tagName, text: text.substring(0, 80), class: all[i].className.substring(0, 80)});
                }
            }
        }
        return results;
    }""")
    print("相关元素:")
    for d in all_divs[:30]:
        print(f"  [{d['tag']}] '{d['text']}' class='{d['class']}'")

    page.screenshot(path='screenshots/vpc_tree_detail.png')
    browser.close()
