"""Debug script: check what happens after clicking 新建 on VPN gateway list."""
import asyncio
from playwright.async_api import async_playwright
from sugon_web.config.config import Config
from sugon_web.common.base import BasePage


async def main():
    Config.load(host="172.22.1.190")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={"width": 1920, "height": 1080})
        page = await context.new_page()

        # Login
        await page.goto(Config.get("base_url"))
        await page.fill("input[placeholder='请输入用户名']", Config.get("username"))
        await page.fill("input[placeholder='请输入密码']", Config.get("password"))
        await page.click("button:has-text('登录')")
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(3000)

        # Navigate to VPN service
        base = BasePage(page)
        await base.goto_service("专有网络VPN")
        await base.goto_submenu("VPN网关")
        await page.wait_for_timeout(2000)

        print(f"Before click URL: {page.url}")

        # Click 新建
        btn = page.get_by_text("新建", exact=True).first
        print(f"Button count: {await btn.count()}")
        print(f"Button visible: {await btn.is_visible()}")
        print(f"Button bounding box: {await btn.bounding_box()}")

        await btn.click()
        await page.wait_for_timeout(3000)

        print(f"After click URL: {page.url}")

        # Check for dialog
        selectors = [
            ".el-dialog__wrapper:visible",
            ".el-dialog:visible",
            ".el-dialog__wrapper",
            ".el-dialog",
            ".dialog:visible",
            ".modal:visible",
            ".create-box",
            ".add-box",
            ".form-box",
        ]
        for sel in selectors:
            loc = page.locator(sel).first
            count = await loc.count()
            visible = await loc.is_visible() if count > 0 else False
            print(f"  {sel}: count={count}, visible={visible}")

        # Check for any visible overlay/popup
        all_visible = page.locator("*").filter(has_text="VPN网关")
        print(f"\nElements with 'VPN网关' text: {await all_visible.count()}")

        # Take screenshot
        await page.screenshot(path="debug_vpn_after_click.png")
        print("Screenshot saved to debug_vpn_after_click.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
