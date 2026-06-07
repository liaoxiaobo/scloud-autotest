#!/usr/bin/env python3
"""调试脚本4：验证刷新策略"""
import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://172.22.1.190:30000"
USERNAME = "admin"
PASSWORD = "keystone_sugon"


def login(page):
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_timeout(3000)
    page.get_by_placeholder("请输入登录账号").fill(USERNAME)
    page.get_by_placeholder("请输入登录密码").fill(PASSWORD)
    page.get_by_text("登 录").click()
    page.wait_for_url(re.compile(r".*#/(index|console-page)$"), timeout=20000)
    page.wait_for_timeout(2000)
    print(f"登录后 URL: {page.url}, 弹窗: {page.locator('.el-message-box').count() > 0}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)

        # 测试1: 直接刷新（不移除弹窗）
        print("=" * 60)
        print("测试1: 登录后直接刷新")
        page = context.new_page()
        login(page)
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        print(f"  刷新后 URL: {page.url}")
        print(f"  弹窗存在: {page.locator('.el-message-box').count() > 0}")

        # 测试2: 直接刷新2次
        print("\n测试2: 再刷新一次")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        print(f"  二次刷新后 URL: {page.url}")
        print(f"  弹窗存在: {page.locator('.el-message-box').count() > 0}")
        page.close()

        # 测试3: 新页面登录后移除弹窗再刷新
        print("\n" + "=" * 60)
        print("测试3: 移除弹窗后刷新")
        page2 = context.new_page()
        login(page2)
        page2.evaluate("""
            () => {
                document.querySelectorAll('.el-message-box__wrapper, .el-message-box, .v-modal').forEach(el => el.remove());
                document.body.classList.remove('el-popup-parent--hidden');
                document.body.style.overflow = '';
            }
        """)
        page2.wait_for_timeout(500)
        print(f"  移除后 URL: {page2.url}, 弹窗: {page2.locator('.el-message-box').count() > 0}")

        page2.reload(wait_until="domcontentloaded")
        page2.wait_for_timeout(3000)
        print(f"  刷新后 URL: {page2.url}")
        print(f"  弹窗存在: {page2.locator('.el-message-box').count() > 0}")

        # 测试4: 刷新后能否直接导航到VPC
        print("\n测试4: 刷新后通过顶部导航到VPC")
        try:
            page2.get_by_text("虚拟私有云 VPC", exact=False).first.click()
            page2.wait_for_timeout(3000)
            print(f"  点击后 URL: {page2.url}")
        except Exception as e:
            print(f"  点击失败: {e}")
        page2.close()

        # 测试5: 使用不同context
        print("\n" + "=" * 60)
        print("测试5: 新context登录")
        context2 = browser.new_context(ignore_https_errors=True)
        page3 = context2.new_page()
        login(page3)
        page3.reload(wait_until="domcontentloaded")
        page3.wait_for_timeout(3000)
        print(f"  刷新后 URL: {page3.url}")
        print(f"  弹窗存在: {page3.locator('.el-message-box').count() > 0}")
        page3.close()
        context2.close()

        browser.close()


if __name__ == "__main__":
    main()
