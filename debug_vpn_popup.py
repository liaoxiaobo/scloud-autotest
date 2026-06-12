"""Debug script: inspect what happens after VPN gateway form submission."""
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

        # Click 新建
        content = page.locator("#cloud-container-content")
        await content.get_by_text("新建", exact=True).first.click()
        await page.wait_for_timeout(3000)

        print(f"After click URL: {page.url}")

        # Fill form
        ctx = page.locator(".el-form").first

        # Name
        await ctx.get_by_placeholder("请输入名称").first.fill("vpn_debug_test")

        # Cluster - try dropdown
        try:
            form_items = ctx.locator(".el-form-item")
            for i in range(await form_items.count()):
                item = form_items.nth(i)
                label_elem = item.locator(".el-form-item__label").first
                if await label_elem.count() > 0:
                    text = await label_elem.inner_text()
                    if text.strip().lstrip("*").strip() == "集群":
                        dropdown = item.locator(".el-select .el-input__inner").first
                        await dropdown.click()
                        await page.wait_for_timeout(500)
                        dropdown_panel = page.locator(".el-select-dropdown:visible")
                        await dropdown_panel.get_by_text("Autotest", exact=False).first.click()
                        await page.wait_for_timeout(500)
                        break
        except Exception as e:
            print(f"Cluster select error: {e}")

        # Type - SSL
        try:
            form_items = ctx.locator(".el-form-item")
            for i in range(await form_items.count()):
                item = form_items.nth(i)
                label_elem = item.locator(".el-form-item__label").first
                if await label_elem.count() > 0:
                    text = await label_elem.inner_text()
                    if text.strip().lstrip("*").strip() == "类型":
                        dropdown = item.locator(".el-select .el-input__inner").first
                        await dropdown.click()
                        await page.wait_for_timeout(500)
                        dropdown_panel = page.locator(".el-select-dropdown:visible")
                        await dropdown_panel.get_by_text("SSL", exact=True).first.click()
                        await page.wait_for_timeout(500)
                        break
        except Exception as e:
            print(f"Type select error: {e}")

        # Resource pool
        try:
            form_items = ctx.locator(".el-form-item")
            for i in range(await form_items.count()):
                item = form_items.nth(i)
                label_elem = item.locator(".el-form-item__label").first
                if await label_elem.count() > 0:
                    text = await label_elem.inner_text()
                    if text.strip().lstrip("*").strip() == "资源池":
                        dropdown = item.locator(".el-select .el-input__inner").first
                        await dropdown.click()
                        await page.wait_for_timeout(500)
                        dropdown_panel = page.locator(".el-select-dropdown:visible")
                        await dropdown_panel.get_by_text("public_net", exact=False).first.click()
                        await page.wait_for_timeout(500)
                        break
        except Exception as e:
            print(f"Pool select error: {e}")

        # Connection type
        try:
            label_elem = ctx.get_by_text("连接类型", exact=True).first
            parent = label_elem.locator("xpath=../..")
            radio_group = parent.locator(".el-radio-group").first
            if await radio_group.count() == 0:
                parent = label_elem.locator("..")
                radio_group = parent.locator(".el-radio-group").first
            await radio_group.get_by_text("虚拟私有云", exact=True).first.click()
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"Connection type error: {e}")

        # VPC
        try:
            vpc_select = ctx.get_by_placeholder("请选择虚拟私有云").first
            await vpc_select.click()
            await page.wait_for_timeout(500)
            dropdown_panel = page.locator(".el-select-dropdown:visible")
            await dropdown_panel.locator(".el-select-dropdown__item").first.click()
            await page.wait_for_timeout(500)
        except Exception as e:
            print(f"VPC select error: {e}")

        # Flavor
        try:
            table = ctx.locator(".el-table").first
            rows = table.locator(".el-table__row")
            for i in range(await rows.count()):
                row = rows.nth(i)
                row_text = await row.inner_text()
                if "虚拟专用网络数据型" in row_text:
                    radio = row.locator(".el-radio__input, .el-radio").first
                    await radio.click()
                    await page.wait_for_timeout(500)
                    break
        except Exception as e:
            print(f"Flavor select error: {e}")

        # Scroll and click submit
        await page.evaluate("() => window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(500)

        # Check for any popup/toast before clicking
        print("\n--- Before submit ---")
        for sel in [".el-message__content", ".el-message", ".sugon-message", ".el-notification__content", ".one-message"]:
            loc = page.locator(sel)
            count = await loc.count()
            visible = await loc.is_visible() if count > 0 else False
            print(f"  {sel}: count={count}, visible={visible}")

        # Click submit
        await page.get_by_text("立即创建", exact=True).first.click()

        # Wait and check for popup
        await page.wait_for_timeout(500)
        print("\n--- 0.5s after submit ---")
        for sel in [".el-message__content", ".el-message", ".sugon-message", ".el-notification__content", ".one-message", ".el-message--success", ".el-message--error"]:
            loc = page.locator(sel)
            count = await loc.count()
            visible = await loc.is_visible() if count > 0 else False
            if count > 0:
                texts = []
                for i in range(min(count, 3)):
                    try:
                        t = await loc.nth(i).inner_text()
                        texts.append(t)
                    except:
                        pass
                print(f"  {sel}: count={count}, visible={visible}, texts={texts}")
            else:
                print(f"  {sel}: count={count}")

        await page.wait_for_timeout(2000)
        print(f"\nAfter submit URL: {page.url}")

        print("\n--- 2s after submit ---")
        for sel in [".el-message__content", ".el-message", ".sugon-message", ".el-notification__content", ".one-message", ".el-message--success", ".el-message--error"]:
            loc = page.locator(sel)
            count = await loc.count()
            visible = await loc.is_visible() if count > 0 else False
            if count > 0:
                texts = []
                for i in range(min(count, 3)):
                    try:
                        t = await loc.nth(i).inner_text()
                        texts.append(t)
                    except:
                        pass
                print(f"  {sel}: count={count}, visible={visible}, texts={texts}")
            else:
                print(f"  {sel}: count={count}")

        # Check for dialog
        print("\n--- Dialogs ---")
        for sel in [".el-dialog__wrapper:visible", ".sugon-dialog:visible", ".el-dialog:visible"]:
            loc = page.locator(sel).first
            count = await loc.count()
            visible = await loc.is_visible() if count > 0 else False
            if count > 0:
                text = await loc.inner_text()
                print(f"  {sel}: count={count}, visible={visible}, text={text[:200]}")
            else:
                print(f"  {sel}: count={count}")

        # Take screenshot
        await page.screenshot(path="debug_vpn_after_submit.png")
        print("\nScreenshot saved to debug_vpn_after_submit.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
