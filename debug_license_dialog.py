#!/usr/bin/env python3
"""调试脚本：系统性测试许可证弹窗关闭方法"""
import re
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://172.22.1.190:30000"
USERNAME = "admin"
PASSWORD = "keystone_sugon"


def test_strategy(page, name, fn):
    """测试单个关闭策略"""
    print(f"\n{'='*60}")
    print(f"策略: {name}")
    print(f"{'='*60}")
    try:
        result = fn(page)
        time.sleep(2)
        has_dialog = page.locator(".el-message-box").count() > 0
        url = page.url
        print(f"  结果: dialog={has_dialog}, url={url}")
        if not has_dialog and "console-page" not in url:
            print(f"  ✓ 成功!")
            return True
        print(f"  ✗ 失败")
        return False
    except Exception as e:
        print(f"  ✗ 异常: {e}")
        return False


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(ignore_https_errors=True)
        page = context.new_page()

        # 登录
        print("导航到登录页...")
        page.goto(BASE_URL, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)

        print("填写登录信息...")
        page.get_by_placeholder("请输入登录账号").fill(USERNAME)
        page.get_by_placeholder("请输入登录密码").fill(PASSWORD)
        page.get_by_text("登 录").click()

        page.wait_for_url(re.compile(r".*#/(index|console-page)$"), timeout=20000)
        page.wait_for_timeout(2000)
        print(f"登录后 URL: {page.url}")

        if "console-page" not in page.url:
            print("没有弹窗，直接退出")
            browser.close()
            return

        # 打印弹窗结构
        print("\n弹窗结构:")
        info = page.evaluate("""
            () => {
                var box = document.querySelector('.el-message-box');
                var btns = document.querySelectorAll('.el-message-box button');
                return {
                    box_exists: !!box,
                    box_classes: box ? box.className : null,
                    buttons: Array.from(btns).map(b => ({
                        text: (b.innerText || b.textContent || '').trim(),
                        class: b.className,
                        disabled: b.disabled,
                        tagName: b.tagName
                    })),
                    vue_on_box: box ? !!box.__vue__ : false,
                    vue_on_wrapper: !!document.querySelector('.el-message-box__wrapper').__vue__
                };
            }
        """)
        print(f"  {info}")

        # 测试各种策略
        strategies = []

        # 1. 直接 JS click
        def s1(p):
            return p.evaluate("""
                () => {
                    var btn = document.querySelector('.el-message-box .el-button--primary');
                    if (btn) { btn.click(); return 'clicked'; }
                    return 'not_found';
                }
            """)
        strategies.append(("JS 直接 click", s1))

        # 2. Playwright click (带 force)
        def s2(p):
            btn = p.locator(".el-message-box .el-button--primary").first
            if btn.count() > 0:
                btn.click(force=True)
            return "clicked"
        strategies.append(("Playwright force click", s2))

        # 3. dispatchEvent click
        def s3(p):
            return p.evaluate("""
                () => {
                    var btn = document.querySelector('.el-message-box .el-button--primary');
                    if (!btn) return 'not_found';
                    var evt = new MouseEvent('click', {bubbles: true, cancelable: true, view: window});
                    btn.dispatchEvent(evt);
                    return 'dispatched';
                }
            """)
        strategies.append(("dispatchEvent click", s3))

        # 4. Vue handleAction
        def s4(p):
            return p.evaluate("""
                () => {
                    var box = document.querySelector('.el-message-box');
                    if (box && box.__vue__ && box.__vue__.handleAction) {
                        box.__vue__.handleAction('confirm');
                        return 'handleAction';
                    }
                    return 'not_found';
                }
            """)
        strategies.append(("Vue handleAction", s4))

        # 5. Vue callback
        def s5(p):
            return p.evaluate("""
                () => {
                    var box = document.querySelector('.el-message-box');
                    var vue = box ? box.__vue__ : null;
                    if (!vue) return 'no_vue';
                    var methods = [];
                    if (vue.callback) { vue.callback('confirm'); methods.push('callback'); }
                    if (vue.doClose) { vue.doClose(); methods.push('doClose'); }
                    if (vue.$emit) { vue.$emit('close'); methods.push('emit'); }
                    if (vue.visible !== undefined) { vue.visible = false; methods.push('visible'); }
                    return methods.join(',') || 'no_methods';
                }
            """)
        strategies.append(("Vue callback/doClose/emit/visible", s5))

        # 6. wrapper Vue callback
        def s6(p):
            return p.evaluate("""
                () => {
                    var wrapper = document.querySelector('.el-message-box__wrapper');
                    var vue = wrapper ? wrapper.__vue__ : null;
                    if (!vue) return 'no_vue';
                    var methods = [];
                    if (vue.handleAction) { vue.handleAction('confirm'); methods.push('handleAction'); }
                    if (vue.callback) { vue.callback('confirm'); methods.push('callback'); }
                    if (vue.doClose) { vue.doClose(); methods.push('doClose'); }
                    return methods.join(',') || 'no_methods';
                }
            """)
        strategies.append(("Wrapper Vue methods", s6))

        # 7. 关闭按钮 (X)
        def s7(p):
            btn = p.locator(".el-message-box__headerbtn").first
            if btn.count() > 0:
                btn.click(force=True)
            return "clicked"
        strategies.append(("关闭按钮(X)", s7))

        # 8. 点击弹窗容器获得焦点 + Enter
        def s8(p):
            p.locator(".el-message-box__wrapper").first.click()
            p.wait_for_timeout(500)
            p.keyboard.press("Tab")
            p.wait_for_timeout(200)
            p.keyboard.press("Enter")
            return "focus+tab+enter"
        strategies.append(("Focus + Tab + Enter", s8))

        # 9. 鼠标坐标点击
        def s9(p):
            btn = p.locator(".el-message-box .el-button--primary").first
            if btn.count() > 0:
                box = btn.bounding_box()
                if box:
                    p.mouse.click(box["x"] + box["width"]/2, box["y"] + box["height"]/2)
            return "mouse_click"
        strategies.append(("鼠标坐标点击", s9))

        # 10. 触发 keydown/keyup
        def s10(p):
            p.evaluate("""
                () => {
                    var btn = document.querySelector('.el-message-box .el-button--primary');
                    if (!btn) return 'not_found';
                    ['keydown', 'keypress', 'keyup'].forEach(type => {
                        var evt = new KeyboardEvent(type, {key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true});
                        btn.dispatchEvent(evt);
                    });
                    return 'keyboard_events';
                }
            """)
            return "keyboard_events"
        strategies.append(("触发 keyboard events", s10))

        # 11. 直接移除弹窗 + hashchange
        def s11(p):
            p.evaluate("""
                () => {
                    document.querySelectorAll('.el-message-box__wrapper, .el-message-box, .v-modal').forEach(el => el.remove());
                    document.body.classList.remove('el-popup-parent--hidden');
                    document.body.style.overflow = '';
                    document.body.style.paddingRight = '';
                    window.location.hash = '#/index';
                    window.dispatchEvent(new HashChangeEvent('hashchange'));
                    return 'done';
                }
            """)
            return "dom_removed"
        strategies.append(("移除DOM + hashchange", s11))

        # 运行所有策略
        success = False
        for name, fn in strategies:
            if test_strategy(page, name, fn):
                success = True
                break

        if not success:
            print("\n所有策略都失败了。尝试组合策略...")
            # 组合: Vue callback + click + hashchange
            page.evaluate("""
                () => {
                    var box = document.querySelector('.el-message-box');
                    var vue = box ? box.__vue__ : null;
                    if (vue) {
                        if (vue.callback) vue.callback('confirm');
                        if (vue.handleAction) vue.handleAction('confirm');
                    }
                    var btn = document.querySelector('.el-message-box .el-button--primary');
                    if (btn) btn.click();
                }
            """)
            page.wait_for_timeout(1000)
            page.evaluate("""
                () => {
                    document.querySelectorAll('.el-message-box__wrapper, .el-message-box, .v-modal').forEach(el => el.remove());
                    document.body.classList.remove('el-popup-parent--hidden');
                    document.body.style.overflow = '';
                    window.location.hash = '#/index';
                    window.dispatchEvent(new HashChangeEvent('hashchange'));
                }
            """)
            page.wait_for_timeout(3000)
            print(f"组合策略后: dialog={page.locator('.el-message-box').count() > 0}, url={page.url}")

        browser.close()


if __name__ == "__main__":
    main()
