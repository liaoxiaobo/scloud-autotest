import pytest
import re

class TestDialogInspect:
    def test_dialog(self, page):
        page.goto("https://172.22.1.190:30000", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        # Login
        page.get_by_placeholder("请输入登录账号").fill("admin")
        page.get_by_placeholder("请输入登录密码").fill("keystone_sugon")
        page.get_by_text("登 录").click()
        
        page.wait_for_url(re.compile(r".*#/(index|console-page)$"), timeout=20000)
        print(f"\n=== URL after login: {page.url} ===\n")
        
        if "console-page" in page.url:
            # Get dialog structure
            result = page.evaluate("""
                () => {
                    const wrapper = document.querySelector('.el-message-box__wrapper');
                    const box = document.querySelector('.el-message-box');
                    const modal = document.querySelector('.v-modal');
                    return {
                        wrapper_exists: !!wrapper,
                        box_exists: !!box,
                        modal_exists: !!modal,
                        box_html: box ? box.outerHTML : null,
                        all_buttons: Array.from(document.querySelectorAll('button, [role="button"], .el-button')).map(b => ({
                            text: (b.innerText || b.textContent || '').trim().substring(0, 20),
                            tag: b.tagName,
                            class: b.className,
                            disabled: b.disabled,
                        })),
                        body_children: document.body.children.length,
                    };
                }
            """)
            print(f"\n=== DIALOG STRUCTURE ===")
            import json
            print(json.dumps(result, ensure_ascii=False, indent=2))
            
            # Try Enter key
            page.keyboard.press("Enter")
            page.wait_for_timeout(2000)
            print(f"\n=== After Enter key, URL: {page.url} ===")
            print(f"=== dialog count: {page.locator('.el-message-box').count()} ===\n")
            
            # Try Escape key
            if "console-page" in page.url:
                page.keyboard.press("Escape")
                page.wait_for_timeout(2000)
                print(f"\n=== After Escape key, URL: {page.url} ===")
                print(f"=== dialog count: {page.locator('.el-message-box').count()} ===\n")
        
        assert True
