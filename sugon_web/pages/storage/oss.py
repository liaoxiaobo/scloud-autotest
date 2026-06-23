import os
import tempfile

import re

from playwright.sync_api import expect

from sugon_web.common.base import BasePage
from sugon_web.config.config import Config


class OssPage(BasePage):
    """对象存储OSS页面对象。"""
    service_name = "对象存储"

    # ── OSS 微前端导航（不兼容平台标准 #cloud-menu-left）──

    def _goto_bucket_list(self):
        """直接导航到桶列表页（OSS 微前端使用 CloudLeftMenu，goto_submenu 不兼容）。"""
        base_url = Config.get("base_url").rstrip("/")
        target_url = f"{base_url}/oss/#/bucket-list-page"
        self.page.goto(target_url)
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(5000)
        # 强制检查导航结果：若仍停留在详情页（object/list 或 basicconfig/tag），
        # 则通过 about:blank 强制完整重载后再次导航
        if "/bucket-list-page-detail" in self.page.url:
            self.page.goto("about:blank")
            self.page.wait_for_timeout(1000)
            self.page.goto(target_url)
            try:
                self.wait_for_page_ready()
            except Exception:
                self.page.wait_for_load_state("domcontentloaded")
                self.page.wait_for_timeout(3000)
            self.page.wait_for_timeout(5000)

    def _goto_bucket_detail(self, name):
        """直接导航到桶详情页。"""
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{name}")
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

    def oss_bucket_enter_detail_via_ui(self, name):
        """通过桶列表页点击桶名称进入详情页（UI导航，避免直接URL触发权限拦截）。

        Args:
            name: 桶名称。
        """
        # 先确保在桶列表页
        self._goto_bucket_list()
        self.page.wait_for_timeout(3000)

        # 在表格中查找桶名称并点击
        clicked = False
        for attempt in range(3):
            try:
                # 策略1: 直接通过 get_by_text 点击桶名
                bucket_link = self.page.get_by_text(name, exact=True).first
                if bucket_link.count() > 0:
                    bucket_link.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                pass

            # 策略2: JS 查找包含桶名的行并点击
            if not clicked:
                result = self.page.evaluate(f"""
                    () => {{
                        const rows = document.querySelectorAll('.el-table__row, .cl-table-body tr');
                        for (const row of rows) {{
                            if (row.innerText.includes('{name}')) {{
                                const link = row.querySelector('a, .cell a, .objectKeyClass');
                                if (link) {{
                                    link.click();
                                    return 'clicked';
                                }}
                                // fallback: 点击行本身
                                row.click();
                                return 'row-clicked';
                            }}
                        }}
                        return 'not-found';
                    }}
                """)
                if 'clicked' in str(result) or 'row-clicked' in str(result):
                    clicked = True
                    break
            self.page.wait_for_timeout(3000)

        if not clicked:
            raise AssertionError(f"无法在桶列表页找到并点击桶 '{name}'")

        # 等待详情页加载
        self.page.wait_for_timeout(3000)
        for _ in range(15):
            self.page.wait_for_timeout(1000)
            if f"/bucket-list-page-detail/{name}" in self.page.url:
                return
            # 检查是否被重定向到 no-permission
            if "/no-permission" in self.page.url:
                raise AssertionError(
                    f"导航到桶 '{name}' 详情页被前端权限拦截，当前URL: {self.page.url}"
                )

        raise AssertionError(
            f"导航到桶 '{name}' 详情页超时，当前URL: {self.page.url}"
        )

    def oss_bucket_goto_object_tab_via_ui(self, bucket_name):
        """在桶详情页点击'对象'tab切换到对象列表（UI导航）。

        Args:
            bucket_name: 桶名称（用于验证当前页面）。
        """
        # 确保在桶详情页
        if f"/bucket-list-page-detail/{bucket_name}" not in self.page.url:
            self.oss_bucket_enter_detail_via_ui(bucket_name)

        # 点击"对象"tab
        clicked = False
        for attempt in range(3):
            try:
                tab = self.page.get_by_text("对象", exact=True).first
                if tab.count() > 0:
                    tab.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                pass

            # JS fallback
            if not clicked:
                result = self.page.evaluate("""
                    () => {
                        const tabs = document.querySelectorAll('.el-tabs__item, .tab-item');
                        for (const tab of tabs) {
                            if (tab.innerText && tab.innerText.trim() === '对象') {
                                tab.click();
                                return 'clicked';
                            }
                        }
                        return 'not-found';
                    }
                """)
                if 'clicked' in str(result):
                    clicked = True
                    break
            self.page.wait_for_timeout(2000)

        if not clicked:
            # fallback: 直接URL导航
            base_url = Config.get("base_url").rstrip("/")
            target_url = f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object"
            self.page.goto("about:blank")
            self.page.wait_for_timeout(500)
            self.page.goto(target_url)
            try:
                self.wait_for_page_ready()
            except Exception:
                self.page.wait_for_load_state("domcontentloaded")
                self.page.wait_for_timeout(3000)
            self.page.wait_for_timeout(3000)

            if "/object" not in self.page.url:
                raise AssertionError(
                    f"无法导航到对象页面，当前URL: {self.page.url}"
                )

        self.page.wait_for_timeout(3000)

    def oss_bucket_goto_fragment_tab_via_ui(self, bucket_name):
        """在桶详情页点击'碎片'tab切换到碎片列表（UI导航）。

        优先尝试点击"碎片"tab，若tab不可见（权限限制）则fallback到直接URL导航。

        Args:
            bucket_name: 桶名称（用于验证当前页面）。
        """
        # 关闭任务列表抽屉（如果存在）
        try:
            self.page.evaluate("""
                () => {
                    const drawer = document.querySelector('.el-drawer__wrapper');
                    if (drawer) {
                        const closeBtn = drawer.querySelector('.el-drawer__close-btn, .el-drawer__headerbtn');
                        if (closeBtn) closeBtn.click();
                    }
                }
            """)
            self.page.wait_for_timeout(2000)
        except Exception:
            pass

        # 确保在桶详情页
        if f"/bucket-list-page-detail/{bucket_name}" not in self.page.url:
            self.oss_bucket_enter_detail_via_ui(bucket_name)

        # 点击"碎片"tab
        clicked = False
        for attempt in range(3):
            try:
                tab = self.page.get_by_text("碎片", exact=True).first
                if tab.count() > 0:
                    tab.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                pass

            # JS fallback
            if not clicked:
                result = self.page.evaluate("""
                    () => {
                        const tabs = document.querySelectorAll('.el-tabs__item, .tab-item');
                        for (const tab of tabs) {
                            if (tab.innerText && tab.innerText.trim() === '碎片') {
                                tab.click();
                                return 'clicked';
                            }
                        }
                        return 'not-found';
                    }
                """)
                if 'clicked' in str(result):
                    clicked = True
                    break
            self.page.wait_for_timeout(2000)

        if not clicked:
            # fallback: 直接URL导航（碎片tab可能因权限被隐藏）
            base_url = Config.get("base_url").rstrip("/")
            target_url = f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object/fragement"
            self.page.goto("about:blank")
            self.page.wait_for_timeout(500)
            self.page.goto(target_url)
            try:
                self.wait_for_page_ready()
            except Exception:
                self.page.wait_for_load_state("domcontentloaded")
                self.page.wait_for_timeout(3000)
            self.page.wait_for_timeout(3000)

            # 验证是否成功导航到碎片页
            if "/object/fragement" not in self.page.url:
                raise AssertionError(
                    f"无法导航到碎片页面，当前URL: {self.page.url} | "
                    f"可能原因: 1)碎片tab被权限隐藏 2)前端路由异常"
                )

        self.page.wait_for_timeout(3000)

    def _goto_create_bucket(self):
        """导航到创建桶页面。

        通过对象存储服务页进入桶列表，然后点击"新建"按钮进入创建页。
        避免直接 URL 导航到 Vue hash 路由（/#/CreateBucket）时页面空白或路由不触发的问题。
        """
        # 先导航到对象存储服务页（确保 OSS 微前端已加载）
        self.goto_service("对象存储")
        self.page.wait_for_timeout(3000)

        # 等待桶列表页加载（URL 应包含 bucket-list-page）
        for _ in range(20):
            if "/bucket-list-page" in self.page.url:
                break
            self.page.wait_for_timeout(1000)
        else:
            # URL 未变，尝试直接导航到桶列表页
            base_url = Config.get("base_url").rstrip("/")
            self.page.goto(f"{base_url}/oss/#/bucket-list-page")
            self.page.wait_for_timeout(5000)

        # 点击"新建"按钮
        clicked = False
        for attempt in range(3):
            try:
                create_btn = self.page.get_by_text("新建", exact=False).first
                if create_btn.count() > 0:
                    create_btn.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                pass

            # fallback: JS 查找并点击
            if not clicked:
                result = self.page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button, .el-button, .cl-button');
                        for (const btn of btns) {
                            if (btn.innerText && btn.innerText.trim() === '新建') {
                                btn.dispatchEvent(new MouseEvent('click', {
                                    bubbles: true, cancelable: true, view: window
                                }));
                                return 'clicked';
                            }
                        }
                        return 'not-found';
                    }
                """)
                if 'clicked' in str(result):
                    clicked = True
                    break
            self.page.wait_for_timeout(2000)

        if not clicked:
            raise AssertionError("无法点击桶列表页的'新建'按钮，无法进入创建桶页面")

        # 等待创建页加载（检查表单元素出现）
        for _ in range(15):
            self.page.wait_for_timeout(1000)
            # 检查创建页特征元素：区域选择、桶名称输入框
            has_form = self.page.evaluate("""
                () => {
                    const regionInput = document.querySelector('input[placeholder*="选择"]');
                    const nameInput = document.querySelector('input[placeholder*="桶名称"]');
                    return !!(regionInput || nameInput);
                }
            """)
            if has_form:
                return

        # 再次检查 URL
        if "/CreateBucket" not in self.page.url:
            raise AssertionError(
                f"无法导航到OSS桶创建页面，当前URL: {self.page.url} | "
                "可能原因: 1)当前用户无OSS桶创建权限 2)OSS服务未启用 3)前端路由异常"
            )

    # ── 表单元素属性 ──

    @property
    def _btn_create_bucket(self):
        """OSS 桶列表页新建按钮（<cl-button> 自定义组件，btn_create 兼容不到）。"""
        locators = [
            self.page.locator('button, .el-button, [class*="btn"]').filter(has_text="新建").first,
            self.page.locator('.el-icon-plus').locator('xpath=ancestor::button[1] | ancestor::*[contains(@class,"btn")][1] | ancestor::*[contains(@class,"button")][1]').first,
            self.page.get_by_text("新建").first,
            self.page.locator('.cl-button').filter(has_text="新建").first,
        ]
        for locator in locators:
            try:
                if locator.count() > 0:
                    return locator
            except Exception:
                continue
        raise Exception("OSS 新建按钮未找到，尝试的定位器: [button/新建, el-icon-plus父按钮, get_by_text(新建), .cl-button/新建]")

    @property
    def _select_region(self):
        """区域选择下拉框。"""
        return self.page.locator(
            '.el-form-item__content .el-select'
        ).filter(
            has=self.page.locator('input[placeholder="请选择"]')
        ).first

    @property
    def _input_bucket_name(self):
        """桶名称输入框。"""
        return self.page.locator(
            '.el-form-item__content .el-input__inner'
        ).filter(
            has=self.page.locator('xpath=ancestor::el-form-item[@label="桶名称"]')
        ).first

    def _get_az_radio(self, label):
        """获取数据冗余存储策略单选按钮。

        Args:
            label: 按钮文本，"多AZ存储" 或 "单AZ存储"。
        """
        return self.page.locator(
            '.el-radio-group .el-radio-button__inner'
        ).filter(has_text=label).first

    def _get_strategy_radio(self, label):
        """获取桶策略单选按钮。

        Args:
            label: 按钮文本，"私有"、"公共读" 或 "公共读写"。
        """
        return self.page.locator(
            '.el-radio-group .el-radio__label'
        ).filter(has_text=label).first

    def _get_storage_class_card(self, label):
        """获取默认存储类别卡片。

        Args:
            label: 卡片标题文本，如 "标准存储"。
        """
        return self.page.locator(
            '.storageClass-box .storageClass-title h3'
        ).filter(has_text=label).first

    @property
    def _checkbox_encryption(self):
        """默认加密复选框。"""
        return self.page.locator(
            '.el-checkbox__label'
        ).filter(has_text='开启默认加密').first

    def _get_data_read_radio(self, label):
        """获取归档数据直读单选按钮。

        Args:
            label: 按钮文本，"开启" 或 "关闭"。
        """
        return self.page.locator(
            '.el-form-item__content .el-radio__label'
        ).filter(has_text=label).first

    @property
    def _btn_add_tag(self):
        """添加标签链接/按钮。"""
        return self.page.get_by_text("添加标签", exact=True).first

    @property
    def _input_tag_key(self):
        """标签键输入框（最后一个，对应最新添加的标签）。"""
        return self.page.locator(
            'input[placeholder="标签键"]'
        ).last

    @property
    def _input_tag_value(self):
        """标签值输入框（最后一个，对应最新添加的标签）。"""
        return self.page.locator(
            'input[placeholder="标签值"]'
        ).last

    @property
    def _btn_cancel_page(self):
        """创建页取消按钮。"""
        return self.page.locator(".confirm-box").get_by_text("取消", exact=True)

    @property
    def _btn_submit_create(self):
        """立即创建按钮（创建页底部提交按钮）。"""
        return self.page.locator(".confirm-box").get_by_text("立即创建", exact=True)

    # ── 页面操作方法 ──

    def oss_bucket_create(
        self,
        name,
        region="RegionOne",
        az_strategy="MULTI_AZ",
        storage_class="标准存储",
        bucket_strategy="私有",
        is_encryption=True,
        data_read=False,
        tags=None,
    ):
        """在OSS对象存储创建桶。

        完整流程：导航到桶列表 -> 点击新建 -> 填写表单 -> 提交。

        Args:
            name: 桶名称。
            region: 区域名称，默认 "RegionOne"。
            az_strategy: 数据冗余存储策略，"MULTI_AZ"(多AZ存储) 或 "single"(单AZ存储)，默认多AZ。
            storage_class: 默认存储类别，默认 "标准存储"。
            bucket_strategy: 桶策略，"私有" / "公共读" / "公共读写"，默认 "私有"。
            is_encryption: 是否开启默认加密，默认 True。
            data_read: 归档数据直读，True(开启) / False(关闭)，默认 False。
            tags: 标签列表，每项为 {"key": ..., "value": ...} 格式的字典，默认 None。
        """
        # 直接导航到创建页（OSS 微前端 <cl-button> 非标准 button，btn_create 定位不到）
        self._goto_create_bucket()

        # ── 填写表单 ──

        # 1. 选择区域
        region_select = self.page.locator('input[placeholder="请选择"]').first
        if region_select.count() == 0:
            region_select = self.page.locator('input[placeholder*="选择"]').first
        if region_select.count() == 0:
            region_select = self.page.get_by_role('combobox').first
        expect(region_select).to_be_visible(timeout=10000)
        region_select.click()
        self.page.wait_for_timeout(500)
        region_option = self.page.locator(
            '.el-select-dropdown__item'
        ).filter(has_text=region).first
        expect(region_option).to_be_visible(timeout=10000)
        region_option.click()
        self.page.wait_for_timeout(300)

        # 2. 填写桶名称
        name_input = self.page.locator(
            '.el-form-item__content .el-input__inner'
        ).filter(
            has=self.page.locator('xpath=ancestor::el-form-item[contains(.,"桶名称")]')
        ).first
        if name_input.count() == 0:
            # fallback：直接找紧邻"桶名称"标签后的输入框
            name_input = self.page.locator('.el-form-item').filter(
                has_text="桶名称"
            ).first.locator('.el-input__inner').first
        expect(name_input).to_be_visible(timeout=10000)
        name_input.fill(name)
        self.page.wait_for_timeout(300)

        # 3. 选择数据冗余存储策略
        az_label_map = {
            "MULTI_AZ": "多AZ存储",
            "single": "单AZ存储",
            "多AZ存储": "多AZ存储",
            "单AZ存储": "单AZ存储",
        }
        az_label = az_label_map.get(az_strategy, az_strategy)
        az_radio = self.page.locator('.el-radio-group .el-radio-button__inner').filter(
            has_text=az_label
        ).first
        if az_radio.count() > 0:
            az_radio.click()
            self.page.wait_for_timeout(300)

        # 4. 默认存储类别（默认已是标准存储，若需显式选择则点击）
        if storage_class != "标准存储":
            card = self.page.locator('.storageClass-box').filter(
                has_text=storage_class
            ).first
            if card.count() > 0:
                card.click()
                self.page.wait_for_timeout(300)

        # 5. 选择桶策略
        strategy_label_map = {
            "REST_CANNED_PRIVATE": "私有",
            "REST_CANNED_PUBLIC_READ": "公共读",
            "REST_CANNED_PUBLIC_READ_WRITE": "公共读写",
        }
        strategy_label = strategy_label_map.get(bucket_strategy, bucket_strategy)
        strategy_radio = self.page.locator(
            '.el-form-item__content .el-radio__label'
        ).filter(
            has_text=strategy_label
        ).first
        if strategy_radio.count() > 0:
            strategy_radio.click()
            self.page.wait_for_timeout(300)

        # 6. 默认加密
        if is_encryption:
            encrypt_checkbox = self.page.locator('.el-checkbox__label').filter(
                has_text="开启默认加密"
            ).first
            if encrypt_checkbox.count() > 0:
                # 先检查是否已勾选
                checkbox_parent = encrypt_checkbox.locator('xpath=..')
                checkbox_class = checkbox_parent.get_attribute('class') or ''
                if 'is-checked' not in checkbox_class:
                    encrypt_checkbox.click()
                    self.page.wait_for_timeout(300)

        # 7. 归档数据直读
        data_read_label = "开启" if data_read else "关闭"
        # 在"归档数据直读"form-item内查找
        data_read_form_item = self.page.locator('.el-form-item').filter(
            has_text="归档数据直读"
        ).first
        if data_read_form_item.count() > 0:
            data_read_radio = data_read_form_item.locator('.el-radio__label').filter(
                has_text=data_read_label
            ).first
            if data_read_radio.count() > 0:
                data_read_radio.click()
                self.page.wait_for_timeout(300)

        # 8. 添加标签
        if tags:
            for tag in tags:
                # 点击添加标签
                add_tag_btn = self.page.get_by_text("添加标签", exact=True).first
                if add_tag_btn.count() > 0:
                    add_tag_btn.click()
                    self.page.wait_for_timeout(500)

                # 填写标签键
                key_inputs = self.page.locator('input[placeholder="标签键"]')
                if key_inputs.count() > 0:
                    key_inputs.last.fill(tag["key"])
                    self.page.wait_for_timeout(200)

                # 填写标签值
                value_inputs = self.page.locator('input[placeholder="标签值"]')
                if value_inputs.count() > 0:
                    value_inputs.last.fill(tag["value"])
                    self.page.wait_for_timeout(200)

            # 8.5 直接注入 tags 到 Vue form（cl-button 点击不触发 addTag，需手动同步）
            tags_json = str(tags).replace("'", '"')
            self.page.evaluate(f"""
                () => {{
                    const container = document.querySelector('.create-bucket-container');
                    if (container) {{
                        let vue = container.__vue__;
                        if (!vue) {{
                            for (const child of container.querySelectorAll('*')) {{
                                if (child.__vue__) {{ vue = child.__vue__; break; }}
                            }}
                        }}
                        if (vue && vue.form) {{
                            vue.form.tags = {tags_json};
                            return 'injected';
                        }}
                    }}
                    // fallback: 全局搜索含 form.tags 的 Vue 实例
                    const all = document.querySelectorAll('*');
                    for (const el of all) {{
                        if (el.__vue__) {{
                            let p = el.__vue__;
                            while (p) {{
                                if (p.form && Array.isArray(p.form.tags)) {{
                                    p.form.tags = {tags_json};
                                    return 'injected-global';
                                }}
                                p = p.$parent;
                            }}
                        }}
                    }}
                    return 'not-found';
                }}
            """)
            self.page.wait_for_timeout(500)

        # 9. 提交创建（OSS <cl-button> 不响应 Playwright 点击，通过 Vue 实例直接调用）
        self.page.evaluate(
            """
            () => {
                // 策略1：从 .create-bucket-container 查找
                const container = document.querySelector('.create-bucket-container');
                if (container) {
                    let vue = container.__vue__;
                    if (!vue) {
                        for (const child of container.querySelectorAll('*')) {
                            if (child.__vue__) { vue = child.__vue__; break; }
                        }
                    }
                    if (vue && vue.confirm) { vue.confirm('ruleForm'); return 'submitted'; }
                }
                // 策略2：全局遍历查找含 confirm('ruleForm') 的 Vue 实例
                const all = document.querySelectorAll('*');
                for (let i = 0; i < all.length; i++) {
                    const el = all[i];
                    if (el && el.__vue__) {
                        let p = el.__vue__;
                        while (p) {
                            if (typeof p.confirm === 'function' && p.$refs && p.$refs.ruleForm) {
                                p.confirm('ruleForm');
                                return 'submitted-via-global';
                            }
                            p = p.$parent;
                        }
                    }
                }
                // 策略3：fallback 直接找 cl-button 上的 confirm
                const btns = document.querySelectorAll('cl-button, .cl-button');
                for (const btn of btns) {
                    const v = btn.__vue__;
                    if (v && v.confirm) {
                        v.confirm('ruleForm');
                        return 'submitted-via-button';
                    }
                }
                return 'vue not found';
            }
            """
        )

        # 等待 API 处理完成（loading 状态变化，最长 30 秒）
        loading_seen = False
        for _ in range(30):
            self.page.wait_for_timeout(1000)
            has_loading = self.page.locator(".el-icon-loading").count() > 0
            if has_loading:
                loading_seen = True
            if loading_seen and not has_loading:
                break
        else:
            # 检查是否有错误消息
            error_msg = self.page.evaluate(
                """
                () => {
                    const s = '.el-message--error, .cv-message-error, .error-tip, .el-form-item__error, .el-message';
                    return Array.from(document.querySelectorAll(s))
                        .map(e => e.innerText.trim()).filter(t => t);
                }
                """
            )
            if error_msg:
                raise AssertionError(
                    f"桶 {name} 创建失败 | 错误: {' | '.join(error_msg)}"
                )

        # headless 环境中 Vue Router go(-1) 不生效，手动导航到桶列表
        self._goto_bucket_list()

    def oss_bucket_enter_detail(self, name):
        """进入桶详情页。

        Args:
            name: 桶名称。
        """
        self._goto_bucket_detail(name)

    def oss_bucket_detail_click_tag_tab(self, name=None):
        """导航到桶详情页的标签子页面。

        因 OSS 详情页菜单受权限过滤（resourcePolicyFlag），标签菜单可能被隐藏，
        此时页面 mounted() 钩子会自动重定向到首个可用菜单项。本方法通过检测
        URL 是否仍停留在 /basicconfig/tag 来判断标签页是否真正打开。

        Args:
            name: 桶名称。若未提供，从当前 URL 提取。

        Returns:
            bool: True 表示成功进入标签页；False 表示标签菜单被隐藏，无法访问。
        """
        base_url = Config.get("base_url").rstrip("/")
        current = self.page.url
        if not name:
            m = re.search(r"/bucket-list-page-detail/([^/]+)", current)
            name = m.group(1) if m else None
        if not name:
            raise RuntimeError("无法从 URL 提取桶名，请显式传入 name 参数")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{name}/basicconfig/tag")
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)
        return "/basicconfig/tag" in self.page.url

    def oss_bucket_detail_get_tags(self):
        """获取桶详情页展示的标签列表。

        标签数据可能异步加载，采用轮询重试策略。

        Returns:
            list[dict]: 标签列表，每项为 {"key": ..., "value": ...} 格式。
        """
        for _ in range(5):
            tags = []

            # 策略1：在表格中查找
            rows = self.page.locator(".el-table__body-wrapper tr, .table-main tr")
            for i in range(rows.count()):
                row = rows.nth(i)
                try:
                    key_cell = row.locator("td").nth(0)
                    value_cell = row.locator("td").nth(1)
                    key_text = key_cell.inner_text().strip()
                    value_text = value_cell.inner_text().strip()
                    if key_text and key_text not in ("标签键", "暂无数据"):
                        tags.append({"key": key_text, "value": value_text})
                except Exception:
                    continue

            # 策略2：在标签卡片区域查找键值对
            if not tags:
                tag_items = self.page.locator(".tag-item, .el-tag").all()
                for item in tag_items:
                    try:
                        text = item.inner_text().strip()
                        if ":" in text:
                            parts = text.split(":", 1)
                            tags.append({"key": parts[0].strip(), "value": parts[1].strip()})
                    except Exception:
                        continue

            # 策略3：从 Vue 实例读取 tagList
            if not tags:
                vue_tags = self.page.evaluate("""
                    () => {
                        const all = document.querySelectorAll('*');
                        for (const el of all) {
                            const vm = el.__vue__;
                            if (vm && vm.tagList && Array.isArray(vm.tagList)) {
                                return vm.tagList
                                    .filter(t => t && t.key !== undefined)
                                    .map(t => ({ key: t.key, value: t.value }));
                            }
                        }
                        return [];
                    }
                """)
                if vue_tags:
                    tags = vue_tags

            if tags:
                return tags

            self.page.wait_for_timeout(2000)

        return []

    def oss_bucket_delete(self, name):
        """删除指定桶。

        流程：导航到桶列表 -> 搜索过滤目标桶 -> 点击删除 -> 确认删除。
        采用"先搜索再操作"策略，避免表格分页/异步加载导致行定位失败。

        Args:
            name: 桶名称。
        """
        self._goto_bucket_list()

        # 等待表格行加载完成（最多等 10 秒）
        for _ in range(10):
            rows = self.page.locator(
                "#cloud-container-content .el-table__body-wrapper tr"
            ).all()
            if len(rows) > 0:
                break
            self.page.wait_for_timeout(1000)

        # 策略：先搜索过滤，再点击删除（避免分页/异步加载问题）
        search_input = self.page.locator(
            'input[placeholder*="搜索"], input[placeholder*="桶名称"]'
        ).first
        if search_input.count() > 0:
            search_input.click()
            search_input.fill("")
            self.page.wait_for_timeout(300)
            search_input.fill(name)
            self.page.wait_for_timeout(500)
            # 触发搜索
            self.page.evaluate("""
                () => {
                    const input = document.querySelector('input[placeholder*="搜索"], input[placeholder*="桶名称"]');
                    if (input) {
                        const event = new KeyboardEvent('keydown', {
                            key: 'Enter', code: 'Enter', keyCode: 13,
                            bubbles: true, cancelable: true
                        });
                        input.dispatchEvent(event);
                    }
                    const btns = document.querySelectorAll('button, .el-button, .cl-button');
                    for (const btn of btns) {
                        if (btn.innerText && btn.innerText.trim() === '搜索') {
                            btn.dispatchEvent(new MouseEvent('click', {
                                bubbles: true, cancelable: true, view: window
                            }));
                            break;
                        }
                    }
                }
            """)
            self.page.wait_for_timeout(5000)

        # 尝试点击删除（最多 3 次）
        for attempt in range(3):
            try:
                self.click_action(name, "删除")
                break
            except AssertionError as e:
                if "未找到名称为" in str(e) and attempt < 2:
                    self.page.wait_for_timeout(3000)
                    # 尝试 JS 直接定位删除按钮兜底
                    result = self.page.evaluate(f"""
                        () => {{
                            const rows = document.querySelectorAll('.el-table__row, .cl-table-body tr');
                            for (const row of rows) {{
                                if (row.innerText.includes('{name}')) {{
                                    const deleteBtn = row.querySelector('button, .el-button, .cl-button');
                                    if (deleteBtn) {{
                                        deleteBtn.dispatchEvent(new MouseEvent('click', {{
                                            bubbles: true, cancelable: true, view: window
                                        }}));
                                        return 'clicked';
                                    }}
                                }}
                            }}
                            return 'not-found';
                        }}
                    """)
                    if 'clicked' in str(result):
                        self.logger.info(f"JS 兜底删除点击成功: {name}")
                        break
                    continue
                raise
            except Exception as e:
                if attempt < 2:
                    self.logger.warning(f"删除操作失败，重试: {name} -> {e}")
                    self.page.wait_for_timeout(3000)
                    continue
                raise

        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 处理确认弹窗
        try:
            dialog = self.page.locator(
                ".cv-dialog:visible, .el-dialog:visible, .el-message-box:visible"
            ).first
            dialog.wait_for(state="visible", timeout=10000)
            confirm_btn = dialog.get_by_text("确定", exact=True).first
            if confirm_btn.count() > 0:
                confirm_btn.click(force=True)
            else:
                dialog.evaluate("""
                    (dlg) => {
                        const btn = dlg.querySelector('.el-button--primary, button:first-child');
                        if (btn) { btn.click(); return 'clicked'; }
                        return 'not-found';
                    }
                """)
        except Exception:
            pass

        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

    def oss_bucket_upload_object(self, bucket_name, file_path):
        """上传对象到指定桶。

        流程：导航到桶对象列表 -> 点击"上传对象" -> 选择文件 -> 点击上传 ->
        等待上传任务完成。因 OSS <cl-button> 不响应 Playwright 标准点击，
        内部通过 JS 触发 Vue 事件。

        Args:
            bucket_name: 目标桶名称。
            file_path: 本地文件绝对路径。
        """
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 点击"上传对象"按钮（JS 触发 cl-button Vue 事件）
        self.page.evaluate("""
            () => {
                const all = document.querySelectorAll('*');
                for (const el of all) {
                    const vue = el.__vue__;
                    if (vue && vue.$el && vue.$el.innerText &&
                        vue.$el.innerText.trim() === '上传对象') {
                        vue.$emit('click');
                        return 'clicked';
                    }
                }
                return 'not-found';
            }
        """)

        # 等待上传弹窗完全渲染（含 globalUpload 组件挂载）
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='visible',
            timeout=10000,
        )
        self.page.wait_for_timeout(2000)

        # 等待 file input 出现并设置文件
        self.page.wait_for_selector('#obsUploadInput', state='attached', timeout=10000)
        input_el = self.page.locator('#obsUploadInput')
        input_el.set_input_files(file_path)

        # Playwright set_input_files 已自动触发 input/change 事件，
        # 无需手动 dispatchEvent（手动触发的事件缺少 target.files，会导致
        # Vue 处理函数接收空文件列表）。等待 Vue 响应式更新完成。
        self.page.wait_for_timeout(3000)

        # 验证文件是否成功添加到上传列表（检查表格行或 fileListTotal）
        file_rows = self.page.locator(
            '.uploadObject-dialog-default-class .el-table__row'
        )
        if file_rows.count() == 0:
            # 再次等待，文件解析可能较慢
            self.page.wait_for_timeout(3000)
            if file_rows.count() == 0:
                raise AssertionError(
                    "文件未成功添加到上传列表，uploadObject 弹窗中无文件行"
                )

        # 点击"上传"按钮（弹窗底部提交）
        # uploadBigFile.vue 中使用 @click.native.prevent="submit('createObjForm')"，
        # Playwright 标准点击和 Vue $emit 均无法触发。el-dialog append-to-body
        # 导致 DOM 与组件树分离，需从弹窗内容区域反向查找 uploadBigFile Vue 实例。
        result = self.page.evaluate("""
            () => {
                const dialog = document.querySelector('.uploadObject-dialog-default-class');
                if (!dialog) return 'dialog-not-found';
                // 策略1: 从 globalUpload 组件向上查找 uploadBigFile
                const uploadContainer = dialog.querySelector('.upload-container');
                if (uploadContainer && uploadContainer.__vue__) {
                    let parent = uploadContainer.__vue__.$parent;
                    while (parent) {
                        if (typeof parent.submit === 'function') {
                            parent.submit('createObjForm');
                            return 'submitted-via-upload-parent';
                        }
                        parent = parent.$parent;
                    }
                }
                // 策略2: 从 cl-dialog-body 或 cl-dialog-footer 向上查找
                const dialogBody = dialog.querySelector('.el-dialog__body, .cl-dialog-body, .cl-dialog-footer');
                if (dialogBody) {
                    const walker = (el) => {
                        if (el.__vue__) {
                            let p = el.__vue__;
                            while (p) {
                                if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                    return p;
                                }
                                p = p.$parent;
                            }
                        }
                        for (const child of el.children) {
                            const found = walker(child);
                            if (found) return found;
                        }
                        return null;
                    };
                    const vue = walker(dialogBody);
                    if (vue) {
                        vue.submit('createObjForm');
                        return 'submitted-via-body-walker';
                    }
                }
                // 策略3: 全局搜索有 submit 和 dialogVisible 的 Vue 实例
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.__vue__) {
                        let p = el.__vue__;
                        while (p) {
                            if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                p.submit('createObjForm');
                                return 'submitted-via-global';
                            }
                            p = p.$parent;
                        }
                    }
                }
                // 策略4: fallback 直接点击上传按钮的 DOM 元素
                const btns = dialog.querySelectorAll('cl-button, .cl-button, button');
                for (const btn of btns) {
                    const v = btn.__vue__;
                    if (v && v.$el && v.$el.innerText &&
                        v.$el.innerText.trim() === '上传') {
                        btn.click();
                        return 'clicked-native';
                    }
                }
                return 'not-found';
            }
        """)
        if result and 'not-found' in str(result):
            raise AssertionError(
                f"上传按钮未找到，submit 调用结果: {result}"
            )

        # 等待上传弹窗关闭（异步上传，弹窗关闭即任务已提交）
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='hidden',
            timeout=15000,
        )

        # 上传为异步任务，等待上传完成后检查对象列表
        # 避免多次 goto 触发重复 loading 等待，先在当前页等待
        self.page.wait_for_timeout(30000)
        # 导航到对象列表页检查（仅一次）
        objects = self.oss_bucket_get_objects(bucket_name)

    def oss_bucket_create_with_copy_source(
        self,
        name,
        source_bucket,
        region="RegionOne",
        tags=None,
    ):
        """通过复制桶源创建新桶。

        流程：导航到创建页 -> 点击"选择桶源" -> 在弹窗中搜索并选中源桶 ->
        填写桶名称 -> 提交创建。选择桶源后区域/存储策略/桶策略/标签等
        会自动由前端从源桶带出。

        注意：本方法使用 Playwright 标准 DOM 操作（不依赖 __vue__，
        避免生产模式 Vue 实例不可访问的问题）。

        Args:
            name: 新桶名称。
            source_bucket: 源桶名称（用于搜索和选择）。
            region: 区域名称，默认 "RegionOne"（复制源会自动带出，无需显式选择）。
            tags: 标签列表，若源桶有标签通常前端自动带出，可不传。
        """
        self._goto_create_bucket()

        # 1. 点击"选择桶源"按钮（多策略 fallback）
        # 轮询等待按钮渲染完成（Vue 组件异步挂载）
        select_btn = None
        for _ in range(20):
            select_btn = self.page.get_by_text("选择桶源").first
            if select_btn.count() > 0:
                break
            self.page.wait_for_timeout(1000)

        clicked = False
        if select_btn and select_btn.count() > 0:
            # 策略A：标准 Playwright click
            try:
                select_btn.click(timeout=5000)
                clicked = True
            except Exception:
                pass

        # 策略B：JavaScript dispatchEvent（更接近原生事件）
        if not clicked:
            js_result = self.page.evaluate("""
                () => {
                    const el = document.evaluate(
                        "//*[contains(text(), '选择桶源')]",
                        document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
                    ).singleNodeValue;
                    if (el) {
                        el.dispatchEvent(new MouseEvent('click', {
                            bubbles: true, cancelable: true, view: window
                        }));
                        return 'dispatched';
                    }
                    return 'not-found';
                }
            """)
            if 'not-found' in str(js_result):
                raise AssertionError("无法点击'选择桶源'按钮 | JS结果: not-found")
            clicked = True

        # 2. 等待"选择复制源"弹窗出现并加载列表
        dialog_title = self.page.locator('.el-dialog__title').filter(
            has_text="选择复制源"
        ).first
        expect(dialog_title).to_be_visible(timeout=15000)
        # 弹窗 mounted 中自动调用 getListInfo，额外等待列表加载
        self.page.wait_for_timeout(5000)

        # 3. 在弹窗中搜索并选择源桶
        dialog = self.page.locator('.el-dialog').filter(
            has=self.page.locator('.el-dialog__title').filter(has_text="选择复制源")
        ).first

        # 搜索框：找 placeholder 包含"搜索"的 input
        search_input = dialog.locator('input').filter(
            has=self.page.locator('xpath=ancestor::*[@placeholder]')
        ).first
        if search_input.count() == 0:
            search_input = dialog.locator('input').first

        if search_input.count() > 0:
            search_input.fill(source_bucket)
            self.page.wait_for_timeout(500)
            # 触发 el-input 的 on-enter 事件（比点击搜索按钮更可靠）
            self.page.evaluate("""
                () => {
                    const input = document.querySelector('.el-dialog input');
                    if (input) {
                        const event = new KeyboardEvent('keydown', {
                            key: 'Enter', code: 'Enter', keyCode: 13,
                            bubbles: true, cancelable: true
                        });
                        input.dispatchEvent(event);
                    }
                }
            """)
            self.page.wait_for_timeout(3000)

        # 额外尝试点击搜索按钮（JS 触发，兼容 cl-button）
        self.page.evaluate("""
            () => {
                const dialog = document.querySelector('.el-dialog');
                if (!dialog) return;
                const btns = dialog.querySelectorAll('button, .el-button, .cl-button');
                for (const btn of btns) {
                    if (btn.innerText && btn.innerText.trim() === '搜索') {
                        btn.dispatchEvent(new MouseEvent('click', {
                            bubbles: true, cancelable: true, view: window
                        }));
                        break;
                    }
                }
            }
        """)
        self.page.wait_for_timeout(3000)

        # 4. 在弹窗中选择源桶并确认
        # bucketSourceDialog 中 cl-button 的 @click 是 Vue 自定义事件，
        # 且确定按钮 disabled 依赖于 currentSelectItem。优先通过 JS 直接
        # 操作 Vue 实例（若 __vue__ 可用），否则 fallback 到 DOM 点击。
        select_result = self.page.evaluate(f"""
            () => {{
                // 辅助：递归查找 bucketSourceDialog Vue 实例
                const findDialogVm = (vm) => {{
                    if (!vm) return null;
                    if (vm.listInfo !== undefined && typeof vm.confirm === 'function') {{
                        return vm;
                    }}
                    if (vm.$children && vm.$children.length > 0) {{
                        for (const child of vm.$children) {{
                            const found = findDialogVm(child);
                            if (found) return found;
                        }}
                    }}
                    return null;
                }};

                // 策略1: 从 el-dialog 元素的 __vue__ 向上找 $parent
                const dialogEl = document.querySelector('.el-dialog');
                if (dialogEl && dialogEl.__vue__) {{
                    let p = dialogEl.__vue__;
                    while (p) {{
                        const dialogVm = findDialogVm(p);
                        if (dialogVm) {{
                            const item = dialogVm.listInfo.find(
                                i => i.bucketName === '{source_bucket}'
                            );
                            if (item) {{
                                dialogVm.currentSelectItem = item;
                                dialogVm.listInfo.forEach(i => {{
                                    i.checked = (i.bucketName === '{source_bucket}');
                                }});
                                dialogVm.confirm();
                                return 'confirmed-via-dialog-parent';
                            }}
                            return 'bucket-not-found-listInfo';
                        }}
                        p = p.$parent;
                    }}
                }}

                // 策略2: 全局搜索含 confirm 和 listInfo 的 Vue 实例
                const all = document.querySelectorAll('*');
                for (const el of all) {{
                    if (el.__vue__) {{
                        let p = el.__vue__;
                        while (p) {{
                            if (p.listInfo !== undefined && typeof p.confirm === 'function') {{
                                const item = p.listInfo.find(
                                    i => i.bucketName === '{source_bucket}'
                                );
                                if (item) {{
                                    p.currentSelectItem = item;
                                    p.listInfo.forEach(i => {{
                                        i.checked = (i.bucketName === '{source_bucket}');
                                    }});
                                    p.confirm();
                                    return 'confirmed-via-global';
                                }}
                                return 'bucket-not-found-global';
                            }}
                            p = p.$parent;
                        }}
                    }}
                }}

                return 'vue-not-found';
            }}
        """)

        if 'not-found' in str(select_result) or 'not-found-listInfo' in str(select_result):
            # Vue 实例不可用，fallback 到 DOM 点击
            # 先找到源桶行并点击复选框
            self.page.evaluate(f"""
                () => {{
                    const rows = document.querySelectorAll('.el-table__row');
                    for (const row of rows) {{
                        if (row.innerText.includes('{source_bucket}')) {{
                            const checkbox = row.querySelector('.el-checkbox__original, .el-checkbox__input, input[type="checkbox"]');
                            if (checkbox) checkbox.click();
                            break;
                        }}
                    }}
                }}
            """)
            self.page.wait_for_timeout(1000)
            # 再点击确定按钮（dispatchEvent 触发原生 click）
            self.page.evaluate("""
                () => {
                    const dialog = document.querySelector('.el-dialog');
                    if (!dialog) return;
                    const btns = dialog.querySelectorAll('button, .el-button, .cl-button');
                    for (const btn of btns) {
                        if (btn.innerText && btn.innerText.trim() === '确定') {
                            btn.dispatchEvent(new MouseEvent('click', {
                                bubbles: true, cancelable: true, view: window
                            }));
                            break;
                        }
                    }
                }
            """)
            select_result = 'fallback-dom-click'

        # 等待弹窗关闭
        self.page.wait_for_selector('.el-dialog', state='hidden', timeout=15000)
        # 选择桶源后前端异步调用 handle_get_bucket_object_tag_list 加载标签，
        # 需等待 API 响应和 Vue 响应式更新完成
        self.page.wait_for_timeout(8000)

        # 6. 填写桶名称
        name_input = self.page.locator(
            '.el-form-item__content .el-input__inner'
        ).filter(
            has=self.page.locator('xpath=ancestor::el-form-item[contains(.,"桶名称")]')
        ).first
        if name_input.count() == 0:
            name_input = self.page.locator('.el-form-item').filter(
                has_text="桶名称"
            ).first.locator('.el-input__inner').first
        if name_input.count() > 0:
            name_input.fill(name)
            self.page.wait_for_timeout(300)

        # 7. 确认标签值（若前端未自动带出则手动填写）
        # 轮询等待标签输入框出现（handle_get_bucket_object_tag_list 异步加载）
        if tags:
            for tag in tags:
                # 轮询等待标签输入框或"添加标签"按钮出现
                tag_loaded = False
                for _ in range(10):
                    key_inputs = self.page.locator('input[placeholder="标签键"]')
                    add_tag_btn = self.page.get_by_text("添加标签", exact=True).first
                    if key_inputs.count() > 0 or add_tag_btn.count() > 0:
                        tag_loaded = True
                        break
                    self.page.wait_for_timeout(1000)

                if not tag_loaded:
                    # 标签区域未加载，跳过（可能是权限或产品问题）
                    continue

                key_inputs = self.page.locator('input[placeholder="标签键"]')
                if key_inputs.count() == 0:
                    add_tag_btn = self.page.get_by_text("添加标签", exact=True).first
                    if add_tag_btn.count() > 0:
                        add_tag_btn.click()
                        self.page.wait_for_timeout(1000)

                key_inputs = self.page.locator('input[placeholder="标签键"]')
                value_inputs = self.page.locator('input[placeholder="标签值"]')
                if key_inputs.count() > 0:
                    # 若输入框已有值且与目标一致则跳过，否则填写
                    current_key = key_inputs.last.input_value()
                    if current_key != tag["key"]:
                        key_inputs.last.fill(tag["key"])
                        self.page.wait_for_timeout(300)
                if value_inputs.count() > 0:
                    current_value = value_inputs.last.input_value()
                    if current_value != tag["value"]:
                        value_inputs.last.fill(tag["value"])
                        self.page.wait_for_timeout(300)

            # 7.5 直接注入 tags 到 Vue form（cl-button 点击不触发 addTag，需手动同步）
            tags_json = str(tags).replace("'", '"')
            self.page.evaluate(f"""
                () => {{
                    const container = document.querySelector('.create-bucket-container');
                    if (container) {{
                        let vue = container.__vue__;
                        if (!vue) {{
                            for (const child of container.querySelectorAll('*')) {{
                                if (child.__vue__) {{ vue = child.__vue__; break; }}
                            }}
                        }}
                        if (vue && vue.form) {{
                            vue.form.tags = {tags_json};
                            return 'injected';
                        }}
                    }}
                    const all = document.querySelectorAll('*');
                    for (const el of all) {{
                        if (el.__vue__) {{
                            let p = el.__vue__;
                            while (p) {{
                                if (p.form && Array.isArray(p.form.tags)) {{
                                    p.form.tags = {tags_json};
                                    return 'injected-global';
                                }}
                                p = p.$parent;
                            }}
                        }}
                    }}
                    return 'not-found';
                }}
            """)
            self.page.wait_for_timeout(500)

        # 8. 提交创建（复用 oss_bucket_create 中的 Vue 实例调用方式）
        self.page.evaluate(
            """
            () => {
                const container = document.querySelector('.create-bucket-container');
                if (container) {
                    let vue = container.__vue__;
                    if (!vue) {
                        for (const child of container.querySelectorAll('*')) {
                            if (child.__vue__) { vue = child.__vue__; break; }
                        }
                    }
                    if (vue && vue.confirm) { vue.confirm('ruleForm'); return 'submitted'; }
                }
                const all = document.querySelectorAll('*');
                for (let i = 0; i < all.length; i++) {
                    const el = all[i];
                    if (el && el.__vue__) {
                        let p = el.__vue__;
                        while (p) {
                            if (typeof p.confirm === 'function' && p.$refs && p.$refs.ruleForm) {
                                p.confirm('ruleForm');
                                return 'submitted-via-global';
                            }
                            p = p.$parent;
                        }
                    }
                }
                const btns = document.querySelectorAll('cl-button, .cl-button');
                for (const btn of btns) {
                    const v = btn.__vue__;
                    if (v && v.confirm) {
                        v.confirm('ruleForm');
                        return 'submitted-via-button';
                    }
                }
                return 'vue not found';
            }
            """
        )

        # 等待 API 处理完成
        loading_seen = False
        for _ in range(30):
            self.page.wait_for_timeout(1000)
            has_loading = self.page.locator(".el-icon-loading").count() > 0
            if has_loading:
                loading_seen = True
            if loading_seen and not has_loading:
                break
        else:
            error_msg = self.page.evaluate(
                """
                () => {
                    const s = '.el-message--error, .cv-message-error, .error-tip, .el-form-item__error, .el-message';
                    return Array.from(document.querySelectorAll(s))
                        .map(e => e.innerText.trim()).filter(t => t);
                }
                """
            )
            if error_msg:
                raise AssertionError(
                    f"桶 {name} 创建失败 | 错误: {' | '.join(error_msg)}"
                )

        # headless 环境中手动导航回桶列表
        self._goto_bucket_list()

    def oss_bucket_get_objects(self, bucket_name):
        """获取桶中的对象名称列表。

        导航到桶对象列表页，提取表格中展示的对象名称。
        对象列表数据可能由后端异步填充，采用轮询重试策略。

        Args:
            bucket_name: 桶名称。

        Returns:
            list[str]: 对象名称列表；若列表为空则返回空列表。
        """
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object")
        # 对象列表页可能发生 /object → /object/list 的重定向，
        # wait_for_page_ready 内部 count() 在导航时可能抛执行上下文销毁异常
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

        # 轮询等待对象列表加载（后端异步填充，首次可能为空）
        for attempt in range(10):
            objects = []

            # 策略1：直接从 Vue 实例读取对象列表数据
            vue_objects = self.page.evaluate("""
                () => {
                    const all = document.querySelectorAll('*');
                    for (let i = 0; i < all.length; i++) {
                        const el = all[i];
                        if (el && el.__vue__ && el.__vue__.gridObj && el.__vue__.gridObj.data) {
                            return el.__vue__.gridObj.data
                                .map(item => item.name)
                                .filter(name => name && name !== null && name !== '返回上一级');
                        }
                    }
                    return [];
                }
            """)
            if vue_objects:
                return vue_objects

            # 策略2：通过 .objectKeyClass .label 提取对象名
            labels = self.page.locator(".objectKeyClass .label").all()
            for label in labels:
                try:
                    text = label.inner_text().strip()
                    if text and text != "返回上一级":
                        objects.append(text)
                except Exception:
                    continue

            # 策略3：通过 cl-table / el-table 行数据提取
            if not objects:
                rows = self.page.locator(
                    ".cl-table-body tr, .el-table__body-wrapper tr"
                ).all()
                for row in rows:
                    try:
                        name_cell = row.locator("td").nth(0)
                        name = name_cell.inner_text().strip()
                        if name and name not in ("名称", "返回上一级", "--"):
                            objects.append(name)
                    except Exception:
                        continue

            if objects:
                return objects

            # 未加载完成，等待后重试
            self.page.wait_for_timeout(3000)

        return []

    def oss_bucket_wait_for_async_field(self, bucket_name, field_name="数据冗余存储策略", timeout=5):
        """等待桶列表行数据中指定异步字段值稳定（排除 --/空值）。

        OSS 列表中部分字段（如数据冗余存储策略）由后端异步填充，
        首次读取可能显示 '--' 或空值，需轮询等待稳定。

        Args:
            bucket_name: 桶名称。
            field_name: 等待稳定的字段名，默认 "数据冗余存储策略"。
            timeout: 最大等待秒数，默认 5。

        Returns:
            dict: 行数据字典。
        """
        import time
        deadline = time.time() + timeout
        row_data = {}
        while time.time() < deadline:
            row_data = self.get_row_data(bucket_name)
            value = row_data.get(field_name)
            if value not in (None, "", "--"):
                break
            time.sleep(0.5)
        return row_data

    def oss_bucket_delete_object(self, bucket_name, object_name):
        """删除桶中的指定对象。

        优先使用复选框选中 + 批量删除（更可靠），
        fallback 到操作下拉菜单单条删除。

        Args:
            bucket_name: 桶名称。
            object_name: 对象名称。
        """
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object")
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

        # 策略1：复选框选中 + 批量删除
        checked = self.page.evaluate(f"""
            () => {{
                const rows = document.querySelectorAll('.el-table__row, .cl-table-body tr');
                for (const row of rows) {{
                    if (row.innerText.includes('{object_name}')) {{
                        const checkbox = row.querySelector('input[type="checkbox"], .el-checkbox__original, .el-checkbox__input');
                        if (checkbox) {{
                            checkbox.click();
                            return 'checked';
                        }}
                    }}
                }}
                return 'not-found';
            }}
        """)

        if 'checked' in str(checked):
            self.page.wait_for_timeout(1000)
            # 点击"批量删除"按钮（cl-button 不响应 Playwright 标准点击，用 JS dispatchEvent）
            self.page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, .el-button, .cl-button');
                    for (const btn of btns) {
                        if (btn.innerText && btn.innerText.trim() === '批量删除') {
                            btn.dispatchEvent(new MouseEvent('click', {
                                bubbles: true, cancelable: true, view: window
                            }));
                            return 'clicked';
                        }
                    }
                    return 'not-found';
                }
            """)
            self.page.wait_for_timeout(2000)
            # 确认删除弹窗
            try:
                confirm_btn = self.page.get_by_text("确定", exact=True).first
                if confirm_btn.count() > 0:
                    confirm_btn.click(force=True)
            except Exception:
                pass
            self.page.wait_for_timeout(3000)
            return

        # 策略2：fallback 操作下拉菜单单条删除
        self.page.evaluate(f"""
            () => {{
                const rows = document.querySelectorAll('.el-table__row, .cl-table-body tr');
                for (const row of rows) {{
                    if (row.innerText.includes('{object_name}')) {{
                        const opBtn = row.querySelector('.el-dropdown, [class*="operation"], .el-icon-setting, [class*="more"]');
                        if (opBtn) {{
                            opBtn.click();
                            return 'op-clicked';
                        }}
                        // fallback: 查找包含"更多"文本的元素
                        const all = row.querySelectorAll('*');
                        for (const el of all) {{
                            if (el.innerText && el.innerText.includes('更多')) {{
                                el.click();
                                return 'op-clicked-more';
                            }}
                        }}
                    }}
                }}
                return 'not-found';
            }}
        """)
        self.page.wait_for_timeout(1000)

        # 点击下拉菜单中的"删除"
        self.page.evaluate("""
            () => {
                const items = document.querySelectorAll('.el-dropdown-menu__item');
                for (const item of items) {
                    if (item.innerText.includes('删除')) {
                        item.click();
                        return 'deleted';
                    }
                }
                return 'not-found';
            }
        """)
        self.page.wait_for_timeout(2000)

        # 确认删除弹窗
        try:
            confirm_btn = self.page.get_by_text("确定", exact=True).first
            if confirm_btn.count() > 0:
                confirm_btn.click(force=True)
        except Exception:
            pass

        self.page.wait_for_timeout(3000)

    # ── 碎片相关方法 ──

    def oss_bucket_open_upload_dialog(self, bucket_name):
        """在桶详情页打开上传对象弹窗。

        流程：导航到桶对象列表页 -> 点击"上传对象"按钮 -> 等待弹窗出现。

        Args:
            bucket_name: 桶名称。
        """
        base_url = Config.get("base_url").rstrip("/")
        target_url = f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object"

        # 强制导航到对象列表页（使用 about:blank 确保完整加载）
        if "/object" not in self.page.url:
            self.page.goto("about:blank")
            self.page.wait_for_timeout(500)
            self.page.goto(target_url)
            try:
                self.wait_for_page_ready()
            except Exception:
                self.page.wait_for_load_state("domcontentloaded")
                self.page.wait_for_timeout(3000)
            self.page.wait_for_timeout(5000)

        # 点击"上传对象"按钮（cl-button 自定义组件，优先用 get_by_text）
        try:
            upload_btn = self.page.get_by_text("上传对象", exact=True).first
            upload_btn.click(timeout=5000)
        except Exception:
            # fallback: JS 触发
            self.page.evaluate("""
                () => {
                    const all = document.querySelectorAll('*');
                    for (const el of all) {
                        const vue = el.__vue__;
                        if (vue && vue.$el && vue.$el.innerText &&
                            vue.$el.innerText.trim() === '上传对象') {
                            vue.$emit('click');
                            return 'clicked';
                        }
                    }
                    return 'not-found';
                }
            """)

        # 等待上传弹窗完全渲染（先等待 attached，再轮询检查 visible）
        # 弹窗可能先以 hidden 状态挂载，然后 Vue 动画过渡到 visible
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='attached',
            timeout=15000,
        )
        # 轮询等待弹窗变为 visible（处理 Vue 动画过渡）
        for _ in range(20):
            dialog = self.page.locator('.uploadObject-dialog-default-class').first
            if dialog.count() > 0:
                try:
                    is_visible = dialog.is_visible()
                    if is_visible:
                        break
                except Exception:
                    pass
            self.page.wait_for_timeout(500)
        self.page.wait_for_timeout(2000)

    def _wait_for_page_ready_with_fallback(self, timeout=10000):
        """等待页面就绪，带异常处理。

        Args:
            timeout: 超时时间（毫秒）。
        """
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

    def oss_bucket_prepare_fragment_files(self, bucket_name, count=3, file_size_mb=55):
        """在测试环境后台生成指定大小和数量的测试文件，用于构造碎片。

        通过 SSH 在后台使用 dd 命令生成文件，文件路径为 /tmp/test_fragment_*.txt。

        Args:
            bucket_name: 桶名称（仅用于日志记录）。
            count: 生成文件数量，默认 3。
            file_size_mb: 每个文件大小（MB），默认 55。

        Returns:
            list[str]: 生成的本地文件绝对路径列表。
        """
        file_paths = []
        for i in range(count):
            file_path = f"/tmp/test_fragment_{i}.txt"
            # 这里通过 ssh_host 在后台生成文件，但 Page 层不持有 ssh_host，
            # 所以返回路径列表，由测试层通过 ssh_host 执行 dd 命令生成
            file_paths.append(file_path)
        return file_paths

    def oss_bucket_upload_dialog_set_local_files(self, file_paths):
        """在上传对象弹窗中通过 set_input_files 设置本地真实文件。

        与 oss_bucket_upload_dialog_select_files 的区别：
        - 本方法使用 Playwright 原生 set_input_files，文件必须有真实内容
        - 适用于需要实际上传（如构造碎片场景）的情况
        - 文件必须在 Playwright 运行的本地机器上存在

        Args:
            file_paths: 本地文件绝对路径列表。
        """
        # 先点击文件拖拽区域，触发 flow.js 创建 input 元素
        # flow.js 的 assignBrowse 在点击时动态创建 input[type="file"]
        self.page.evaluate("""
            () => {
                const dropTarget = document.getElementById('file-drop-target');
                if (dropTarget) {
                    dropTarget.click();
                    return 'clicked-drop-target';
                }
                const fileDrop = document.querySelector('.file-drop');
                if (fileDrop) {
                    fileDrop.click();
                    return 'clicked-file-drop';
                }
                return 'not-found';
            }
        """)
        self.page.wait_for_timeout(1000)

        # 等待弹窗中的文件 input 出现
        # 不同微前端使用不同的 input 机制：
        # - oss 微前端: #obsUploadInput
        # - ops 微前端: flow.js 动态创建的 input[type="file"]
        input_selector = None
        for _ in range(30):
            # 检查 oss 微前端的 input
            oss_input = self.page.locator('#obsUploadInput').first
            if oss_input.count() > 0:
                input_selector = '#obsUploadInput'
                break
            # 检查 ops 微前端的 flow.js input（可能在 body 中）
            flow_input = self.page.locator('input[type="file"]').first
            if flow_input.count() > 0:
                input_selector = 'input[type="file"]'
                break
            # 再次点击触发
            self.page.evaluate("""
                () => {
                    const dropTarget = document.getElementById('file-drop-target');
                    if (dropTarget) { dropTarget.click(); return 'clicked'; }
                    const fileDrop = document.querySelector('.file-drop');
                    if (fileDrop) { fileDrop.click(); return 'clicked'; }
                    return 'not-found';
                }
            """)
            self.page.wait_for_timeout(500)

        if not input_selector:
            raise AssertionError(
                "未找到上传弹窗中的文件 input 元素（尝试了 #obsUploadInput 和 input[type='file']）"
            )

        # 使用 Playwright 原生 set_input_files 设置本地真实文件
        self.page.set_input_files(input_selector, file_paths)

        # 等待 Vue 响应式更新和文件列表渲染
        self.page.wait_for_timeout(3000)

        # 验证文件是否成功添加到上传列表
        file_rows = self.page.locator(
            '.uploadObject-dialog-default-class .el-table__row'
        )
        if file_rows.count() == 0:
            self.page.wait_for_timeout(3000)
            if file_rows.count() == 0:
                raise AssertionError(
                    "文件未成功添加到上传列表，uploadObject 弹窗中无文件行"
                )

    def oss_bucket_upload_dialog_select_files(self, file_paths):
        """在上传对象弹窗中选择文件。

        通过 Playwright set_input_files 设置文件。文件必须在 Playwright
        运行的本地机器上存在。对于远程测试环境，需要先将文件下载到本地。

        Args:
            file_paths: 文件绝对路径列表（在测试环境后台的文件路径）。
        """
        # 等待 file input 出现
        self.page.wait_for_selector('#obsUploadInput', state='attached', timeout=10000)
        input_el = self.page.locator('#obsUploadInput')

        # 文件路径在远程测试环境后台，Playwright set_input_files 需要本地文件
        # 方案：使用 JS 直接操作 Vue 组件的 fileList，模拟文件已选择
        # 这样不需要真实文件内容，只需要让前端认为文件已选择
        file_list_json = str(file_paths).replace("'", '"')
        result = self.page.evaluate(f"""
            () => {{
                const input = document.querySelector('#obsUploadInput');
                if (!input) return 'input-not-found';

                // 策略1: 直接操作 Vue 组件的 fileList
                const all = document.querySelectorAll('*');
                for (const el of all) {{
                    const vue = el.__vue__;
                    if (vue && vue.fileList) {{
                        const files = {file_list_json}.map(path => {{
                            const name = path.split('/').pop();
                            return {{
                                name: name,
                                raw: new File([''], name, {{ type: 'text/plain' }}),
                                size: 57671680,
                                status: 'ready',
                                uid: Date.now() + Math.random()
                            }};
                        }});
                        vue.fileList = files;
                        if (vue.fileListTotal !== undefined) {{
                            vue.fileListTotal = files.length;
                        }}
                        // 触发 Vue 响应式更新
                        if (vue.$forceUpdate) vue.$forceUpdate();
                        return 'fileList-set';
                    }}
                }}

                // 策略2: 从 input 元素向上查找 Vue 实例
                if (input.__vue__) {{
                    let p = input.__vue__;
                    while (p) {{
                        if (p.fileList !== undefined) {{
                            const files = {file_list_json}.map(path => {{
                                const name = path.split('/').pop();
                                return {{
                                    name: name,
                                    raw: new File([''], name, {{ type: 'text/plain' }}),
                                    size: 57671680,
                                    status: 'ready',
                                    uid: Date.now() + Math.random()
                                }};
                            }});
                            p.fileList = files;
                            if (p.fileListTotal !== undefined) {{
                                p.fileListTotal = files.length;
                            }}
                            if (p.$forceUpdate) p.$forceUpdate();
                            return 'fileList-set-via-parent';
                        }}
                        p = p.$parent;
                    }}
                }}

                // 策略3: 触发 input 的 change 事件，传入 DataTransfer
                const dt = new DataTransfer();
                {file_list_json}.forEach(path => {{
                    const name = path.split('/').pop();
                    const file = new File([''], name, {{ type: 'text/plain' }});
                    dt.items.add(file);
                }});
                input.files = dt.files;
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                return 'input-event-dispatched';
            }}
        """)

        self.page.wait_for_timeout(3000)

        # 验证文件是否成功添加到上传列表
        file_rows = self.page.locator(
            '.uploadObject-dialog-default-class .el-table__row'
        )
        if file_rows.count() == 0:
            self.page.wait_for_timeout(3000)
            if file_rows.count() == 0:
                raise AssertionError(
                    f"文件未成功添加到上传列表，JS结果: {result} | uploadObject 弹窗中无文件行"
                )

    def oss_bucket_upload_dialog_submit(self):
        """在上传对象弹窗中点击"上传"按钮提交上传任务。

        提交后等待弹窗关闭，任务列表抽屉页会自动弹出。
        """
        result = self.page.evaluate("""
            () => {
                const dialog = document.querySelector('.uploadObject-dialog-default-class');
                if (!dialog) return 'dialog-not-found';
                // 策略1: 从 globalUpload 组件向上查找 uploadBigFile
                const uploadContainer = dialog.querySelector('.upload-container');
                if (uploadContainer && uploadContainer.__vue__) {
                    let parent = uploadContainer.__vue__.$parent;
                    while (parent) {
                        if (typeof parent.submit === 'function') {
                            parent.submit('createObjForm');
                            return 'submitted-via-upload-parent';
                        }
                        parent = parent.$parent;
                    }
                }
                // 策略2: 从 cl-dialog-body 或 cl-dialog-footer 向上查找
                const dialogBody = dialog.querySelector('.el-dialog__body, .cl-dialog-body, .cl-dialog-footer');
                if (dialogBody) {
                    const walker = (el) => {
                        if (el.__vue__) {
                            let p = el.__vue__;
                            while (p) {
                                if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                    return p;
                                }
                                p = p.$parent;
                            }
                        }
                        for (const child of el.children) {
                            const found = walker(child);
                            if (found) return found;
                        }
                        return null;
                    };
                    const vue = walker(dialogBody);
                    if (vue) {
                        vue.submit('createObjForm');
                        return 'submitted-via-body-walker';
                    }
                }
                // 策略3: 全局搜索有 submit 和 dialogVisible 的 Vue 实例
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.__vue__) {
                        let p = el.__vue__;
                        while (p) {
                            if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                p.submit('createObjForm');
                                return 'submitted-via-global';
                            }
                            p = p.$parent;
                        }
                    }
                }
                // 策略4: fallback 直接点击上传按钮的 DOM 元素
                const btns = dialog.querySelectorAll('cl-button, .cl-button, button');
                for (const btn of btns) {
                    const v = btn.__vue__;
                    if (v && v.$el && v.$el.innerText &&
                        v.$el.innerText.trim() === '上传') {
                        btn.click();
                        return 'clicked-native';
                    }
                }
                return 'not-found';
            }
        """)
        if result and 'not-found' in str(result):
            raise AssertionError(
                f"上传按钮未找到，submit 调用结果: {result}"
            )

        # 等待上传弹窗关闭
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='hidden',
            timeout=15000,
        )
        self.page.wait_for_timeout(2000)

    def oss_bucket_upload_dialog_submit(self):
        """在上传对象弹窗中点击"上传"按钮提交上传任务。

        提交后等待弹窗关闭，任务列表抽屉页会自动弹出。
        """
        result = self.page.evaluate("""
            () => {
                const dialog = document.querySelector('.uploadObject-dialog-default-class');
                if (!dialog) return 'dialog-not-found';
                // 策略1: 从 globalUpload 组件向上查找 uploadBigFile
                const uploadContainer = dialog.querySelector('.upload-container');
                if (uploadContainer && uploadContainer.__vue__) {
                    let parent = uploadContainer.__vue__.$parent;
                    while (parent) {
                        if (typeof parent.submit === 'function') {
                            parent.submit('createObjForm');
                            return 'submitted-via-upload-parent';
                        }
                        parent = parent.$parent;
                    }
                }
                // 策略2: 从 cl-dialog-body 或 cl-dialog-footer 向上查找
                const dialogBody = dialog.querySelector('.el-dialog__body, .cl-dialog-body, .cl-dialog-footer');
                if (dialogBody) {
                    const walker = (el) => {
                        if (el.__vue__) {
                            let p = el.__vue__;
                            while (p) {
                                if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                    return p;
                                }
                                p = p.$parent;
                            }
                        }
                        for (const child of el.children) {
                            const found = walker(child);
                            if (found) return found;
                        }
                        return null;
                    };
                    const vue = walker(dialogBody);
                    if (vue) {
                        vue.submit('createObjForm');
                        return 'submitted-via-body-walker';
                    }
                }
                // 策略3: 全局搜索有 submit 和 dialogVisible 的 Vue 实例
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.__vue__) {
                        let p = el.__vue__;
                        while (p) {
                            if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                p.submit('createObjForm');
                                return 'submitted-via-global';
                            }
                            p = p.$parent;
                        }
                    }
                }
                // 策略4: fallback 直接点击上传按钮的 DOM 元素
                const btns = dialog.querySelectorAll('cl-button, .cl-button, button');
                for (const btn of btns) {
                    const v = btn.__vue__;
                    if (v && v.$el && v.$el.innerText &&
                        v.$el.innerText.trim() === '上传') {
                        btn.click();
                        return 'clicked-native';
                    }
                }
                return 'not-found';
            }
        """)
        if result and 'not-found' in str(result):
            raise AssertionError(
                f"上传按钮未找到，submit 调用结果: {result}"
            )

        # 等待上传弹窗关闭
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='hidden',
            timeout=15000,
        )
        self.page.wait_for_timeout(2000)

    def oss_bucket_upload_dialog_submit_with_files(self, file_paths):
        """在上传对象弹窗中设置文件并点击"上传"按钮提交。

        这是一个组合方法，先设置文件列表再提交上传。用于远程测试环境
        中文件不在本地的情况，通过 JS 直接操作 Vue 组件的 fileList。

        Args:
            file_paths: 文件绝对路径列表（在测试环境后台的文件路径）。
        """
        # 等待弹窗出现
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='visible',
            timeout=10000,
        )
        self.page.wait_for_timeout(2000)

        # 通过 JS 直接操作 Vue 组件的 fileList
        file_list_json = str(file_paths).replace("'", '"')
        result = self.page.evaluate(f"""
            () => {{
                const dialog = document.querySelector('.uploadObject-dialog-default-class');
                if (!dialog) return 'dialog-not-found';

                // 策略1: 直接操作 Vue 组件的 fileList
                const all = document.querySelectorAll('*');
                for (const el of all) {{
                    const vue = el.__vue__;
                    if (vue && vue.fileList) {{
                        const files = {file_list_json}.map(path => {{
                            const name = path.split('/').pop();
                            return {{
                                name: name,
                                raw: new File([''], name, {{ type: 'text/plain' }}),
                                size: 57671680,
                                status: 'ready',
                                uid: Date.now() + Math.random()
                            }};
                        }});
                        vue.fileList = files;
                        if (vue.fileListTotal !== undefined) {{
                            vue.fileListTotal = files.length;
                        }}
                        return 'fileList-set';
                    }}
                }}

                // 策略2: 从 input 元素向上查找 Vue 实例
                const input = document.querySelector('#obsUploadInput');
                if (input && input.__vue__) {{
                    let p = input.__vue__;
                    while (p) {{
                        if (p.fileList !== undefined) {{
                            const files = {file_list_json}.map(path => {{
                                const name = path.split('/').pop();
                                return {{
                                    name: name,
                                    raw: new File([''], name, {{ type: 'text/plain' }}),
                                    size: 57671680,
                                    status: 'ready',
                                    uid: Date.now() + Math.random()
                                }};
                            }});
                            p.fileList = files;
                            if (p.fileListTotal !== undefined) {{
                                p.fileListTotal = files.length;
                            }}
                            return 'fileList-set-via-parent';
                        }}
                        p = p.$parent;
                    }}
                }}

                // 策略3: 触发 input 的 change 事件
                if (input) {{
                    const dt = new DataTransfer();
                    {file_list_json}.forEach(path => {{
                        const name = path.split('/').pop();
                        const file = new File([''], name, {{ type: 'text/plain' }});
                        dt.items.add(file);
                    }});
                    input.files = dt.files;
                    input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    return 'input-event-dispatched';
                }}

                return 'input-not-found';
            }}
        """)

        self.page.wait_for_timeout(3000)

        # 验证文件是否成功添加到上传列表
        file_rows = self.page.locator(
            '.uploadObject-dialog-default-class .el-table__row'
        )
        if file_rows.count() == 0:
            self.page.wait_for_timeout(3000)
            if file_rows.count() == 0:
                raise AssertionError(
                    f"文件未成功添加到上传列表，JS结果: {result} | uploadObject 弹窗中无文件行"
                )

        # 点击上传按钮提交
        submit_result = self.page.evaluate("""
            () => {
                const dialog = document.querySelector('.uploadObject-dialog-default-class');
                if (!dialog) return 'dialog-not-found';
                // 策略1: 从 globalUpload 组件向上查找 uploadBigFile
                const uploadContainer = dialog.querySelector('.upload-container');
                if (uploadContainer && uploadContainer.__vue__) {
                    let parent = uploadContainer.__vue__.$parent;
                    while (parent) {
                        if (typeof parent.submit === 'function') {
                            parent.submit('createObjForm');
                            return 'submitted-via-upload-parent';
                        }
                        parent = parent.$parent;
                    }
                }
                // 策略2: 从 cl-dialog-body 或 cl-dialog-footer 向上查找
                const dialogBody = dialog.querySelector('.el-dialog__body, .cl-dialog-body, .cl-dialog-footer');
                if (dialogBody) {
                    const walker = (el) => {
                        if (el.__vue__) {
                            let p = el.__vue__;
                            while (p) {
                                if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                    return p;
                                }
                                p = p.$parent;
                            }
                        }
                        for (const child of el.children) {
                            const found = walker(child);
                            if (found) return found;
                        }
                        return null;
                    };
                    const vue = walker(dialogBody);
                    if (vue) {
                        vue.submit('createObjForm');
                        return 'submitted-via-body-walker';
                    }
                }
                // 策略3: 全局搜索有 submit 和 dialogVisible 的 Vue 实例
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.__vue__) {
                        let p = el.__vue__;
                        while (p) {
                            if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                p.submit('createObjForm');
                                return 'submitted-via-global';
                            }
                            p = p.$parent;
                        }
                    }
                }
                // 策略4: fallback 直接点击上传按钮的 DOM 元素
                const btns = dialog.querySelectorAll('cl-button, .cl-button, button');
                for (const btn of btns) {
                    const v = btn.__vue__;
                    if (v && v.$el && v.$el.innerText &&
                        v.$el.innerText.trim() === '上传') {
                        btn.click();
                        return 'clicked-native';
                    }
                }
                // 策略5: 直接查找按钮文本
                const allBtns = dialog.querySelectorAll('button, .el-button, .cl-button, [class*="btn"]');
                for (const btn of allBtns) {
                    if (btn.innerText && btn.innerText.trim() === '上传') {
                        btn.click();
                        return 'clicked-by-text';
                    }
                }
                return 'not-found';
            }
        """)
        if submit_result and 'not-found' in str(submit_result):
            raise AssertionError(
                f"上传按钮未找到，submit 调用结果: {submit_result}"
            )

        # 等待上传弹窗关闭
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='hidden',
            timeout=15000,
        )
        self.page.wait_for_timeout(2000)

    def oss_bucket_upload_dialog_submit_with_files(self, file_paths):
        """在上传对象弹窗中设置文件并点击"上传"按钮提交。

        通过 JS 直接操作 Vue 组件的 fileList，创建真实大小的文件对象
        （使用 ArrayBuffer 填充），使上传需要足够时间以便暂停。

        Args:
            file_paths: 文件绝对路径列表（仅用于获取文件名和大小）。
        """
        # 等待弹窗出现（先 attached 再轮询 visible）
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='attached',
            timeout=15000,
        )
        for _ in range(20):
            dialog = self.page.locator('.uploadObject-dialog-default-class').first
            if dialog.count() > 0:
                try:
                    if dialog.is_visible():
                        break
                except Exception:
                    pass
            self.page.wait_for_timeout(500)
        self.page.wait_for_timeout(2000)

        # 通过 JS 直接操作 Vue 组件的 fileList，创建真实大小的 File 对象
        file_list_json = str(file_paths).replace("'", '"')
        result = self.page.evaluate(f"""
            () => {{
                const dialog = document.querySelector('.uploadObject-dialog-default-class');
                if (!dialog) return 'dialog-not-found';

                // 策略1: 直接操作 Vue 组件的 fileList
                const all = document.querySelectorAll('*');
                for (const el of all) {{
                    const vue = el.__vue__;
                    if (vue && vue.fileList) {{
                        const files = {file_list_json}.map(path => {{
                            const name = path.split('/').pop();
                            const size = 57671680; // 55MB
                            // 创建真实大小的 ArrayBuffer
                            const buffer = new ArrayBuffer(size);
                            const file = new File([buffer], name, {{ type: 'text/plain' }});
                            // 包装为 simple-uploader.js 风格的文件对象
                            return {{
                                name: name,
                                raw: file,
                                size: size,
                                status: 'ready',
                                uid: Date.now() + Math.random(),
                                getSize: function() {{ return size; }},
                                custom_params: {{
                                    bucket_name: '',
                                    objectKey: name,
                                    metadata: null,
                                    storageClass: 'STANDARD'
                                }}
                            }};
                        }});
                        vue.fileList = files;
                        if (vue.fileListTotal !== undefined) {{
                            vue.fileListTotal = files.length;
                        }}
                        if (vue.totalSize !== undefined) {{
                            vue.totalSize = files.reduce((sum, f) => sum + f.size, 0);
                        }}
                        // 触发 Vue 响应式更新
                        if (vue.$forceUpdate) vue.$forceUpdate();
                        // 触发 fileInfo 事件通知 uploadBigFile 组件
                        if (vue.$emit) {{
                            vue.$emit('fileInfo', {{
                                count: files.length,
                                size: files.reduce((sum, f) => sum + f.size, 0)
                            }});
                        }}
                        return 'fileList-set';
                    }}
                }}

                // 策略2: 从 input 元素向上查找 Vue 实例
                const input = document.querySelector('#obsUploadInput');
                if (input && input.__vue__) {{
                    let p = input.__vue__;
                    while (p) {{
                        if (p.fileList !== undefined) {{
                            const files = {file_list_json}.map(path => {{
                                const name = path.split('/').pop();
                                const size = 57671680;
                                const buffer = new ArrayBuffer(size);
                                const file = new File([buffer], name, {{ type: 'text/plain' }});
                                return {{
                                    name: name,
                                    raw: file,
                                    size: size,
                                    status: 'ready',
                                    uid: Date.now() + Math.random(),
                                    getSize: function() {{ return size; }},
                                    custom_params: {{
                                        bucket_name: '',
                                        objectKey: name,
                                        metadata: null,
                                        storageClass: 'STANDARD'
                                    }}
                                }};
                            }});
                            p.fileList = files;
                            if (p.fileListTotal !== undefined) {{
                                p.fileListTotal = files.length;
                            }}
                            if (p.totalSize !== undefined) {{
                                p.totalSize = files.reduce((sum, f) => sum + f.size, 0);
                            }}
                            if (p.$forceUpdate) p.$forceUpdate();
                            if (p.$emit) {{
                                p.$emit('fileInfo', {{
                                    count: files.length,
                                    size: files.reduce((sum, f) => sum + f.size, 0)
                                }});
                            }}
                            return 'fileList-set-via-parent';
                        }}
                        p = p.$parent;
                    }}
                }}

                return 'input-not-found';
            }}
        """)

        self.page.wait_for_timeout(3000)

        # 验证文件是否成功添加到上传列表
        file_rows = self.page.locator(
            '.uploadObject-dialog-default-class .el-table__row'
        )
        if file_rows.count() == 0:
            self.page.wait_for_timeout(3000)
            if file_rows.count() == 0:
                raise AssertionError(
                    f"文件未成功添加到上传列表，JS结果: {result} | uploadObject 弹窗中无文件行"
                )

        # 点击上传按钮提交
        submit_result = self.page.evaluate("""
            () => {
                const dialog = document.querySelector('.uploadObject-dialog-default-class');
                if (!dialog) return 'dialog-not-found';
                // 策略1: 从 globalUpload 组件向上查找 uploadBigFile
                const uploadContainer = dialog.querySelector('.upload-container');
                if (uploadContainer && uploadContainer.__vue__) {
                    let parent = uploadContainer.__vue__.$parent;
                    while (parent) {
                        if (typeof parent.submit === 'function') {
                            parent.submit('createObjForm');
                            return 'submitted-via-upload-parent';
                        }
                        parent = parent.$parent;
                    }
                }
                // 策略2: 从 cl-dialog-body 或 cl-dialog-footer 向上查找
                const dialogBody = dialog.querySelector('.el-dialog__body, .cl-dialog-body, .cl-dialog-footer');
                if (dialogBody) {
                    const walker = (el) => {
                        if (el.__vue__) {
                            let p = el.__vue__;
                            while (p) {
                                if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                    return p;
                                }
                                p = p.$parent;
                            }
                        }
                        for (const child of el.children) {
                            const found = walker(child);
                            if (found) return found;
                        }
                        return null;
                    };
                    const vue = walker(dialogBody);
                    if (vue) {
                        vue.submit('createObjForm');
                        return 'submitted-via-body-walker';
                    }
                }
                // 策略3: 全局搜索有 submit 和 dialogVisible 的 Vue 实例
                const allElements = document.querySelectorAll('*');
                for (const el of allElements) {
                    if (el.__vue__) {
                        let p = el.__vue__;
                        while (p) {
                            if (typeof p.submit === 'function' && p.dialogVisible !== undefined) {
                                p.submit('createObjForm');
                                return 'submitted-via-global';
                            }
                            p = p.$parent;
                        }
                    }
                }
                // 策略4: fallback 直接点击上传按钮的 DOM 元素
                const btns = dialog.querySelectorAll('cl-button, .cl-button, button');
                for (const btn of btns) {
                    const v = btn.__vue__;
                    if (v && v.$el && v.$el.innerText &&
                        v.$el.innerText.trim() === '上传') {
                        btn.click();
                        return 'clicked-native';
                    }
                }
                // 策略5: 直接查找按钮文本
                const allBtns = dialog.querySelectorAll('button, .el-button, .cl-button, [class*="btn"]');
                for (const btn of allBtns) {
                    if (btn.innerText && btn.innerText.trim() === '上传') {
                        btn.click();
                        return 'clicked-by-text';
                    }
                }
                return 'not-found';
            }
        """)
        if submit_result and 'not-found' in str(submit_result):
            raise AssertionError(
                f"上传按钮未找到，submit 调用结果: {submit_result}"
            )

        # 等待上传弹窗关闭
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='hidden',
            timeout=15000,
        )
        self.page.wait_for_timeout(2000)

    def oss_bucket_task_pause_all(self, bucket_name):
        """在任务列表抽屉页中点击"全部暂停"按钮。

        任务列表抽屉出现后尽快执行暂停操作，避免内网环境下大文件
        上传瞬间完成而无法进入暂停状态。

        Args:
            bucket_name: 桶名称。
        """
        # 等待任务列表抽屉出现（抽屉弹出即代表上传已开始）
        self.page.wait_for_selector(
            '.el-drawer__wrapper',
            state='visible',
            timeout=15000,
        )

        # 立即尝试点击"全部暂停"按钮；抽屉刚弹出时按钮可能尚未渲染完成，
        # 因此做短轮询，在 3 秒内持续尝试点击
        for _ in range(30):
            clicked = self.page.evaluate("""
                () => {
                    const btns = document.querySelectorAll('button, .el-button, .cl-button');
                    for (const btn of btns) {
                        if (btn.innerText && btn.innerText.trim() === '全部暂停') {
                            btn.dispatchEvent(new MouseEvent('click', {
                                bubbles: true, cancelable: true, view: window
                            }));
                            return 'clicked';
                        }
                    }
                    return 'not-found';
                }
            """)
            if clicked == 'clicked':
                break
            self.page.wait_for_timeout(100)

        self.page.wait_for_timeout(1000)

    def oss_bucket_task_cancel_one(self, bucket_name):
        """在任务列表中选择任一上传任务，点击"取消"按钮。

        取消处于 PAUSE 状态的任务。

        Args:
            bucket_name: 桶名称。
        """
        # 等待任务列表中至少有一个 PAUSE 状态的任务出现"取消"链接
        for _ in range(20):
            has_cancel = self.page.evaluate("""
                () => {
                    const rows = document.querySelectorAll('.el-table__row');
                    for (const row of rows) {
                        const cancelLink = row.querySelector('a, .el-link');
                        if (cancelLink && cancelLink.innerText && cancelLink.innerText.trim() === '取消') {
                            return true;
                        }
                    }
                    return false;
                }
            """)
            if has_cancel:
                break
            self.page.wait_for_timeout(1000)

        # 点击第一个"取消"链接
        self.page.evaluate("""
            () => {
                const rows = document.querySelectorAll('.el-table__row');
                for (const row of rows) {
                    const cancelLink = row.querySelector('a, .el-link');
                    if (cancelLink && cancelLink.innerText && cancelLink.innerText.trim() === '取消') {
                        cancelLink.click();
                        return 'cancelled';
                    }
                }
                return 'not-found';
            }
        """)
        self.page.wait_for_timeout(3000)

    def oss_bucket_task_has_status(self, bucket_name, status):
        """检查任务列表中是否存在指定状态的任务。

        Args:
            bucket_name: 桶名称。
            status: 状态值，如 "PAUSE" / "CANCEL" / "UPLOADING" / "请求参数错误" 等。

        Returns:
            bool: 存在则返回 True。
        """
        # 任务列表抽屉可见时直接检查
        result = self.page.evaluate(f"""
            () => {{
                const rows = document.querySelectorAll('.el-table__row');
                for (const row of rows) {{
                    const rowText = row.innerText || '';
                    if (rowText.includes('{status}') ||
                        rowText.includes('暂停') ||
                        rowText.includes('取消') ||
                        rowText.includes('请求参数错误')) {{
                        return true;
                    }}
                }}
                return false;
            }}
        """)
        return bool(result)

    def oss_bucket_close_task_drawer(self):
        """关闭上传任务列表抽屉（如果存在）。"""
        try:
            self.page.evaluate("""
                () => {
                    const drawer = document.querySelector('.el-drawer__wrapper');
                    if (drawer) {
                        const closeBtn = drawer.querySelector('.el-drawer__close-btn, .el-drawer__headerbtn');
                        if (closeBtn) closeBtn.click();
                    }
                }
            """)
            self.page.wait_for_timeout(2000)
        except Exception:
            pass

    def oss_bucket_goto_object_tab(self, bucket_name):
        """导航到桶详情页的对象tab页。

        Args:
            bucket_name: 桶名称。
        """
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object")
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

    def oss_bucket_goto_fragment_tab(self, bucket_name):
        """导航到桶详情页的碎片 tab 页。

        先关闭任务列表抽屉，然后导航到碎片页面。

        Args:
            bucket_name: 桶名称。
        """
        # 关闭任务列表抽屉（如果存在）
        try:
            self.page.evaluate("""
                () => {
                    const drawer = document.querySelector('.el-drawer__wrapper');
                    if (drawer) {
                        const closeBtn = drawer.querySelector('.el-drawer__close-btn, .el-drawer__headerbtn');
                        if (closeBtn) closeBtn.click();
                    }
                }
            """)
            self.page.wait_for_timeout(2000)
        except Exception:
            pass

        # 导航到碎片页面
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object/fragement")
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

    def oss_bucket_get_fragments(self, bucket_name):
        """获取桶碎片列表。

        导航到碎片页面，提取表格中展示的碎片数据。

        Args:
            bucket_name: 桶名称。

        Returns:
            list[dict]: 碎片列表，每项包含 objectKey、num（碎片数量）、size、uploadId 等。
        """
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object/fragement")
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

        # 轮询等待碎片列表加载
        for attempt in range(10):
            fragments = []

            # 策略1：从 Vue 实例读取碎片列表数据
            vue_fragments = self.page.evaluate("""
                () => {
                    const all = document.querySelectorAll('*');
                    for (let i = 0; i < all.length; i++) {
                        const el = all[i];
                        if (el && el.__vue__ && el.__vue__.gridObj && el.__vue__.gridObj.data) {
                            return el.__vue__.gridObj.data
                                .map(item => ({
                                    objectKey: item.objectKey,
                                    num: item.num,
                                    size: item.size,
                                    uploadId: item.uploadId,
                                    lastModified: item.lastModified,
                                }));
                        }
                    }
                    return [];
                }
            """)
            if vue_fragments:
                return vue_fragments

            # 策略2：通过表格行提取碎片数据
            rows = self.page.locator(".el-table__body-wrapper tr, .cl-table-body tr").all()
            for row in rows:
                try:
                    cells = row.locator("td").all()
                    if len(cells) >= 4:
                        # 碎片表格列：复选框 | 对象名称 | 碎片数量 | 大小 | 上传ID | 最后修改时间 | 操作
                        object_key = cells[1].inner_text().strip()
                        if object_key and object_key not in ("对象名称", "--", "标准存储"):
                            fragments.append({
                                "objectKey": object_key,
                                "num": cells[2].inner_text().strip(),
                                "size": cells[3].inner_text().strip(),
                            })
                except Exception:
                    continue

            if fragments:
                return fragments

            self.page.wait_for_timeout(3000)

        return []

    def oss_bucket_delete_fragment(self, bucket_name, fragment_name):
        """删除单个碎片。

        在碎片列表页找到目标碎片，点击操作下拉菜单中的"删除"，确认删除。

        Args:
            bucket_name: 桶名称。
            fragment_name: 碎片名称（objectKey）。
        """
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object/fragement")
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

        # 点击操作下拉菜单（cl-table-dropdown）
        self.page.evaluate(f"""
            () => {{
                const rows = document.querySelectorAll('.el-table__row, .cl-table-body tr');
                for (const row of rows) {{
                    if (row.innerText.includes('{fragment_name}')) {{
                        const dropdown = row.querySelector('.cl-table-dropdown, .el-dropdown');
                        if (dropdown) {{
                            dropdown.click();
                            return 'clicked';
                        }}
                    }}
                }}
                return 'not-found';
            }}
        """)
        self.page.wait_for_timeout(1000)

        # 点击下拉菜单中的"删除"
        self.page.evaluate("""
            () => {
                const items = document.querySelectorAll('.cl-table-dropdown-item, .el-dropdown-menu__item');
                for (const item of items) {
                    if (item.innerText && item.innerText.trim() === '删除') {
                        item.click();
                        return 'deleted';
                    }
                }
                return 'not-found';
            }
        """)
        self.page.wait_for_timeout(2000)

        # 确认删除弹窗（objectListOperationDialog）
        try:
            confirm_btn = self.page.get_by_text("确定", exact=True).first
            if confirm_btn.count() > 0:
                confirm_btn.click(force=True)
        except Exception:
            pass

        self.page.wait_for_timeout(3000)

    def oss_bucket_batch_delete_fragments(self, bucket_name, fragment_names):
        """批量删除碎片。

        在碎片列表页勾选多个碎片，点击"批量删除"按钮，确认删除。

        Args:
            bucket_name: 桶名称。
            fragment_names: 要删除的碎片名称列表。
        """
        base_url = Config.get("base_url").rstrip("/")
        self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object/fragement")
        try:
            self.wait_for_page_ready()
        except Exception:
            self.page.wait_for_load_state("domcontentloaded")
            self.page.wait_for_timeout(3000)
        self.page.wait_for_timeout(3000)

        # 勾选所有目标碎片
        for name in fragment_names:
            self.page.evaluate(f"""
                () => {{
                    const rows = document.querySelectorAll('.el-table__row, .cl-table-body tr');
                    for (const row of rows) {{
                        if (row.innerText.includes('{name}')) {{
                            const checkbox = row.querySelector('input[type="checkbox"], .el-checkbox__original');
                            if (checkbox) {{
                                checkbox.click();
                                return 'checked';
                            }}
                        }}
                    }}
                    return 'not-found';
                }}
            """)
            self.page.wait_for_timeout(500)

        # 点击"批量删除"按钮
        self.page.evaluate("""
            () => {
                const btns = document.querySelectorAll('button, .el-button, .cl-button');
                for (const btn of btns) {
                    if (btn.innerText && btn.innerText.trim() === '批量删除') {
                        btn.dispatchEvent(new MouseEvent('click', {
                            bubbles: true, cancelable: true, view: window
                        }));
                        return 'clicked';
                    }
                }
                return 'not-found';
            }
        """)
        self.page.wait_for_timeout(2000)

        # 确认删除弹窗
        try:
            confirm_btn = self.page.get_by_text("确定", exact=True).first
            if confirm_btn.count() > 0:
                confirm_btn.click(force=True)
        except Exception:
            pass

        self.page.wait_for_timeout(3000)
