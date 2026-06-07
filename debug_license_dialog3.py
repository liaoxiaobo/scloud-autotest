#!/usr/bin/env python3
"""调试脚本3：测试移除弹窗后能否直接导航到服务页面"""
import re
from playwright.sync_api import sync_playwright

BASE_URL = "https://172.22.1.190:30000"
USERNAME = "admin"
PASSWORD = "keystone_sugon"


def remove_dialog(page):
    """移除弹窗"""
    page.evaluate("""
        () => {
            document.querySelectorAll('.el-message-box__wrapper, .el-message-box, .v-modal').forEach(el => el.remove());
            document.body.classList.remove('el-popup-parent--hidden');
            document.body.style.overflow = '';
            document.body.style.paddingRight = '';
        }
    """)
    page.wait_for_timeout(500)


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # 登录
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        page.get_by_placeholder("请输入登录账号").fill(USERNAME)
        page.get_by_placeholder("请输入登录密码").fill(PASSWORD)
        page.get_by_text("登 录").click()
        page.wait_for_url(re.compile(r".*#/(index|console-page)$"), timeout=20000)
        page.wait_for_timeout(2000)
        print(f"登录后 URL: {page.url}")

        # 移除弹窗
        remove_dialog(page)
        print(f"移除弹窗后 URL: {page.url}")

        # 测试1: 直接导航到 /#/vpc
        print("\n测试1: page.goto /#/vpc")
        page.goto(f"{BASE_URL}/#/vpc", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        print(f"  URL: {page.url}")
        # 检查是否有VPC相关元素
        has_vpc = page.locator("text=虚拟私有云").count() > 0 or page.locator("text=虚拟私有云 VPC").count() > 0
        print(f"  有VPC元素: {has_vpc}")

        # 如果还在console-page，尝试点击顶部导航
        if "console-page" in page.url:
            print("\n  尝试点击顶部导航...")
            # 尝试找到并点击 VPC 相关链接
            try:
                # 尝试各种选择器
                selectors = [
                    "text=虚拟私有云",
                    "text=VPC",
                    "[title='虚拟私有云']",
                    ".app-mainframe-header a",
                ]
                for sel in selectors:
                    els = page.locator(sel)
                    count = els.count()
                    if count > 0:
                        print(f"    找到 {sel}: {count} 个")
                        for i in range(min(count, 3)):
                            text = els.nth(i).inner_text()
                            print(f"      [{i}] text='{text[:50]}'")
            except Exception as e:
                print(f"    错误: {e}")

        # 测试2: 移除弹窗后刷新页面
        print("\n测试2: 移除弹窗后刷新")
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        print(f"  刷新后 URL: {page.url}")
        print(f"  弹窗存在: {page.locator('.el-message-box').count() > 0}")

        # 测试3: 检查 console-page 是否有链接到VPC
        print("\n测试3: 检查 console-page 的导航结构")
        remove_dialog(page)
        nav_info = page.evaluate("""
            () => {
                var links = Array.from(document.querySelectorAll('a, button'));
                return links.filter(el => {
                    var text = (el.innerText || el.textContent || '').toLowerCase();
                    return text.includes('vpc') || text.includes('虚拟私有云') || text.includes('云产品');
                }).map(el => ({
                    tag: el.tagName,
                    text: (el.innerText || el.textContent || '').trim().substring(0, 50),
                    class: el.className,
                    href: el.href || ''
                }));
            }
        """)
        print(f"  相关链接/按钮: {nav_info}")

        # 测试4: 尝试点击"虚拟私有云 VPC"
        print("\n测试4: 尝试点击虚拟私有云相关元素")
        try:
            # 从body_text中查找
            page.get_by_text("虚拟私有云 VPC", exact=False).first.click()
            page.wait_for_timeout(3000)
            print(f"  点击后 URL: {page.url}")
        except Exception as e:
            print(f"  点击失败: {e}")

        # 测试5: 尝试点击顶部菜单按钮
        print("\n测试5: 尝试点击大菜单按钮")
        try:
            btn = page.locator(".app-mainframe-menu-bt").first
            if btn.count() > 0:
                btn.click()
                page.wait_for_timeout(2000)
                print(f"  菜单展开后 URL: {page.url}")
                # 检查展开的菜单
                menu_items = page.evaluate("""
                    () => {
                        var items = Array.from(document.querySelectorAll('.el-menu-item, .el-submenu__title'));
                        return items.map(el => (el.innerText || el.textContent || '').trim()).filter(t => t);
                    }
                """)
                print(f"  菜单项: {menu_items[:10]}")
        except Exception as e:
            print(f"  失败: {e}")

        # 测试6: 直接修改window.location到服务URL
        print("\n测试6: 直接修改 window.location")
        remove_dialog(page)
        page.evaluate("window.location.href = 'https://172.22.1.190:30000/#/vpc'")
        page.wait_for_timeout(5000)
        print(f"  修改后 URL: {page.url}")
        print(f"  弹窗存在: {page.locator('.el-message-box').count() > 0}")

        browser.close()


if __name__ == "__main__":
    main()
