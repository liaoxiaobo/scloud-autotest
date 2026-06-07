#!/usr/bin/env python3
"""调试脚本2：检查移除弹窗后的页面状态"""
import re
import time
from playwright.sync_api import sync_playwright

BASE_URL = "https://172.22.1.190:30000"
USERNAME = "admin"
PASSWORD = "keystone_sugon"


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

        # 检查弹窗CSS
        print("\n弹窗CSS样式:")
        css = page.evaluate("""
            () => {
                var wrapper = document.querySelector('.el-message-box__wrapper');
                var box = document.querySelector('.el-message-box');
                var btn = document.querySelector('.el-message-box .el-button--primary');
                var modal = document.querySelector('.v-modal');
                function getStyles(el) {
                    if (!el) return null;
                    var s = window.getComputedStyle(el);
                    return {
                        display: s.display,
                        visibility: s.visibility,
                        opacity: s.opacity,
                        zIndex: s.zIndex,
                        pointerEvents: s.pointerEvents
                    };
                }
                return {
                    wrapper: getStyles(wrapper),
                    box: getStyles(box),
                    btn: getStyles(btn),
                    modal: getStyles(modal)
                };
            }
        """)
        print(f"  {css}")

        # 检查Vue实例
        print("\nVue实例信息:")
        vue_info = page.evaluate("""
            () => {
                var wrapper = document.querySelector('.el-message-box__wrapper');
                var vue = wrapper ? wrapper.__vue__ : null;
                if (!vue) return 'no_vue';
                var info = {
                    methods: Object.keys(vue).filter(k => typeof vue[k] === 'function'),
                    props: vue.$options && vue.$options.propsData ? Object.keys(vue.$options.propsData) : [],
                    data: Object.keys(vue.$data || {}),
                    visible: vue.visible
                };
                return info;
            }
        """)
        print(f"  {vue_info}")

        # 移除弹窗
        print("\n移除弹窗...")
        page.evaluate("""
            () => {
                document.querySelectorAll('.el-message-box__wrapper, .el-message-box, .v-modal, .el-popup-parent--hidden').forEach(el => el.remove());
                document.body.classList.remove('el-popup-parent--hidden');
                document.body.style.overflow = '';
                document.body.style.paddingRight = '';
            }
        """)
        page.wait_for_timeout(1000)
        print(f"移除后 dialog 存在: {page.locator('.el-message-box').count() > 0}")
        print(f"移除后 URL: {page.url}")

        # 检查页面内容
        print("\n移除弹窗后的页面内容:")
        content = page.evaluate("""
            () => {
                return {
                    body_children: document.body.children.length,
                    app_exists: !!document.querySelector('#app'),
                    menu_exists: !!document.querySelector('#cloud-menu-left'),
                    header_exists: !!document.querySelector('.app-mainframe-header'),
                    sidebar_exists: !!document.querySelector('.app-mainframe-sidebar'),
                    main_exists: !!document.querySelector('.app-mainframe-main'),
                    body_text: document.body.innerText.substring(0, 200)
                };
            }
        """)
        print(f"  {content}")

        # 尝试修改 hash 并触发 hashchange
        print("\n尝试修改 hash 到 /#/index...")
        page.evaluate("""
            () => {
                window.location.hash = '#/index';
                window.dispatchEvent(new HashChangeEvent('hashchange', {
                    oldURL: window.location.href.replace('#/index', '#/console-page'),
                    newURL: window.location.href
                }));
            }
        """)
        page.wait_for_timeout(3000)
        print(f"hashchange 后 URL: {page.url}")

        # 检查 no-permission 页面
        if "no-permission" in page.url:
            print("\n在 no-permission 页面:")
            np_content = page.evaluate("""
                () => {
                    return {
                        body_text: document.body.innerText,
                        has_back_btn: document.body.innerText.includes('返回') || document.body.innerText.includes('首页')
                    };
                }
            """)
            print(f"  {np_content}")

        # 尝试直接 goto index
        print("\n尝试 page.goto 到 index...")
        page.goto(f"{BASE_URL}/#/index", wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        print(f"goto 后 URL: {page.url}")

        # 检查 console-page 页面源码
        print("\nconsole-page 的 HTML 结构:")
        html = page.evaluate("""
            () => {
                var app = document.querySelector('#app');
                return app ? app.outerHTML.substring(0, 500) : 'no #app';
            }
        """)
        print(f"  {html}")

        # 检查是否有路由守卫
        print("\n检查 Vue Router:")
        router = page.evaluate("""
            () => {
                var app = document.querySelector('#app');
                var vue = app ? app.__vue__ : null;
                if (!vue) return 'no_vue_on_app';
                var router = vue.$router;
                if (!router) return 'no_router';
                return {
                    current_route: router.currentRoute ? router.currentRoute.path : 'unknown',
                    before_hooks: router.beforeHooks ? router.beforeHooks.length : 0,
                    resolve_hooks: router.resolveHooks ? router.resolveHooks.length : 0
                };
            }
        """)
        print(f"  {router}")

        browser.close()


if __name__ == "__main__":
    main()
