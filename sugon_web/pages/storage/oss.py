import json
import os
import tempfile

import re

from playwright.sync_api import expect

from sugon_web.common.base import BasePage
from sugon_web.config.config import Config
from sugon_web.utils.data import random_data
from sugon_web.utils.logger import logger


class OssPage(BasePage):
    """对象存储OSS页面对象。"""
    service_name = "对象存储"

    def goto_service(self, service: str, force: bool = False):
        """重写服务导航：对象存储直接落到桶列表页并等待数据加载完成。

        OSS 是独立微前端，平台标准服务导航在已进入 OSS 后再次调用可能
        被重定向到控制台首页，因此对"对象存储"直接通过 URL 进入桶列表。
        """
        # 先关闭可能存在的弹窗
        try:
            self.close_dialog_if_exists()
        except Exception:
            pass

        if service == self.service_name:
            self._goto_bucket_list()
            return self
        return super().goto_service(service, force=force)

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

        # 等待桶列表数据行或空态渲染完成（避免测试直接点击桶名时数据尚未加载）
        self._wait_for_bucket_list_loaded()
        # 将分页设置为 50，降低因桶数量多导致目标桶不在首屏的概率
        self._set_bucket_list_page_size(50)

    def _wait_for_bucket_list_loaded(self):
        """等待桶列表表格数据渲染完成（有数据行或空态提示）。"""
        for _ in range(30):
            rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
            if rows:
                return
            empty = self.page.locator(".el-empty, .el-table__empty-text, .empty-text").first
            if empty.count() > 0 and empty.is_visible():
                return
            no_data = self.page.get_by_text("暂无数据", exact=False).first
            if no_data.count() > 0 and no_data.is_visible():
                return
            self.page.wait_for_timeout(1000)

    def _set_bucket_list_page_size(self, size=50):
        """在桶列表页将分页大小设置为指定值（支持 10/20/50/100）。"""
        try:
            # 定位分页器下拉（placeholder='请选择'）
            select = self.page.locator(
                ".cl-table-footer .el-pagination__sizes .el-input__inner, "
                ".el-pagination__sizes input[placeholder='请选择']"
            ).first
            if select.count() == 0:
                return
            # 若当前已是目标大小则跳过
            current = (select.input_value() or "").strip()
            if current == f"{size}条/页" or current == str(size):
                return
            select.click()
            self.page.wait_for_timeout(500)
            option = self.page.locator(".el-select-dropdown__item").filter(has_text=f"{size}条/页").first
            if option.count() == 0:
                option = self.page.get_by_text(f"{size}", exact=False).filter(has_text="条/页").first
            if option.count() > 0:
                option.click()
                self.page.wait_for_timeout(2000)
                self._wait_for_bucket_list_loaded()
        except Exception:
            pass

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
        self._ensure_session_owner()

    def _ensure_session_owner(self):
        """将 ``sessionStorage.owner`` 设置为当前登录用户 ID。

        OSS 微前端多个页面（桶详情、对象列表、生命周期规则等）通过
        ``is_disabled()`` 判断 admin 用户是否为桶所有者，若
        ``sessionStorage.owner`` 为空或与当前用户 ID 不一致，会隐藏/禁用
        ``上传对象``、``新建`` 等操作按钮。直接 URL 进入或某些 UI 回退场景
        可能未经过桶列表页的 ``show_detail``，导致该值缺失，因此需要显式补齐。
        """
        try:
            self.page.evaluate("""
                () => {
                    if (typeof GetUserInfo === 'function') {
                        const userId = GetUserInfo('userId');
                        if (userId) {
                            sessionStorage.setItem('owner', userId);
                            return userId;
                        }
                    }
                    return null;
                }
            """)
        except Exception:
            pass

    def oss_bucket_enter_detail_via_ui(self, name):
        """通过桶列表页点击桶名称进入详情页（UI导航，避免直接URL触发权限拦截）。

        若桶不在当前分页，会自动通过搜索框过滤后再点击。

        Args:
            name: 桶名称。
        """
        # 先确保在桶列表页（内部会等待数据加载并设置分页为50）
        self._goto_bucket_list()
        self.page.wait_for_timeout(2000)

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

            # 策略2: 通过搜索框过滤桶名后再点击
            try:
                self._search_in_bucket_list(name)
                self.page.wait_for_timeout(2000)
                bucket_link = self.page.get_by_text(name, exact=True).first
                if bucket_link.count() > 0:
                    bucket_link.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                pass

            # 策略3: JS 查找包含桶名的行并点击
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
                self._ensure_session_owner()
                return
            # 检查是否被重定向到 no-permission
            if "/no-permission" in self.page.url:
                raise AssertionError(
                    f"导航到桶 '{name}' 详情页被前端权限拦截，当前URL: {self.page.url}"
                )

        # URL 未变但 DOM 已渲染详情页也接受
        if (
            self.page.locator("text=桶详情").count() > 0
            or self.page.locator(".bucket-detail-left-menu").count() > 0
        ):
            self._ensure_session_owner()
            return
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

        优先通过桶列表页"新建"按钮进入；若按钮因权限/渲染时序未出现，
        则回退到直接 URL 导航到 /CreateBucket 并等待表单渲染。
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

        # 尝试点击"新建"按钮（等待权限指令渲染）
        clicked = False
        for attempt in range(10):
            try:
                create_btn = self.page.locator(".cl-table-header, .table-tool-bar").get_by_text("新建", exact=False).first
                if create_btn.count() > 0 and create_btn.is_visible():
                    create_btn.click(timeout=5000)
                    clicked = True
                    break
            except Exception:
                pass
            self.page.wait_for_timeout(1000)

        # 若按钮未出现，直接 URL 导航到创建页
        if not clicked:
            base_url = Config.get("base_url").rstrip("/")
            self.page.goto(f"{base_url}/oss/#/CreateBucket")
            try:
                self.wait_for_page_ready()
            except Exception:
                self.page.wait_for_load_state("domcontentloaded")
                self.page.wait_for_timeout(3000)

        # 等待创建页表单元素出现
        for _ in range(20):
            self.page.wait_for_timeout(1000)
            has_form = self.page.evaluate("""
                () => {
                    const regionInput = document.querySelector('input[placeholder*="选择"]');
                    const nameInput = document.querySelector('input[placeholder*="桶名称"]');
                    return !!(regionInput || nameInput);
                }
            """)
            if has_form:
                return

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
        # 临时诊断：从进入创建页前开始监听区域接口响应，避免 mounted 调用已结束才监听
        region_responses = []
        all_api_urls = []
        def _capture_region(resp):
            url = resp.url
            if "/api/" in url:
                all_api_urls.append({"url": url, "status": resp.status})
            if "region" in url.lower():
                try:
                    body = resp.text()
                except Exception:
                    body = "<unable to read body>"
                region_responses.append({"url": url, "status": resp.status, "body": body[:500]})
        self.page.on("response", _capture_region)

        # 直接导航到创建页（OSS 微前端 <cl-button> 非标准 button，btn_create 定位不到）
        try:
            self._goto_create_bucket()
        except Exception as goto_exc:
            logger.error(f"进入创建桶页面失败，已捕获 API: {all_api_urls[:30]}")
            self.page.remove_listener("response", _capture_region)
            raise

        # ── 填写表单 ──

        # 1. 选择区域
        # 优先定位 el-select 容器（而非 input），点击容器触发下拉展开更稳定
        region_select = self.page.locator('.el-select').filter(
            has=self.page.locator('input[placeholder="请选择"]')
        ).first
        if region_select.count() == 0:
            region_select = self.page.locator('input[placeholder="请选择"]').first
        if region_select.count() == 0:
            region_select = self.page.get_by_role('combobox').first
        expect(region_select).to_be_visible(timeout=10000)

        region_select.click()
        # 等待下拉面板展开且选项已加载（区域接口可能较慢，给足 30s）
        try:
            self.page.locator('.el-select-dropdown__item').first.wait_for(state='visible', timeout=30000)
        except Exception as wait_exc:
            # 诊断：下拉选项未加载，记录当前下拉面板 HTML 与网络响应
            dropdown_html = self.page.evaluate("""
                () => {
                    const dropdown = document.querySelector('.el-select-dropdown');
                    return dropdown ? dropdown.outerHTML : 'no .el-select-dropdown found';
                }
            """)
            logger.error(f"区域下拉选项 30s 内未加载，下拉面板 HTML: {dropdown_html}")
            logger.error(f"区域相关接口响应: {region_responses}")
            logger.error(f"进入创建页后所有 API 响应(前30): {all_api_urls[:30]}")
            self.page.remove_listener("response", _capture_region)
            raise AssertionError(f"区域下拉选项未加载 | 期望区域: {region}") from wait_exc
        # 在展开的下拉项中定位目标区域：优先按选项 value 属性匹配（el-option 会渲染 value 到 li），
        # 未命中再按可见文本匹配（兼容 description 与 id 不同的情况）。
        region_option = self.page.locator(f'.el-select-dropdown__item[value="{region}"]').first
        if region_option.count() == 0:
            region_option = self.page.locator(
                '.el-select-dropdown__item'
            ).filter(has_text=region).first
        if region_option.count() == 0:
            # 诊断：记录当前下拉选项的真实文案与 value，便于定位选项文本差异
            all_items = self.page.locator('.el-select-dropdown__item').all()
            item_texts = [item.inner_text().strip() for item in all_items]
            item_values = [
                item.evaluate('el => el.getAttribute("value")') for item in all_items
            ]
            logger.warning(
                f"未找到区域选项 {region!r}，当前下拉选项: texts={item_texts}, values={item_values}"
            )
        region_option.wait_for(state='visible', timeout=10000)
        region_option.click()
        self.page.wait_for_timeout(300)
        self.page.remove_listener("response", _capture_region)

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

        通过桶列表页点击桶名称进入，确保 ``sessionStorage.owner`` 被正确设置，
        否则 admin 用户在生命周期规则等页面会因 ``v-limit`` 权限控制看不到
        ``新建`` 等操作按钮。

        Args:
            name: 桶名称。
        """
        self.oss_bucket_enter_detail_via_ui(name)

    def oss_bucket_detail_click_tag_tab(self, name=None):
        """导航到桶详情页的标签子页面。

        通过桶列表页点击进入详情页（确保 ``sessionStorage.owner`` 被正确设置，
        否则详情页 mounted 钩子会因权限过滤重定向到首个可用菜单），然后点击左侧
        ``标签`` 菜单，最后检测 URL 是否稳定在 ``/basicconfig/tag``。

        Args:
            name: 桶名称。若未提供，从当前 URL 提取。

        Returns:
            bool: True 表示成功进入标签页；False 表示标签菜单被隐藏，无法访问。
        """
        current = self.page.url
        if not name:
            m = re.search(r"/bucket-list-page-detail/([^/]+)", current)
            name = m.group(1) if m else None
        if not name:
            raise RuntimeError("无法从 URL 提取桶名，请显式传入 name 参数")

        self._enter_bucket_detail_via_ui(name)
        clicked = self._click_left_menu("标签")
        if not clicked:
            return False

        # 等待 URL 稳定：标签页保留 /basicconfig/tag，被权限重定向后会离开
        for _ in range(20):
            url = self.page.url
            if "/basicconfig/tag" in url:
                return True
            if "/no-permission" in url:
                return False
            self.page.wait_for_timeout(500)
        return "/basicconfig/tag" in self.page.url

    def oss_bucket_detail_get_tags(self):
        """获取桶详情页展示的标签列表。

        标签数据可能异步加载，采用轮询重试策略。优先读取标签组件 Vue
        实例的 ``tableData``，并在表格渲染后从 DOM 行交叉验证。

        Returns:
            list[dict]: 标签列表，每项为 {"key": ..., "value": ...} 格式。
        """
        # 等待标签组件挂载且首次加载完成
        self.page.locator(".Tags-container").first.wait_for(state="visible", timeout=15000)
        for _ in range(15):
            tags = []

            # 策略1：从标签页 Vue 实例直接读取 tableData
            vue_tags = self.page.evaluate("""
                () => {
                    const container = document.querySelector('.Tags-container');
                    if (container && container.__vue__) {
                        const vm = container.__vue__;
                        const data = vm.tableData || vm.tags;
                        if (Array.isArray(data) && data.length > 0) {
                            return data
                                .filter(t => t && t.key !== undefined)
                                .map(t => ({ key: t.key, value: t.value === undefined ? '' : t.value }));
                        }
                    }
                    return [];
                }
            """)
            if vue_tags:
                tags = vue_tags

            # 策略2：在表格中查找
            if not tags:
                rows = self.page.locator(".Tags-container .el-table__body-wrapper .el-table__row")
                for i in range(rows.count()):
                    row = rows.nth(i)
                    try:
                        # tag table columns: checkbox | key | value | operation
                        key_cell = row.locator("td").nth(1)
                        value_cell = row.locator("td").nth(2)
                        key_text = key_cell.inner_text().strip()
                        value_text = value_cell.inner_text().strip()
                        if key_text and key_text not in ("标签键", "暂无数据", "操作"):
                            tags.append({"key": key_text, "value": value_text})
                    except Exception:
                        continue

            # 策略3：在标签卡片区域查找键值对
            if not tags:
                tag_items = self.page.locator(".Tags-container .tag-item, .Tags-container .el-tag").all()
                for item in tag_items:
                    try:
                        text = item.inner_text().strip()
                        if ":" in text:
                            parts = text.split(":", 1)
                            tags.append({"key": parts[0].strip(), "value": parts[1].strip()})
                    except Exception:
                        continue

            if tags:
                return tags

            # 仍在加载中：等待 loading 消失后再试
            loading = self.page.locator(".Tags-container .el-loading-mask").first
            if loading.count() > 0 and loading.is_visible():
                loading.wait_for(state="hidden", timeout=5000)
            else:
                self.page.wait_for_timeout(1000)

        return []

    def oss_bucket_delete(self, name):
        """删除指定桶。

        流程：导航到桶列表 -> 搜索过滤目标桶 -> 点击删除 -> 确认删除。
        采用"先搜索再操作"策略，避免表格分页/异步加载导致行定位失败。

        Args:
            name: 桶名称。
        """
        self._goto_bucket_list()

        # 关闭可能残留的弹窗/抽屉，避免遮挡搜索/删除操作（teardown 场景常见）
        try:
            self.close_dialog_if_exists()
        except Exception:
            pass
        try:
            self._close_task_drawer_if_exists()
        except Exception:
            pass

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

    def oss_bucket_upload_object(self, bucket_name, file_path, skip_navigation=False, folder_path=None):
        """上传对象到指定桶。

        流程：通过 UI 导航到桶对象列表 -> 点击"上传对象" -> 选择文件 -> 点击上传 ->
        等待上传弹窗关闭。全部采用原生 Playwright 交互；OSS <cl-button> 标准点击
        即可触发 ``@click`` / ``@click.native`` 事件。

        Args:
            bucket_name: 目标桶名称。
            file_path: 本地文件绝对路径。
            skip_navigation: 为 True 时跳过对象列表页导航（调用方已确保在对象页）。
            folder_path: 可选，上传到指定文件夹内（prefix）。
        """
        if not skip_navigation:
            self.oss_bucket_click_object_tab(bucket_name)
            if folder_path:
                self.oss_bucket_enter_folder(bucket_name, folder_path)
            self.page.wait_for_timeout(2000)

        # 关闭可能遮挡的上传任务抽屉
        self._close_task_drawer_if_exists()

        # 点击"上传对象"按钮（优先精确文案，再按 role），等待按钮可用
        btn = self.page.get_by_text("上传对象", exact=True).first
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="上传对象").first
        if btn.count() == 0:
            raise AssertionError(
                f"未找到'上传对象'按钮 | 当前URL: {self.page.url}"
            )
        self._wait_for_button_enabled(btn, timeout=15000)
        btn.click()

        # 等待上传弹窗渲染
        dialog = self.page.locator(".uploadObject-dialog-default-class")
        dialog.wait_for(state="visible", timeout=10000)

        # 等待文件 input 挂载并设置文件
        input_el = dialog.locator("#obsUploadInput").first
        input_el.wait_for(state="attached", timeout=10000)
        input_el.set_input_files(file_path)
        self.page.wait_for_timeout(2000)

        # 点击弹窗"上传"按钮（Playwright 会自动等待按钮可用）
        submit = dialog.get_by_text("上传", exact=True).first
        if submit.count() == 0:
            submit = dialog.locator("button").filter(has_text="上传").first
        if submit.count() == 0:
            raise AssertionError("未找到弹窗'上传'按钮")
        submit.click(timeout=15000)

        # 等待弹窗关闭（任务已提交，后台异步上传）
        dialog.wait_for(state="hidden", timeout=30000)
        self.page.wait_for_timeout(5000)

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

    def oss_bucket_get_objects(self, bucket_name, folder_path=None):
        """获取桶中的对象名称列表。

        通过 UI 导航到桶对象列表页，提取表格中展示的对象名称。
        对象列表数据可能由后端异步填充，采用轮询重试策略。

        Args:
            bucket_name: 桶名称。
            folder_path: 可选，指定文件夹路径；提供时会先进入该文件夹。

        Returns:
            list[str]: 对象名称列表；若列表为空则返回空列表。
        """
        if folder_path:
            self.oss_bucket_enter_folder(bucket_name, folder_path)
        else:
            self.oss_bucket_click_object_tab(bucket_name)

        # 轮询等待对象列表加载（后端异步填充，首次可能为空）
        for attempt in range(20):
            objects = self._get_current_object_names()
            if objects:
                return objects
            self.page.wait_for_timeout(2000)
        return []

    def _get_current_object_names(self):
        """从当前对象列表容器中提取对象/文件夹名称（不触发导航）。"""
        objects = []
        container = self.page.locator(".object-list-page-container").first
        if container.count() == 0:
            return objects

        # 策略1：通过 objectKeyClass label 提取
        labels = container.locator(".objectKeyClass .label").all()
        exclude = {
            "名称", "返回上一级", "--", "配置对象策略", "更多",
            "速度:", "速度",
        }
        for label in labels:
            try:
                text = label.inner_text().strip()
                if text and text not in exclude:
                    objects.append(text)
            except Exception:
                continue
        if objects:
            return objects

        # 策略2：按表格行文本提取首个有效 token
        size_pattern = re.compile(r"^\d+(\.\d+)?\s*(B|KB|MB|GB|TB)$", re.I)
        pure_num_pattern = re.compile(r"^\d+(%|)$")
        rows = container.locator(".el-table__body-wrapper .el-table__row, .cl-table-body tr").all()
        for row in rows:
            try:
                lbl = row.locator(".objectKeyClass .label").first
                if lbl.count() > 0:
                    text = lbl.inner_text().strip()
                    if text and text not in exclude:
                        objects.append(text)
                        continue

                row_text = (row.inner_text() or "").strip()
                if not row_text:
                    continue
                tokens = re.split(r"[\s\n\r\t]+", row_text)
                for token in tokens:
                    token = token.strip()
                    if not token or token in exclude:
                        continue
                    if size_pattern.match(token) or pure_num_pattern.match(token):
                        continue
                    objects.append(token)
                    break
            except Exception:
                continue
        return objects

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

    def oss_bucket_delete_object(self, bucket_name, object_name, folder_path=None):
        """删除桶中的指定对象（支持在指定文件夹内删除）。

        优先使用复选框选中 + 批量删除（更可靠），
        fallback 到操作下拉菜单单条删除。

        Args:
            bucket_name: 桶名称。
            object_name: 对象名称。
            folder_path: 可选，指定文件夹路径。
        """
        if folder_path:
            self.oss_bucket_enter_folder(bucket_name, folder_path)
        else:
            self.oss_bucket_click_object_tab(bucket_name)
        self._delete_row_by_name(object_name)

    # ── 碎片相关方法 ──

    def oss_bucket_open_upload_dialog(self, bucket_name):
        """在桶详情页打开上传对象弹窗。

        流程：通过 UI 导航到桶对象列表页 -> 等待"上传对象"按钮渲染 -> 原生点击 -> 等待弹窗出现。

        Args:
            bucket_name: 桶名称。
        """
        # 通过 UI 导航到对象列表页，确保对象列表组件（含上传按钮）完整加载
        self.oss_bucket_click_object_tab(bucket_name)

        # 等待"上传对象"按钮渲染并可用
        upload_btn = self.page.get_by_text("上传对象", exact=True).first
        try:
            upload_btn.wait_for(state="visible", timeout=15000)
        except Exception:
            upload_btn = self.page.get_by_role("button", name="上传对象").first
            upload_btn.wait_for(state="visible", timeout=15000)

        # 原生点击触发上传弹窗
        upload_btn.click(timeout=15000)

        # 等待上传弹窗可见
        self.page.wait_for_selector(
            '.uploadObject-dialog-default-class',
            state='visible',
            timeout=15000,
        )
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

        优先使用 Playwright 原生点击上传按钮；失败后回退到 JS 调用 Vue submit。
        提交后等待弹窗关闭，任务列表抽屉页会自动弹出。
        """
        dialog = self.page.locator('.uploadObject-dialog-default-class').first
        dialog.wait_for(state='visible', timeout=15000)

        # 优先原生点击"上传"按钮
        submit_btn = dialog.get_by_text("上传", exact=True).first
        try:
            submit_btn.wait_for(state="visible", timeout=10000)
            submit_btn.click(timeout=15000)
        except Exception:
            # fallback: JS 调用 Vue submit
            result = self.page.evaluate("""
                () => {
                    const dialog = document.querySelector('.uploadObject-dialog-default-class');
                    if (!dialog) return 'dialog-not-found';
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
        drawer = self.page.locator('.el-drawer__wrapper').first
        drawer.wait_for(state='visible', timeout=15000)

        # 原生点击"全部暂停"按钮
        pause_btn = drawer.get_by_text("全部暂停", exact=True).first
        pause_btn.wait_for(state="visible", timeout=10000)
        pause_btn.click(timeout=15000)
        self.page.wait_for_timeout(1000)

    def oss_bucket_task_cancel_one(self, bucket_name):
        """在任务列表中选择任一上传任务，点击"取消"按钮。

        取消处于 PAUSE 状态的任务。

        Args:
            bucket_name: 桶名称。
        """
        drawer = self.page.locator('.el-drawer__wrapper').first
        drawer.wait_for(state='visible', timeout=15000)

        # 等待"取消"链接可见后原生点击
        cancel_link = drawer.get_by_text("取消", exact=True).first
        cancel_link.wait_for(state="visible", timeout=20000)
        cancel_link.click(timeout=15000)
        self.page.wait_for_timeout(3000)

    def oss_bucket_task_has_status(self, bucket_name, status):
        """检查任务列表中是否存在指定状态的任务。

        Args:
            bucket_name: 桶名称。
            status: 状态值，如 "PAUSE" / "CANCEL" / "UPLOADING" 等。

        Returns:
            bool: 存在则返回 True。
        """
        status_map = {
            "PAUSE": ["PAUSE", "暂停"],
            "CANCEL": ["CANCEL", "取消"],
            "UPLOADING": ["UPLOADING", "上传中"],
        }
        texts = status_map.get(status, [status])

        drawer = self.page.locator('.el-drawer__wrapper').first
        if drawer.count() == 0 or not drawer.is_visible():
            return False
        rows = drawer.locator('.el-table__row').all()
        for row in rows:
            row_text = row.inner_text()
            if any(t in row_text for t in texts):
                return True
        return False

    def oss_bucket_close_task_drawer(self):
        """关闭上传任务列表抽屉（如果存在）。"""
        drawer = self.page.locator('.el-drawer__wrapper').first
        if drawer.count() == 0 or not drawer.is_visible():
            return
        try:
            close_btn = drawer.locator('.el-drawer__close-btn, .el-drawer__headerbtn').first
            if close_btn.count() > 0:
                close_btn.click(timeout=5000)
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

    def _wait_for_fragment_list_ready(self, timeout=30000):
        """等待碎片列表页加载完成（loading 消失、表格行或空态渲染）。"""
        start = self.page.evaluate("() => Date.now()")
        while True:
            loading = self.page.locator(".el-loading-mask").first
            loading_visible = loading.count() > 0 and loading.is_visible()

            rows = self.page.locator(".el-table__body-wrapper .el-table__row, .cl-table-body .cl-table-row").all()
            empty = self.page.locator(".el-empty, .el-table__empty-text, .empty-text").first
            empty_visible = empty.count() > 0 and empty.is_visible()
            no_data = self.page.get_by_text("暂无数据", exact=False).first
            no_data_visible = no_data.count() > 0 and no_data.is_visible()
            list_ready = bool(rows) or empty_visible or no_data_visible

            if not loading_visible and list_ready:
                return

            elapsed = self.page.evaluate("() => Date.now()") - start
            if elapsed >= timeout:
                raise AssertionError(
                    f"碎片列表页在 {timeout}ms 内未就绪 | loading={loading_visible}, rows={len(rows)}"
                )
            self.page.wait_for_timeout(500)

    def oss_bucket_goto_fragment_tab(self, bucket_name):
        """导航到桶详情页的碎片 tab 页。

        通过 UI 导航进入桶详情 -> 对象页 -> 碎片 tab，避免直接 URL goto
        因 sessionStorage.owner 未设置而被权限拦截回列表页。

        Args:
            bucket_name: 桶名称。
        """
        # 关闭任务列表抽屉（如果存在）
        self._close_task_drawer_if_exists()

        # 通过 UI 导航到对象页
        self.oss_bucket_click_object_tab(bucket_name)

        # 点击顶部"碎片" tab
        if not self._click_top_tab("碎片"):
            # 兜底：通过 URL 中 tab id 尝试（保留原逻辑作为 fallback）
            base_url = Config.get("base_url").rstrip("/")
            self.page.goto(f"{base_url}/oss/#/bucket-list-page-detail/{bucket_name}/object/fragement")
            self.page.wait_for_timeout(3000)

        self._wait_for_fragment_list_ready()

    def oss_bucket_get_fragments(self, bucket_name):
        """获取桶碎片列表。

        通过 UI 导航到碎片页面，提取表格中展示的碎片数据。

        Args:
            bucket_name: 桶名称。

        Returns:
            list[dict]: 碎片列表，每项包含 objectKey、num（碎片数量）、size、uploadId 等。
        """
        self.oss_bucket_goto_fragment_tab(bucket_name)

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

    # =====================================================================
    # 以下方法为修复 OSS 14 个测试文件所补充的 Page Object 方法。
    # 实现原则：优先原生 Playwright 点击/填写；OSS 微前端部分自定义组件
    # 在标准交互无效时保留最小化 JS 兜底，以保证测试稳定性。
    # =====================================================================

    def _ensure_bucket_list(self):
        """确保当前位于 OSS 桶列表页。"""
        self._goto_bucket_list()

    def _enter_bucket_detail_via_ui(self, bucket_name):
        """通过桶列表页点击桶名称进入详情页（避免直接 URL 权限拦截）。

        每次均重新从桶列表点击桶名称，确保 ``sessionStorage.owner`` 被正确设置，
        否则 admin 用户在对象列表/标签等页面会被 ``is_disabled()`` 判定为无权限，
        导致操作按钮被禁用、左侧菜单被隐藏。

        若当前已在目标桶详情页，直接返回，避免重复从列表页导航导致 Jenkins
        桶数量多时列表搜索/分页不稳定。
        """
        if f"/bucket-list-page-detail/{bucket_name}" in self.page.url:
            # 仍在目标桶详情页，左侧菜单已渲染即可
            if (
                self.page.locator("text=桶详情").count() > 0
                or self.page.locator(".bucket-detail-left-menu").count() > 0
            ):
                self._ensure_session_owner()
                return
        self._ensure_bucket_list()
        self.page.wait_for_timeout(2000)
        link = self.page.get_by_text(bucket_name, exact=True).first
        if link.count() == 0:
            self._search_in_bucket_list(bucket_name)
            link = self.page.get_by_text(bucket_name, exact=True).first
        if link.count() == 0:
            raise AssertionError(f"桶列表中未找到 {bucket_name}")
        link.click()
        self.page.wait_for_timeout(3000)
        # 等待 URL 变化或页面渲染完成
        for _ in range(15):
            if f"/bucket-list-page-detail/{bucket_name}" in self.page.url:
                self._ensure_session_owner()
                return
            if "/no-permission" in self.page.url:
                raise AssertionError(f"进入桶 {bucket_name} 详情页被权限拦截")
            self.page.wait_for_timeout(1000)
        # URL 未变但 DOM 已渲染详情页也接受
        if self.page.locator("text=桶详情").count() > 0 or self.page.locator(".bucket-detail-left-menu").count() > 0:
            self._ensure_session_owner()
            return
        raise AssertionError(f"进入桶 {bucket_name} 详情页超时")

    def _search_in_bucket_list(self, name):
        """在桶列表页搜索指定桶名称。"""
        search = self.page.locator(
            'input[placeholder*="桶名称"], input[placeholder*="搜索桶"], '
            'input[placeholder*="按桶名称"], input[placeholder*="搜索"]'
        ).first
        if search.count() == 0:
            return
        try:
            search.wait_for(state="visible", timeout=10000)
            search.click()
            # 清空旧内容（Ctrl+A 后 Delete，兼容中文输入法）
            search.fill("")
            self.page.keyboard.press("Control+a")
            self.page.keyboard.press("Delete")
            self.page.wait_for_timeout(300)
            search.fill(name)
            self.page.keyboard.press("Enter")
            # 等待列表加载完成
            self._wait_for_bucket_list_loaded()
        except Exception:
            # 搜索失败不阻断，外层仍会尝试直接定位
            pass

    def _close_task_drawer_if_exists(self):
        """关闭上传任务列表抽屉（如果存在），避免遮挡页面操作。"""
        try:
            # 优先通过 aria-label 定位关闭按钮
            close_btn = self.page.locator("button[aria-label='close 任务列表']").first
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
                self.page.wait_for_timeout(1500)
                return
            # 兜底：通用抽屉关闭按钮
            close_btn = self.page.locator(
                ".el-drawer__close-btn:visible, .el-drawer__headerbtn:visible"
            ).first
            if close_btn.count() > 0 and close_btn.is_visible():
                close_btn.click()
                self.page.wait_for_timeout(1500)
        except Exception:
            pass

    def _wait_for_button_enabled(self, btn, timeout=15000):
        """等待自定义 cl-button 按钮变为可用状态（移除 disabled 类/属性）。"""
        start = self.page.evaluate("() => Date.now()")
        while True:
            if btn.count() == 0:
                raise AssertionError("等待可用状态的按钮已消失")
            cls = btn.get_attribute("class") or ""
            disabled_attr = btn.get_attribute("disabled") or ""
            if (
                "disabled" not in cls.lower()
                and "cl-btn-disa" not in cls
                and disabled_attr != "true"
            ):
                return
            elapsed = self.page.evaluate("() => Date.now()") - start
            if elapsed >= timeout:
                raise AssertionError(
                    f"'上传对象'按钮在 {timeout}ms 内未变为可用 | class={cls}"
                )
            self.page.wait_for_timeout(500)

    def _wait_for_object_list_ready(self, timeout=30000):
        """等待对象列表页加载完成（loading 消失、表格行或空态渲染、上传按钮可用）。"""
        start = self.page.evaluate("() => Date.now()")
        while True:
            # loading mask 消失
            loading = self.page.locator(".el-loading-mask").first
            loading_visible = loading.count() > 0 and loading.is_visible()

            # 表格行或空态已渲染
            rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
            empty = self.page.locator(".el-empty, .el-table__empty-text, .empty-text").first
            empty_visible = empty.count() > 0 and empty.is_visible()
            no_data = self.page.get_by_text("暂无数据", exact=False).first
            no_data_visible = no_data.count() > 0 and no_data.is_visible()
            list_ready = bool(rows) or empty_visible or no_data_visible

            # 上传对象按钮可用（未处于 disabled 状态）
            upload_btn = self.page.get_by_text("上传对象", exact=True).first
            upload_enabled = False
            if upload_btn.count() > 0:
                cls = upload_btn.get_attribute("class") or ""
                disabled_attr = upload_btn.get_attribute("disabled") or ""
                upload_enabled = (
                    "disabled" not in cls.lower()
                    and "cl-btn-disa" not in cls
                    and disabled_attr != "true"
                )

            if not loading_visible and list_ready and upload_enabled:
                return

            elapsed = self.page.evaluate("() => Date.now()") - start
            if elapsed >= timeout:
                raise AssertionError(
                    f"对象列表页在 {timeout}ms 内未就绪 | loading={loading_visible}, "
                    f"rows={len(rows)}, upload_enabled={upload_enabled}"
                )
            self.page.wait_for_timeout(500)

    def _click_left_menu(self, menu_text):
        """点击桶详情页左侧菜单项（支持折叠分组内的子项）。

        优先在左侧菜单容器 ``.left-menu-box`` / ``.el-menu-vertical-demo``
        内查找，避免命中页面其它同名文案。
        """
        # 先关闭可能遮挡左侧菜单的抽屉/弹窗
        self._close_task_drawer_if_exists()
        menu = self.page.locator(".left-menu-box .el-menu, .el-menu-vertical-demo").first
        if menu.count() > 0:
            item = menu.get_by_text(menu_text, exact=True).first
            if item.count() > 0:
                item.click()
                self.page.wait_for_timeout(2000)
                return True
        # fallback：全局精确文案
        item = self.page.get_by_text(menu_text, exact=True).first
        if item.count() > 0:
            item.click()
            self.page.wait_for_timeout(2000)
            return True
        return False

    def _click_top_tab(self, tab_text):
        """点击对象页顶部 tab（对象 / 已删除对象 / 碎片）。"""
        tab = self.page.locator(".el-tabs__nav").get_by_text(tab_text, exact=True).first
        if tab.count() == 0:
            tab = self.page.get_by_text(tab_text, exact=True).first
        if tab.count() > 0:
            tab.click()
            self.page.wait_for_timeout(2000)
            return True
        return False

    def oss_bucket_object_tab_click(self):
        """在桶详情页点击左侧菜单'对象'，进入对象列表页。

        桶详情布局使用左侧菜单导航；``_click_top_tab`` 仅用于已进入对象页后的
        顶部 tab 切换，不能从桶详情直接到达对象列表。
        """
        if "/object" in self.page.url:
            self._wait_for_object_list_ready()
            return
        # 若调用方刚刚点击桶名称，可能仍在列表页加载中，先确保进入桶详情
        if "/bucket-list-page-detail/" not in self.page.url:
            # 无桶名参数，依赖当前页面已渲染左侧菜单；未渲染则让后续点击失败
            pass
        self._click_left_menu("对象")
        self._wait_for_object_list_ready()

    def oss_bucket_click_object_tab(self, bucket_name):
        """确保进入桶详情页并通过左侧菜单切换到对象列表页（根路径，清除 prefix）。"""
        self._enter_bucket_detail_via_ui(bucket_name)
        # 始终点击左侧菜单"对象"，确保回到 /object/list 根路径（即使当前在子文件夹内）
        self._click_left_menu("对象")
        self._wait_for_object_list_ready()

    def oss_bucket_click_deleted_objects_tab(self, bucket_name):
        """通过顶部 tab 切换到'已删除对象'页。"""
        # 若已在已删除对象 tab，避免重新导航导致已勾选的行被取消
        if "/object/delist" in self.page.url:
            active_tab = self.page.locator("#tab-delist.is-active, #tab-delist.el-tabs__item.is-active").first
            if active_tab.count() > 0:
                self.page.wait_for_timeout(1000)
                return
        self._enter_bucket_detail_via_ui(bucket_name)
        self._click_top_tab("已删除对象")
        self.page.wait_for_timeout(3000)

    def oss_bucket_enable_versioning(self, bucket_name):
        """开启桶多版本控制。

        桶详情页右上角开关直接触发后端接口；点击后等待状态变为"已启用"，
        并处理可能弹出的确认对话框。
        """
        self._enter_bucket_detail_via_ui(bucket_name)

        # 多版本开关为 Element UI el-switch，实际可点击元素是 .el-switch__core
        switch = self.page.locator(".bucket-name-box .el-switch__core").first
        if switch.count() == 0:
            switch = self.page.locator(".version-control-switch, [class*='version']").first
        if switch.count() == 0:
            # fallback：通过文案查找开关父级内的可点击 core
            label = self.page.get_by_text("多版本控制", exact=True).first
            if label.count() > 0:
                switch = label.locator("xpath=../.././/span[contains(@class,'el-switch__core')]").first

        if switch.count() == 0:
            raise AssertionError(f"未找到桶 '{bucket_name}' 的多版本控制开关")

        # 若已经是已启用，直接返回
        status = self.page.locator(".bucket-name-box").get_by_text("已启用").first
        if status.count() > 0 and status.is_visible():
            return

        switch.click()
        self.page.wait_for_timeout(1000)

        # 处理可能弹出的确认对话框（启用/暂停选择）
        dialog = self.page.locator(".versionStatus-dialog, .el-dialog:has-text('多版本控制')").first
        if dialog.count() > 0 and dialog.is_visible():
            enabled_radio = dialog.get_by_text("启用", exact=True).first
            if enabled_radio.count() > 0:
                enabled_radio.click()
                self.page.wait_for_timeout(500)
            confirm = dialog.get_by_text("确定", exact=True).first
            if confirm.count() > 0:
                confirm.click()
            # 等待对话框关闭及请求完成
            dialog.wait_for(state="hidden", timeout=20000)
            self.page.wait_for_timeout(2000)

        # 等待状态收敛到"已启用"（最长 30s）
        for _ in range(60):
            status = self.page.locator(".bucket-name-box").get_by_text("已启用").first
            if status.count() > 0 and status.is_visible():
                break
            self.page.wait_for_timeout(500)
        else:
            raise AssertionError(
                f"开启多版本控制后状态未变为'已启用' | bucket={bucket_name}"
            )

        # 确保页面 loading 消失，再返回
        try:
            loading = self.page.locator(".el-loading-mask").first
            if loading.count() > 0:
                loading.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass
        self.page.wait_for_timeout(1500)

    def oss_bucket_create_folder(self, bucket_name, folder_name):
        """在桶对象列表页创建文件夹。"""
        self.oss_bucket_click_object_tab(bucket_name)
        # 关闭可能遮挡的抽屉
        self._close_task_drawer_if_exists()
        btn = self.page.get_by_text("新建文件夹", exact=True).first
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="新建文件夹").first
        if btn.count() == 0:
            raise AssertionError("未找到'新建文件夹'按钮")
        btn.click()
        self.page.wait_for_timeout(2000)
        dialog = self.page.locator(".el-dialog").filter(has=self.page.get_by_text("新建文件夹")).first
        if dialog.count() == 0:
            dialog = self.page.locator(".el-dialog:visible").first
        input_el = dialog.locator("input").first
        input_el.fill(folder_name)
        self.page.wait_for_timeout(500)
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)

    def oss_bucket_enter_folder(self, bucket_name, folder_name):
        """在桶对象列表页点击进入文件夹，并验证已进入文件夹内部。"""
        self.oss_bucket_click_object_tab(bucket_name)
        self._ensure_enter_folder(folder_name)

    def _ensure_enter_folder(self, folder_name, max_attempts=3):
        """通过点击文件夹名称进入文件夹，并通过"返回上一级"行校验成功。"""
        for attempt in range(max_attempts):
            # 关闭可能遮挡的抽屉
            self._close_task_drawer_if_exists()

            # 定位文件夹行
            row = self.page.locator(".object-list-page-container .el-table__row").filter(has_text=folder_name).first
            if row.count() == 0:
                # 可能已在文件夹内
                if self.page.get_by_text("返回上一级", exact=True).count() > 0:
                    return
                raise AssertionError(f"对象列表中未找到文件夹 {folder_name}")

            # 点击 objectKeyClass 区域（Vue 点击事件绑定在该 span 上）
            link = row.locator(".objectKeyClass").first
            if link.count() == 0:
                link = row.locator("span").filter(has_text=folder_name).first
            if link.count() > 0:
                link.click()
            else:
                row.click()

            # 等待并校验：出现"返回上一级"或原文件夹行消失
            for _ in range(15):
                self.page.wait_for_timeout(1000)
                if self.page.get_by_text("返回上一级", exact=True).count() > 0:
                    return
                if self.page.locator(".object-list-page-container .el-table__row").filter(has_text=folder_name).first.count() == 0:
                    return

        raise AssertionError(f"无法通过点击进入文件夹 {folder_name}")

    def oss_bucket_delete_folder(self, bucket_name, folder_name):
        """删除桶对象列表页中的文件夹。"""
        self.oss_bucket_click_object_tab(bucket_name)
        self._delete_row_by_name(folder_name)

    def oss_bucket_copy_object_path(self, bucket_name, object_name, folder_path=None):
        """复制对象路径到剪贴板并返回路径字符串。

        当前 OSS 对象列表的行内操作项位于"更多"下拉菜单中，点击后前端通过
        ``copyContent`` 将 ``objectKey`` 写入剪贴板并弹出"复制成功"提示。
        由于无头环境无法读取剪贴板，方法在确认操作完成后按对象实际 ``objectKey``
        返回路径（根目录下为对象名，文件夹内为 folder/object）。
        """
        if folder_path:
            self.oss_bucket_enter_folder(bucket_name, folder_path)
        else:
            self.oss_bucket_click_object_tab(bucket_name)
        row = self._get_object_operation_row(object_name)
        if row.count() == 0:
            raise AssertionError(f"未找到对象 {object_name}")
        self._click_row_dropdown_item(row, "复制路径")
        # 等待"复制成功"提示出现
        for _ in range(20):
            msg = self.page.locator(".el-message__content").first
            if msg.count() > 0 and "复制成功" in (msg.inner_text() or ""):
                break
            self.page.wait_for_timeout(500)
        expected_path = f"{folder_path}/{object_name}" if folder_path else object_name
        return expected_path

    def _delete_row_by_name(self, name):
        """通用：在对象/碎片/已删除对象列表中删除指定名称的行。

        对象列表在窄视口下会隐藏行内"操作"下拉，因此优先使用复选框选中 +
        批量删除；失败后回退到行内下拉删除。
        """
        # 先关闭可能遮挡列表的抽屉
        self._close_task_drawer_if_exists()

        # 策略1：复选框选中 + 批量删除
        try:
            checked = self.page.evaluate(f"""
                () => {{
                    const rows = document.querySelectorAll('.object-list-page-container .el-table__row, .el-table__row');
                    for (const row of rows) {{
                        if (row.innerText.includes({name!r})) {{
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
                clicked = self.page.evaluate("""
                    () => {
                        const btns = document.querySelectorAll('button, .el-button, .cl-button, .cloud-button-btn');
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
                if 'clicked' in str(clicked):
                    self.page.wait_for_timeout(2000)
                    confirm = self.page.get_by_text("确定", exact=True).first
                    if confirm.count() > 0:
                        confirm.click()
                    self.page.wait_for_timeout(3000)
                    return
        except Exception:
            pass

        # 策略2：行内下拉菜单删除（使用固定右侧可见操作列）
        row = self._get_object_operation_row(name)
        if row.count() == 0:
            raise AssertionError(f"列表中未找到 {name}")
        self._click_row_dropdown_item(row, "删除")
        self.page.wait_for_timeout(2000)
        confirm = self.page.get_by_text("确定", exact=True).first
        if confirm.count() > 0:
            confirm.click()
        self.page.wait_for_timeout(3000)

    def _get_object_operation_row(self, name):
        """定位对象列表中目标名称对应的可见操作行。

        OSS 对象列表使用了 ``el-table__fixed-right`` 固定右侧操作列，实际操作按钮
        （配置对象策略 / 更多）位于固定列的副本行中，而非主表格体的隐藏操作单元格内。
        因此优先返回 ``.el-table__fixed-right`` 内包含目标名称的行。
        """
        fixed = self.page.locator(".el-table__fixed-right").first
        if fixed.count() > 0:
            row = fixed.locator(".el-table__row").filter(has_text=name).first
            if row.count() > 0:
                return row
        # 兜底：在对象列表容器内查找可见行
        container = self.page.locator(".object-list-page-container").first
        rows = container.locator(".el-table__row").filter(has_text=name).all()
        for row in rows:
            try:
                if row.is_visible():
                    return row
            except Exception:
                continue
        if rows:
            return rows[0]
        return container.locator(".el-table__row").filter(has_text=name).first

    def _click_row_dropdown_item(self, row, item_text):
        """点击表格行内"更多"浮层菜单中的指定项。

        对象列表的固定右侧操作列中，"更多"是一个 ``el-popover__reference`` 触发器。
        先关闭可能遮挡的抽屉，再点击该触发器展开 popover，最后在可见的 popover 中
        选择目标项。
        """
        self._close_task_drawer_if_exists()

        # 点击"更多"触发器（外层 .el-popover__reference）
        trigger = row.locator(".cloud-table-dropdown-item-cl-btn.el-popover__reference:visible").first
        if trigger.count() == 0:
            trigger = row.locator(".el-popover__reference:visible").filter(has_text="更多").first
        if trigger.count() == 0:
            # 兜底：行内任意可见且包含"更多"文本的元素
            trigger = row.get_by_text("更多", exact=True).locator(":visible").first
        if trigger.count() == 0:
            raise AssertionError("未找到行内'更多'操作按钮")
        trigger.click()

        # 等待 popover 可见（aria-hidden 变为 false）
        popover = self.page.locator(".el-popover[aria-hidden='false']").first
        if popover.count() == 0:
            popover = self.page.locator(".el-popover:visible").first
        for _ in range(10):
            if popover.count() > 0:
                break
            self.page.wait_for_timeout(300)
            popover = self.page.locator(".el-popover[aria-hidden='false']").first
            if popover.count() == 0:
                popover = self.page.locator(".el-popover:visible").first

        # 在可见 popover 中定位选项
        if popover.count() > 0:
            option = popover.get_by_text(item_text, exact=True).first
            if option.count() == 0:
                option = popover.locator(".cloud-table-dropdown-item").filter(has_text=item_text).first
        else:
            option = self.page.locator(".cloud-table-dropdown-item:visible, .el-dropdown-menu__item:visible").filter(has_text=item_text).first
        if option.count() == 0:
            raise AssertionError(f"下拉菜单中未找到选项: {item_text}")
        option.click()
        self.page.wait_for_timeout(1000)
        return True

    def _click_row_action_button(self, row, text):
        """点击表格行内直接展示的操作按钮（非"更多"下拉）。

        已删除对象列表的操作列为直接按钮（如"取消删除"/"彻底删除"），没有
        "更多"触发器，使用本方法替代 ``_click_row_dropdown_item``。
        """
        self._close_task_drawer_if_exists()
        # 优先命中可见的 cl-btn-link / cloud-button-btn 类按钮
        btn = row.locator(
            ".cl-btn-link:visible, .cloud-button-btn:visible, .cloud-table-dropdown-item-cl-btn:visible"
        ).filter(has_text=text).first
        if btn.count() == 0:
            btn = row.get_by_text(text, exact=True).locator(":visible").first
        if btn.count() == 0:
            raise AssertionError(f"未找到行内'{text}'操作按钮")
        btn.click()
        self.page.wait_for_timeout(1000)
        return True

    def oss_bucket_batch_upload(self, bucket_name, file_paths, folder_path=None):
        """批量上传多个文件到桶（或指定文件夹），并等待所有文件出现在对象列表中。

        若 ``folder_path`` 未提供且当前页面已处于文件夹内部（出现"返回上一级"），
        则保持当前目录不上传；否则先导航到对象列表页根目录。
        """
        if folder_path:
            self.oss_bucket_enter_folder(bucket_name, folder_path)
        else:
            # 未指定文件夹时：仅在当前不在对象列表页/文件夹内时兜底导航到对象tab
            in_folder = self.page.get_by_text("返回上一级", exact=True).count() > 0
            object_container = self.page.locator(".object-list-page-container").count() > 0
            if not in_folder and not object_container:
                self.oss_bucket_click_object_tab(bucket_name)

        expected_names = [os.path.basename(p) for p in file_paths]

        # 关闭可能遮挡的上传任务抽屉
        self._close_task_drawer_if_exists()

        # 点击上传对象按钮
        btn = self.page.get_by_text("上传对象", exact=True).first
        if btn.count() == 0:
            btn = self.page.get_by_role("button", name="上传对象").first
        if btn.count() == 0:
            raise AssertionError("未找到'上传对象'按钮")
        self._wait_for_button_enabled(btn, timeout=15000)
        btn.click()

        self.page.wait_for_selector("#obsUploadInput", state="attached", timeout=10000)
        input_el = self.page.locator("#obsUploadInput")
        input_el.set_input_files(file_paths)
        self.page.wait_for_timeout(2000)

        # 点击弹窗上传按钮
        dialog = self.page.locator(".uploadObject-dialog-default-class").first
        submit = dialog.get_by_text("上传", exact=True).first
        if submit.count() == 0:
            submit = dialog.locator("button").filter(has_text="上传").first
        if submit.count() == 0:
            raise AssertionError("未找到上传弹窗中的'上传'按钮")
        submit.click()

        # 等待上传弹窗关闭（大文件可能需要更长时间）
        self.page.wait_for_selector(".uploadObject-dialog-default-class", state="hidden", timeout=120000)
        self.page.wait_for_timeout(2000)

        # 关闭上传任务列表抽屉，避免遮挡对象列表
        self._close_task_drawer_if_exists()

        # 轮询等待所有文件都出现在当前对象列表中
        missing = list(expected_names)
        for _ in range(60):
            objects = self._get_current_object_names()
            missing = [name for name in expected_names if name not in objects]
            if not missing:
                return
            self.page.wait_for_timeout(2000)

        raise AssertionError(
            f"批量上传后以下文件未出现在对象列表中: {missing} | 当前列表: {objects}"
        )

    def oss_bucket_get_object_url(self, bucket_name, object_name):
        """获取对象可访问 URL。

        优先调用后端 endpoint 接口取真实 OSS 网关地址，再按
        ``endpoint/bucket/objectKey`` 拼接；接口不可用则回退到 base_url 拼接。
        """
        base_url = Config.get("base_url").rstrip("/")

        # 从 localStorage 读取平台鉴权信息（OSS 微前端复用主框架 token）
        try:
            api_header = self.page.evaluate(
                """() => {
                    try { return JSON.parse(localStorage.getItem('api_header') || '{}'); } catch(e) { return {}; }
                }"""
            ) or {}
        except Exception:
            api_header = {}
        user_info = api_header.get("user_info") or {}
        try:
            region_id = self.page.evaluate(
                """() => localStorage.getItem('regionId') || 'RegionOne'"""
            ) or "RegionOne"
            project_id = self.page.evaluate(
                """() => localStorage.getItem('projectId') || ''"""
            ) or ""
        except Exception:
            region_id = "RegionOne"
            project_id = ""

        headers = {"regionId": region_id}
        auth_token = api_header.get("Authorization")
        if auth_token:
            headers["Authorization"] = auth_token
        for key in ("userId", "ProjectId", "userType", "userName"):
            val = user_info.get(key)
            if val:
                headers[key] = val
        if project_id:
            headers["Current-Project-Id"] = project_id

        endpoint_url = None
        for path in ("/api/sugoncloud-oss-api/endpoint", "/sugoncloud-oss-api/endpoint"):
            try:
                resp = self.page.request.get(
                    f"{base_url}{path}",
                    headers=headers,
                    params={"regionId": region_id},
                )
                self.logger.info(
                    f"[oss_bucket_get_object_url] {path} status: {resp.status}"
                )
                if resp.ok:
                    data = resp.json()
                    self.logger.info(
                        f"[oss_bucket_get_object_url] {path} response: {data}"
                    )
                    content = data.get("content") or {}
                    if isinstance(content, dict) and content.get("url"):
                        protocol = content.get("protocol") or "https"
                        host = content["url"].rstrip("/")
                        is_domain = content.get("isDomain")
                        if is_domain == 1:
                            endpoint_url = f"{protocol}://{bucket_name}.{host}"
                        else:
                            endpoint_url = f"{protocol}://{host}/{bucket_name}"
                        break
            except Exception as e:
                self.logger.warning(f"[oss_bucket_get_object_url] {path} failed: {e}")
        if endpoint_url:
            return f"{endpoint_url}/{object_name}"
        return f"{base_url}/{bucket_name}/{object_name}"

    def oss_bucket_get_deleted_objects(self, bucket_name):
        """获取'已删除对象'tab中的对象名称列表。"""
        self.oss_bucket_click_deleted_objects_tab(bucket_name)
        rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
        names = []
        for row in rows:
            try:
                txt = row.locator("td").nth(1).inner_text().strip()
                if txt and txt != object.__name__:
                    names.append(txt)
            except Exception:
                pass
        return names

    def oss_bucket_check_deleted_object_row(self, bucket_name, object_name):
        """在'已删除对象'tab中勾选指定对象的复选框。"""
        self.oss_bucket_click_deleted_objects_tab(bucket_name)
        row = self.page.locator(".el-table__row").filter(has_text=object_name).first
        if row.count() == 0:
            raise AssertionError(f"已删除对象列表中未找到 {object_name}")
        # 使用 JS 点击行内原生 checkbox，避免可见 label 点击未触发 Vue 状态切换
        result = row.evaluate("""
            (row) => {
                const cb = row.querySelector('input[type="checkbox"], .el-checkbox__original, .el-checkbox__input');
                if (!cb) return 'not-found';
                cb.click();
                return 'checked';
            }
        """)
        if 'checked' not in str(result):
            raise AssertionError(f"无法勾选已删除对象行 {object_name}: {result}")
        self.page.wait_for_timeout(1000)

    def oss_bucket_click_batch_permanent_delete(self, bucket_name):
        """在'已删除对象'tab点击顶部'彻底删除'按钮并确认。"""
        self.oss_bucket_click_deleted_objects_tab(bucket_name)
        # 顶部工具栏按钮（勾选行后才会启用），避免命中行内同名按钮
        toolbar = self.page.locator(".cl-table-header, .table-tool-bar").first
        btn = toolbar.get_by_text("彻底删除", exact=True).first
        if btn.count() == 0:
            btn = self.page.get_by_text("彻底删除", exact=True).first
        if btn.count() == 0:
            raise AssertionError("未找到'彻底删除'批量按钮")
        # 等待按钮由禁用变为可用（说明已有行被勾选）
        self._wait_for_button_enabled(btn, timeout=15000)
        btn.click()
        self.page.wait_for_timeout(2000)
        confirm = self.page.get_by_text("确定", exact=True).first
        if confirm.count() > 0:
            confirm.click()
        self.page.wait_for_timeout(3000)
        # 等待列表刷新：目标行消失或 loading 结束
        for _ in range(30):
            rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
            if not rows:
                break
            self.page.wait_for_timeout(1000)

    def oss_bucket_goto_lifecycle_page(self, bucket_name):
        """导航到桶的生命周期规则页面。"""
        self._enter_bucket_detail_via_ui(bucket_name)
        self._click_left_menu("生命周期规则")

    def _fill_lifecycle_days_inputs(self, dialog, expiration_days=None, noncurrent_expiration_days=None):
        """根据表单标签填充生命周期规则的当前版本/历史版本自动删除天数。

        创建/编辑弹窗中的 ``el-input`` 默认渲染为文本输入框，通过 ``input[type='number']``
        无法稳定命中，因此按 ``el-form-item`` 的 "自动删除天数" 标签定位对应输入框。
        """
        items = dialog.locator(".el-form-item").filter(has_text="自动删除天数").all()
        if expiration_days is not None and len(items) > 0:
            inp = items[0].locator("input").first
            inp.click()
            inp.fill(str(expiration_days))
            for _ in range(5):
                if inp.input_value() == str(expiration_days):
                    break
                self.page.wait_for_timeout(200)
        if noncurrent_expiration_days is not None and len(items) > 1:
            inp = items[1].locator("input").first
            inp.click()
            inp.fill(str(noncurrent_expiration_days))
            for _ in range(5):
                if inp.input_value() == str(noncurrent_expiration_days):
                    break
                self.page.wait_for_timeout(200)

    def oss_bucket_lifecycle_create_rule(
        self,
        bucket_name,
        rule_name,
        prefix=None,
        enabled=True,
        days=None,
        transitions=None,
        expiration_days=None,
        noncurrent_expiration_days=None,
    ):
        """创建生命周期规则。

        Args:
            days: ``expiration_days`` 的别名，与测试用例调用对齐。
        """
        if days is not None and expiration_days is None:
            expiration_days = days
        self.oss_bucket_goto_lifecycle_page(bucket_name)
        # 限定在生命周期规则容器内点击“新建”，避免命中页面其它同名按钮
        create_btn = (
            self.page.locator(".lifeCycleRule-container")
            .get_by_text("新建", exact=True)
            .first
        )
        create_btn.wait_for(state="visible", timeout=15000)
        create_btn.click()
        self.page.wait_for_timeout(2000)
        dialog = self.page.locator(".el-dialog:visible").first
        # 规则名称：弹窗内第一个普通文本输入框（避免命中状态 radio）
        dialog.locator("input[type='text']").nth(0).fill(rule_name)
        if prefix:
            dialog.get_by_placeholder("请输入对象名前缀").fill(prefix)
        if not enabled:
            dialog.get_by_role("radio", name="禁用").click()
        # 转换规则
        if transitions:
            for _ in transitions:
                dialog.get_by_text("添加转换规则", exact=True).first.click()
                self.page.wait_for_timeout(500)
        # 当前版本/历史版本过期删除天数
        self._fill_lifecycle_days_inputs(
            dialog,
            expiration_days=expiration_days,
            noncurrent_expiration_days=noncurrent_expiration_days,
        )
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        return {"name": rule_name, "prefix": prefix, "days": expiration_days, "enabled": enabled}

    def oss_bucket_lifecycle_get_rules(self, bucket_name):
        """获取生命周期规则列表（含名称、启用状态、前缀、天数）。"""
        self.oss_bucket_goto_lifecycle_page(bucket_name)
        rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
        rules = []
        for row in rows:
            try:
                text = row.inner_text().strip().replace("\n", " ")
                if not text:
                    continue
                parts = text.split()
                name = parts[0] if parts else ""
                status_text = parts[1] if len(parts) > 1 else ""
                enabled = status_text == "已启用"
                prefix = ""
                days = None
                for part in parts:
                    if part.startswith("按前缀配置:") or part.startswith("前缀:"):
                        prefix = part.split(":", 1)[1]
                    m = re.search(r"自动删除天数:(\d+)", part)
                    if m:
                        days = int(m.group(1))
                rules.append({
                    "name": name,
                    "enabled": enabled,
                    "prefix": prefix,
                    "days": days,
                    "status": status_text,
                })
            except Exception:
                pass
        return rules

    def oss_bucket_lifecycle_edit_rule(
        self,
        bucket_name,
        rule_name=None,
        original_rule_name=None,
        new_rule_name=None,
        prefix=None,
        days=None,
        enabled=None,
        **kwargs,
    ):
        """编辑生命周期规则（支持 ``original_rule_name`` 别名）。"""
        target = original_rule_name or rule_name
        if not target:
            raise ValueError("编辑规则时必须提供 original_rule_name 或 rule_name")
        new_name = new_rule_name or kwargs.get("name")
        self.oss_bucket_goto_lifecycle_page(bucket_name)
        self.click_action(target, "编辑")
        self.page.wait_for_timeout(2000)
        dialog = self.page.locator(".el-dialog:visible").first
        text_inputs = dialog.locator("input[type='text']").all()
        if new_name and text_inputs:
            text_inputs[0].fill(new_name)
        if prefix is not None and len(text_inputs) > 1:
            text_inputs[1].fill(prefix)
        if days is not None:
            self._fill_lifecycle_days_inputs(dialog, expiration_days=days)
        if enabled is not None:
            radio = dialog.get_by_role("radio", name="启用" if enabled else "禁用")
            if radio.count() > 0:
                radio.click()
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)

    def oss_bucket_lifecycle_click_more_dropdown(self, action, bucket_name=None):
        """点击生命周期规则页顶部批量操作'更多'下拉选项。

        调用方应先通过 ``select_rows_by_names`` 勾选目标规则。
        若已处于生命周期规则页面（例如刚完成行勾选），可不传 ``bucket_name``，
        避免重复导航导致选择丢失。
        """
        if bucket_name is not None:
            self.oss_bucket_goto_lifecycle_page(bucket_name)
        # 关闭可能遮挡的抽屉
        self._close_task_drawer_if_exists()
        # 点击顶部工具栏"更多"按钮（通常包含 启用/禁用/删除 等批量操作）
        more_btn = self.page.locator(".table-toolbar, .operation-group, .table-main").get_by_text("更多", exact=True).first
        if more_btn.count() == 0:
            more_btn = self.page.get_by_role("button", name="更多").first
        if more_btn.count() == 0:
            raise AssertionError(f"未找到生命周期规则页顶部'更多'批量操作按钮")
        more_btn.click()
        self.page.wait_for_timeout(1000)
        # 在下拉菜单中选择 action
        option = self.page.locator(".el-dropdown-menu__item, .el-dropdown-menu").get_by_text(action, exact=True).first
        if option.count() == 0:
            option = self.page.get_by_text(action, exact=True).first
        if option.count() == 0:
            raise AssertionError(f"未找到批量操作选项: {action}")
        option.click()
        self.page.wait_for_timeout(2000)

    def oss_bucket_goto_policy_page(self, bucket_name):
        """导航到桶策略页面。"""
        self._enter_bucket_detail_via_ui(bucket_name)
        self._click_left_menu("桶策略")

    def oss_bucket_get_policies(self, bucket_name):
        """获取桶策略名称列表（策略列表为 confirm-box 卡片式布局，名称在 .strategy-name-text 中）。"""
        self.oss_bucket_goto_policy_page(bucket_name)
        cards = self.page.locator(".bucket-strategy-list-container .confirm-box").all()
        policies = []
        for card in cards:
            try:
                name_el = card.locator(".strategy-name-text").first
                if name_el.count() > 0:
                    policies.append(name_el.inner_text().strip())
            except Exception:
                pass
        return policies

    def oss_bucket_policy_create(
        self,
        bucket_name,
        name=None,
        policy_name=None,
        template_name=None,
        effect="允许",
        principal="*",
        actions=None,
        resources=None,
    ):
        """创建桶策略（兼容 ``policy_name`` 别名与 ``template_name`` 模板选择）。

        当前 UI 为三步向导页面：选择模板 -> 配置策略 -> 确认策略。
        使用模板时会进入创建页，先选择模板，再填写策略名称，经配置确认后创建。
        """
        name = policy_name or name
        self.oss_bucket_goto_policy_page(bucket_name)
        # 限定在桶策略列表容器内点击“新建”
        create_btn = (
            self.page.locator(".bucket-strategy-list-container")
            .get_by_text("新建", exact=True)
            .first
        )
        create_btn.wait_for(state="visible", timeout=15000)
        create_btn.click()
        self.page.wait_for_url(lambda url: "/permission/policy/create" in url, timeout=15000)

        # 选择模板：在包含模板名称的行内点击“使用模板创建”
        if template_name:
            template_row = self.page.locator(".el-table__row").filter(has_text=template_name).first
            if template_row.count() == 0:
                raise AssertionError(f"未找到策略模板: {template_name}")
            template_row.get_by_text("使用模板创建", exact=True).first.click()
        else:
            # 自定义策略：点击“自定义创建”
            self.page.get_by_text("自定义创建", exact=True).first.click()

        # 等待配置策略页（策略名称输入框出现）
        name_input = self.page.locator(".el-form-item").filter(has_text="策略名称").locator("input").first
        name_input.wait_for(state="visible", timeout=15000)
        if name:
            name_input.fill(name)

        # 配置确认 -> 确认策略 -> 立即创建
        self.page.get_by_text("配置确认", exact=True).first.click()
        create_btn = self.page.get_by_text("立即创建", exact=True).first
        create_btn.wait_for(state="visible", timeout=15000)
        create_btn.click()
        # 等待创建完成后返回策略列表页
        self.page.wait_for_url(lambda url: "/permission/policy/create" not in url, timeout=30000)
        return name

    def _policy_row_operation(self, bucket_name, target_name, op_icon_title):
        """在桶策略列表中定位到指定策略行并点击行内操作图标（编辑/删除）。"""
        self.oss_bucket_goto_policy_page(bucket_name)
        row = self.page.locator(".confirm-box").filter(has_text=target_name).first
        if row.count() == 0:
            raise AssertionError(f"策略列表中未找到: {target_name}")
        op_container = row.locator(".operation-tool-btn").first
        if op_container.count() == 0:
            raise AssertionError(f"策略行 '{target_name}' 未找到操作按钮容器")
        # operation-tool-btn 内包含两个 <span>：第 1 个编辑，第 2 个删除
        idx = 0 if op_icon_title == "编辑" else 1
        op_btn = op_container.locator("span").nth(idx)
        if op_btn.count() == 0:
            raise AssertionError(f"策略行 '{target_name}' 未找到第 {idx + 1} 个操作按钮（{op_icon_title}）")
        op_btn.click()

    def oss_bucket_policy_edit(
        self,
        bucket_name,
        old_name=None,
        policy_name=None,
        new_policy_name=None,
        **kwargs,
    ):
        """编辑桶策略（兼容 ``policy_name`` 作为原名称）。"""
        target = policy_name or old_name
        new_name = new_policy_name or kwargs.get("name")
        if not target:
            raise ValueError("编辑策略时必须提供 policy_name 或 old_name")
        self._policy_row_operation(bucket_name, target, "编辑")
        self.page.wait_for_url(lambda url: "/permission/policy/modify/" in url, timeout=15000)

        name_input = self.page.locator(".el-form-item").filter(has_text="策略名称").locator("input").first
        name_input.wait_for(state="visible", timeout=15000)
        if new_name:
            name_input.fill(new_name)

        # 点击“配置确认”进入确认步骤
        config_confirm_btn = self.page.get_by_text("配置确认", exact=True).first
        config_confirm_btn.click()

        # 等待 Vue 路由/页面状态稳定后再定位确认页容器
        self.wait_for_page_ready()
        self.page.wait_for_timeout(500)

        # 等待 loading 消失、确认策略页渲染（轮询，兼容并发/慢环境）
        loading = self.page.locator(".modify-bucket-strategy-container .el-loading-mask").first
        if loading.count() > 0:
            loading.wait_for(state="hidden", timeout=10000)
        confirm_container = self.page.locator(".strategy-confirm-container").first
        confirm_container.wait_for(state="visible", timeout=30000)

        # 底部确认按钮在页面底栏，可能与其他“确认”文案冲突， scoped 到底栏
        confirm_btn = self.page.locator(".modify-bucket-strategy-container").get_by_text("确认", exact=True).first
        confirm_btn.wait_for(state="visible", timeout=30000)
        confirm_btn.click()
        self.page.wait_for_url(lambda url: "/permission/policy/modify/" not in url, timeout=30000)

    def oss_bucket_policy_delete(self, bucket_name, name=None, policy_name=None):
        """删除桶策略（兼容 ``policy_name`` 参数名）。"""
        name = policy_name or name
        self._policy_row_operation(bucket_name, name, "删除")
        # 等待并确认删除弹窗（兼容 SugonDeleteDialog / el-dialog / message-box）
        if not self._confirm_delete_dialog(timeout=15000):
            raise AssertionError("点击删除后未弹出确认弹窗")
        # 等待弹窗消失、列表刷新
        self.page.locator(".sugon-dialog-box:visible, .cv-dialog:visible, .el-dialog:visible, .el-message-box:visible").first.wait_for(state="hidden", timeout=30000)

    def oss_bucket_goto_safety_chain_page(self, bucket_name):
        """导航到防盗链页面。"""
        self._enter_bucket_detail_via_ui(bucket_name)
        self._click_left_menu("防盗链")

    def oss_bucket_set_referer(self, bucket_name, referer_type, referer_value):
        """设置桶防盗链（黑名单/白名单）。

        ``referer_type`` 支持英文 ``whitelist/blacklist`` 或中文 ``白名单/黑名单``。
        实际页面为两个独立表单项，每项通过编辑图标进入编辑态，填写后点“确认”。
        """
        type_map = {"whitelist": "白名单Referer", "blacklist": "黑名单Referer"}
        label = type_map.get(referer_type, referer_type)
        if not label.endswith("Referer"):
            label = label + "Referer"

        self.oss_bucket_goto_safety_chain_page(bucket_name)
        self.page.wait_for_timeout(1500)

        form_item = self.page.locator(".el-form-item").filter(has_text=label).first
        if form_item.count() == 0:
            raise AssertionError(f"未找到防盗链表单项: {label}")

        textarea = form_item.locator("textarea").first
        # 若 textarea 处于禁用态，先点击编辑图标进入编辑态
        if textarea.count() > 0 and textarea.is_disabled():
            edit_btn = form_item.locator(".el-icon-edit").first
            if edit_btn.count() == 0:
                # fallback：点击该表单项下第一个可见 cloud-button
                edit_btn = form_item.locator(".cloud-button").filter(has_not_text="").first
            if edit_btn.count() > 0:
                edit_btn.click()
                self.page.wait_for_timeout(800)

        textarea = form_item.locator("textarea").first
        if textarea.count() == 0:
            raise AssertionError(f"{label} 下未找到 textarea")
        textarea.fill(referer_value)
        self.page.wait_for_timeout(300)

        confirm = form_item.get_by_text("确认", exact=True).first
        if confirm.count() == 0:
            confirm = form_item.locator("button").filter(has_text="确认").first
        if confirm.count() == 0:
            confirm = form_item.locator(".cloud-button").filter(has_text="确认").first
        if confirm.count() == 0:
            raise AssertionError(f"未找到 {label} 的确认按钮")
        confirm.click()
        self.page.wait_for_timeout(2500)

    def oss_bucket_get_referer(self, bucket_name, referer_type):
        """读取当前设置的防盗链值（按类型切到对应表单项）。"""
        type_map = {"whitelist": "白名单Referer", "blacklist": "黑名单Referer"}
        label = type_map.get(referer_type, referer_type)
        if not label.endswith("Referer"):
            label = label + "Referer"

        self.oss_bucket_goto_safety_chain_page(bucket_name)
        self.page.wait_for_timeout(1500)

        form_item = self.page.locator(".el-form-item").filter(has_text=label).first
        if form_item.count() == 0:
            return ""
        textarea = form_item.locator("textarea").first
        if textarea.count() > 0:
            return textarea.input_value().strip()
        return ""

    def oss_bucket_tag_create(self, bucket_name, key, value, skip_navigation=False):
        """在桶详情标签页创建标签。"""
        if not skip_navigation:
            self._enter_bucket_detail_via_ui(bucket_name)
            self._click_left_menu("标签")
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)
        dialog = self.page.locator(".el-dialog:visible").first
        if dialog.count() == 0:
            btn = self.page.get_by_text("新建", exact=True).first
            cls = btn.get_attribute("class") or ""
            disabled = btn.get_attribute("disabled") or ""
            if (
                disabled == "true"
                or "is-disabled" in cls
                or "cl-btn-primary-disabled" in cls
            ):
                raise AssertionError("标签数量已达上限，'新建'按钮被禁用")
            self.page.wait_for_timeout(2000)
            dialog = self.page.locator(".el-dialog:visible").first
        inputs = dialog.locator("input").all()
        if len(inputs) >= 2:
            inputs[0].fill(key)
            inputs[1].fill(value)
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(2000)

    def oss_bucket_tag_get_count(self, bucket_name):
        """获取桶标签数量。"""
        self._enter_bucket_detail_via_ui(bucket_name)
        self._click_left_menu("标签")
        rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
        return len([r for r in rows if r.locator("td").count() >= 2])

    def oss_bucket_tag_is_create_disabled(self, bucket_name):
        """判断'新建'标签按钮是否被禁用（标签数达到上限 10）。"""
        self._enter_bucket_detail_via_ui(bucket_name)
        self._click_left_menu("标签")
        btn = self.page.get_by_text("新建", exact=True).first
        if btn.count() == 0:
            return False
        disabled = btn.get_attribute("disabled") or ""
        class_attr = btn.get_attribute("class") or ""
        return (
            disabled == "true"
            or "is-disabled" in class_attr
            or "cl-btn-primary-disabled" in class_attr
        )

    def oss_bucket_goto_acl_page(self, bucket_name):
        """导航到桶 ACL 页面。"""
        self._enter_bucket_detail_via_ui(bucket_name)
        self._click_left_menu("桶Acls")

    def oss_bucket_acl_assert_page_loaded(self, bucket_name):
        """断言 ACL 页面已加载。"""
        self.oss_bucket_goto_acl_page(bucket_name)
        assert self.page.get_by_text("桶Acls", exact=True).count() > 0 or self.page.locator(".el-table__header").count() > 0

    def oss_bucket_acl_click_new(self):
        """点击 ACL 页面'新建'按钮。"""
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

    def oss_bucket_acl_dialog_is_visible(self, title):
        """判断 ACL 弹窗是否可见。"""
        dialog = self.page.locator(".el-dialog").filter(has=self.page.get_by_text(title, exact=True)).first
        return dialog.count() > 0 and dialog.is_visible()

    def _acl_dialog_active_form_item(self, dialog, label_text):
        """在 ACL 弹窗中按 label 文本定位 el-form-item。"""
        return dialog.locator(".el-form-item").filter(has_text=label_text).first

    def oss_bucket_acl_dialog_fill_account(self, account_id):
        """在 ACL 弹窗填写账号 ID。"""
        dialog = self.page.locator(".el-dialog:visible").first
        item = self._acl_dialog_active_form_item(dialog, "账号")
        inp = item.locator("input").first
        inp.fill(account_id)
        inp.press("Tab")

    def _acl_permission_checkbox_label(self, dialog, category, permission):
        """按权限分类定位到对应的可见 checkbox label（桶访问权限 / ACL访问权限）。"""
        item = self._acl_dialog_active_form_item(dialog, category)
        return item.locator("label.el-checkbox").filter(has_text=permission).first

    def _acl_checkbox_is_checked(self, label):
        """通过 label 的 class 判断 ElementUI 复选框是否已勾选。"""
        classes = label.get_attribute("class") or ""
        return "is-checked" in classes

    def oss_bucket_acl_dialog_check_permission(self, category, permission):
        """勾选 ACL 权限（点击可见 label，通过 class 校验状态）。"""
        dialog = self.page.locator(".el-dialog:visible").first
        label = self._acl_permission_checkbox_label(dialog, category, permission)
        if label.count() == 0:
            raise AssertionError(f"未找到 [{category}] 下的 '{permission}' 复选框")
        label.wait_for(state="visible", timeout=5000)
        if not self._acl_checkbox_is_checked(label):
            label.click()
        self.page.wait_for_timeout(500)

    def oss_bucket_acl_dialog_uncheck_permission(self, category, permission):
        """取消勾选 ACL 权限（点击可见 label，通过 class 校验状态）。"""
        dialog = self.page.locator(".el-dialog:visible").first
        label = self._acl_permission_checkbox_label(dialog, category, permission)
        if label.count() == 0:
            raise AssertionError(f"未找到 [{category}] 下的 '{permission}' 复选框")
        label.wait_for(state="visible", timeout=5000)
        if self._acl_checkbox_is_checked(label):
            label.click()
        self.page.wait_for_timeout(500)

    def oss_bucket_acl_dialog_click_confirm(self):
        """点击 ACL 弹窗'确定'。"""
        dialog = self.page.locator(".el-dialog:visible").first
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(2000)

    def oss_bucket_acl_get_list(self, bucket_name):
        """获取 ACL 列表（合并"桶访问权限"与"ACL访问权限"两列文本）。"""
        self.oss_bucket_goto_acl_page(bucket_name)
        rows = self.page.locator(".el-table__body-wrapper .el-table__row").all()
        items = []
        for row in rows:
            try:
                cells = row.locator("td").all()
                if len(cells) >= 3:
                    name = cells[0].inner_text().strip()
                    bucket_perm = cells[1].inner_text().strip()
                    acl_perm = cells[2].inner_text().strip()
                    items.append({
                        "name": name,
                        "permissions": f"桶:{bucket_perm} ACL:{acl_perm}",
                        "bucket_permissions": bucket_perm,
                        "acl_permissions": acl_perm,
                    })
            except Exception:
                pass
        return items

    def oss_bucket_acl_assert_account_permissions(
        self, bucket_name, account_id,
        expect_bucket_read=False, expect_bucket_write=False,
        expect_acl_read=False, expect_acl_write=False,
    ):
        """断言账号 ACL 权限与预期一致。

        UI 列表使用“读权限/写权限/完全控制”文案；当后端返回 FULL_CONTROL 时显示“完全控制”，
        其同时满足读取与写入预期。
        """
        items = self.oss_bucket_acl_get_list(bucket_name)
        found = [i for i in items if i["name"] == account_id]
        assert found, f"ACL 列表未找到账号 {account_id}"
        bucket_actual = found[0]["bucket_permissions"]
        acl_actual = found[0]["acl_permissions"]

        def _has_permission(actual_text, expect_read, expect_write):
            has_read = "读权限" in actual_text or "完全控制" in actual_text
            has_write = "写权限" in actual_text or "完全控制" in actual_text
            if expect_read and not has_read:
                return False
            if expect_write and not has_write:
                return False
            return True

        assert _has_permission(bucket_actual, expect_bucket_read, expect_bucket_write), \
            f"桶访问权限不符，期望 读={expect_bucket_read}/写={expect_bucket_write}，实际: {bucket_actual}"
        assert _has_permission(acl_actual, expect_acl_read, expect_acl_write), \
            f"ACL访问权限不符，期望 读={expect_acl_read}/写={expect_acl_write}，实际: {acl_actual}"

    def oss_bucket_acl_create(
        self, bucket_name, account_id,
        bucket_read=False, bucket_write=False,
        acl_read=False, acl_write=False,
    ):
        """创建账号 ACL（支持按权限布尔值调用）。"""
        self.oss_bucket_goto_acl_page(bucket_name)
        self.oss_bucket_acl_click_new()
        self.oss_bucket_acl_dialog_fill_account(account_id)
        if bucket_read:
            self.oss_bucket_acl_dialog_check_permission("桶访问权限", "读取权限")
        if bucket_write:
            self.oss_bucket_acl_dialog_check_permission("桶访问权限", "写入权限")
        if acl_read:
            self.oss_bucket_acl_dialog_check_permission("ACL访问权限", "读取权限")
        if acl_write:
            self.oss_bucket_acl_dialog_check_permission("ACL访问权限", "写入权限")
        self.oss_bucket_acl_dialog_click_confirm()

    def oss_bucket_acl_exists(self, bucket_name, account_id):
        """判断账号 ACL 是否存在。"""
        items = self.oss_bucket_acl_get_list(bucket_name)
        return any(i["name"] == account_id for i in items)

    def oss_bucket_acl_click_row_edit(self, account_id):
        """点击 ACL 列表行内'编辑'。

        桶 ACL 页面操作列为平铺按钮，非"更多"下拉，直接点击行内"编辑"。
        """
        row = self.page.locator(".el-table__row").filter(has_text=account_id).first
        if row.count() == 0:
            raise AssertionError(f"ACL 列表中未找到账号 '{account_id}' 所在行")
        edit_btn = row.get_by_text("编辑", exact=True).first
        if edit_btn.count() == 0:
            raise AssertionError(f"账号 '{account_id}' 行内未找到'编辑'按钮")
        edit_btn.click()
        self.page.wait_for_timeout(1500)

    def oss_bucket_acl_click_row_delete(self, account_id):
        """点击 ACL 列表行内'删除'。

        桶 ACL 页面操作列为平铺按钮，非"更多"下拉，直接点击行内"删除"。
        """
        row = self.page.locator(".el-table__row").filter(has_text=account_id).first
        if row.count() == 0:
            raise AssertionError(f"ACL 列表中未找到账号 '{account_id}' 所在行")
        delete_btn = row.get_by_text("删除", exact=True).first
        if delete_btn.count() == 0:
            raise AssertionError(f"账号 '{account_id}' 行内未找到'删除'按钮")
        delete_btn.click()
        self.page.wait_for_timeout(1500)

    def oss_bucket_acl_click_delete_confirm(self):
        """点击 ACL 删除确认弹窗'确定'。"""
        confirm = self.page.get_by_text("确定", exact=True).first
        if confirm.count() > 0:
            confirm.click()
        self.page.wait_for_timeout(2000)

    def oss_bucket_acl_assert_account_not_exists(self, bucket_name, account_id):
        """断言账号 ACL 不存在。"""
        assert not self.oss_bucket_acl_exists(bucket_name, account_id), f"账号 {account_id} 仍存在"

    def _oss_api_headers(self):
        """从 localStorage 读取当前登录凭证与区域，用于直接调用 OSS 内部 API。

        在整套件并行/页面导航间隙，page 可能短暂处于 about:blank 或非同源 document，
        直接读取 localStorage 会抛 SecurityError。本方法先校验页面是否处于控制台同
        origin，必要时导航回 OSS 桶列表页再读取；读取过程捕获 SecurityError 后同样
        会回退到桶列表页重试一次。
        """
        base_url = Config.get("base_url")
        origin_prefix = base_url.rstrip("/") + "/"

        def _is_valid_origin():
            url = self.page.url
            return bool(url and url.startswith(origin_prefix))

        def _read_storage():
            api_header_json = self.page.evaluate(
                """() => {
                    try { return localStorage.getItem("api_header") || "{}"; }
                    catch(e) { return "{}"; }
                }"""
            ) or "{}"
            try:
                api_header = json.loads(api_header_json)
            except Exception:
                api_header = {}
            token = api_header.get("Authorization") or api_header.get("authorization")
            region_id = self.page.evaluate(
                """() => {
                    try { return localStorage.getItem("regionId") || "RegionOne"; }
                    catch(e) { return "RegionOne"; }
                }"""
            ) or "RegionOne"
            headers = {}
            if token:
                headers["Authorization"] = token
            headers["regionId"] = region_id
            return headers

        # 页面不在控制台 origin 时，先回到有效页面
        if not _is_valid_origin():
            self._goto_bucket_list()

        # 第一次读取；若触发 SecurityError 则导航回桶列表页后重试一次
        try:
            return _read_storage()
        except Exception as exc:
            error_text = str(exc)
            if "SecurityError" in error_text or "localStorage" in error_text:
                self._goto_bucket_list()
                return _read_storage()
            raise

    def oss_bucket_get_tags_via_api(self, bucket_name):
        """通过 OSS 内部 API 查询桶标签列表。

        Returns:
            list[dict]: 标签列表，每项为 {"key": ..., "value": ...} 格式。
        """
        import urllib.parse
        host = Config.get("host")
        headers = self._oss_api_headers()
        url = (
            f"https://{host}:30000/api/sugoncloud-oss-api/api/bucket/tagging"
            f"?bucketName={urllib.parse.quote(bucket_name)}"
        )
        result = self.page.evaluate(
            """async ({url, headers}) => {
                const resp = await fetch(url, { method: 'GET', headers: headers });
                return await resp.json();
            }""",
            {"url": url, "headers": headers},
        )
        if not result or not result.get("success"):
            return []
        content = result.get("content") or {}
        tags = content.get("tags") or []
        return [{"key": t.get("key"), "value": t.get("value")} for t in tags]

    def oss_bucket_create_tags_via_api(self, bucket_name, tags):
        """通过 OSS 内部 API 为桶创建/覆盖标签。

        Args:
            bucket_name: 桶名称。
            tags: 标签列表，每项为 {"key": ..., "value": ...} 格式。

        Returns:
            bool: API 返回成功为 True，否则 False。
        """
        host = Config.get("host")
        headers = self._oss_api_headers()
        url = f"https://{host}:30000/api/sugoncloud-oss-api/api/bucket/tagging"
        tags_obj = {}
        for tag in tags:
            if tag.get("key"):
                tags_obj[tag["key"]] = tag.get("value", "")
        result = self.page.evaluate(
            """async ({url, headers, bucket_name, tags}) => {
                const resp = await fetch(url, {
                    method: 'POST',
                    headers: Object.assign({'Content-Type': 'application/json'}, headers),
                    body: JSON.stringify({ bucketName: bucket_name, tags: tags })
                });
                return await resp.json();
            }""",
            {"url": url, "headers": headers, "bucket_name": bucket_name, "tags": tags_obj},
        )
        return bool(result and result.get("success"))

    def oss_bucket_create_fragments_via_api(self, bucket_name, count=3):
        """通过 OSS 内部 API 初始化多段上传任务，构造碎片记录。

        返回列表元素包含 ``objectKey`` 与 ``uploadId``，与测试断言对齐。
        """
        import urllib.parse
        host = Config.get("host")
        headers = self._oss_api_headers()
        fragments = []
        for i in range(count):
            object_key = f"fragment-{i}-{random_data()}"
            url = f"https://{host}:30000/api/sugoncloud-oss-api/api/ossObject/upload-chunk/inint"
            # 使用 page.evaluate 在浏览器上下文发起同域 fetch
            result = self.page.evaluate(
                """async ({url, headers, bucket_name, object_key}) => {
                    const form = new FormData();
                    form.append('bucket_name', bucket_name);
                    form.append('objectKey', object_key);
                    form.append('metadata', null);
                    form.append('storageClass', 'STANDARD');
                    const resp = await fetch(url, {
                        method: 'POST',
                        headers: headers,
                        body: form
                    });
                    return await resp.json();
                }""",
                {
                    "url": url,
                    "headers": headers,
                    "bucket_name": bucket_name,
                    "object_key": object_key,
                },
            )
            if not result or not result.get("success"):
                raise AssertionError(
                    f"初始化多段上传失败 | objectKey={object_key} | response={result}"
                )
            upload_id = result.get("content", {}).get("uploadId")
            if not upload_id:
                raise AssertionError(
                    f"初始化多段上传未返回 uploadId | objectKey={object_key} | response={result}"
                )
            fragments.append({"objectKey": object_key, "uploadId": upload_id})
        return fragments

    def oss_bucket_list_fragments_via_api(self, bucket_name):
        """通过 OSS 内部 API 查询桶的碎片列表。"""
        import urllib.parse
        host = Config.get("host")
        headers = self._oss_api_headers()
        url = f"https://{host}:30000/api/sugoncloud-oss-api/api/bucket/parts?bucketName={urllib.parse.quote(bucket_name)}"
        result = self.page.evaluate(
            """async ({url, headers}) => {
                const resp = await fetch(url, { method: 'GET', headers: headers });
                return await resp.json();
            }""",
            {"url": url, "headers": headers},
        )
        if not result or not result.get("success"):
            raise AssertionError(f"查询碎片列表失败 | response={result}")
        content = result.get("content") or []
        return [
            {
                "objectKey": item.get("objectKey"),
                "uploadId": item.get("uploadId"),
                "size": item.get("size"),
                "num": item.get("num"),
            }
            for item in content
        ]

    def oss_bucket_delete_fragment_via_api(self, bucket_name, fragment_name, upload_id):
        """通过 OSS 内部 API 删除指定碎片。"""
        import urllib.parse
        host = Config.get("host")
        headers = self._oss_api_headers()
        object_key_enc = urllib.parse.quote(fragment_name, safe="")
        url = (
            f"https://{host}:30000/api/sugoncloud-oss-api/api/bucket/parts"
            f"?bucketName={urllib.parse.quote(bucket_name)}"
            f"&objectKey={object_key_enc}"
            f"&uploadId={urllib.parse.quote(str(upload_id), safe='')}".replace(" ", "")
        )
        result = self.page.evaluate(
            """async ({url, headers}) => {
                const resp = await fetch(url, { method: 'DELETE', headers: headers });
                return await resp.json();
            }""",
            {"url": url, "headers": headers},
        )
        if not result or not result.get("success"):
            raise AssertionError(
                f"通过 API 删除碎片失败 | objectKey={fragment_name} | response={result}"
            )
        return True

    def _confirm_delete_dialog(self, timeout=5000):
        """点击当前可见删除确认弹窗中的"确定"按钮（兼容 SugonDeleteDialog / el-message-box）。"""
        selectors = [
            ".sugon-dialog-box:visible",
            ".cv-dialog:visible",
            ".el-dialog:visible",
            ".el-message-box:visible",
            ".cv-message-box:visible",
            ".cv-message-box__wrapper:visible",
        ]
        dialog = None
        for sel in selectors:
            dialog = self.page.locator(sel).first
            try:
                dialog.wait_for(state="visible", timeout=timeout)
                break
            except Exception:
                dialog = None
        if dialog is None or dialog.count() == 0:
            return False

        confirm = dialog.get_by_text("确定", exact=True).first
        if confirm.count() == 0:
            confirm = dialog.locator("button").filter(has_text="确定").first
        if confirm.count() > 0 and confirm.is_visible():
            confirm.click()
            return True
        return False

    def oss_bucket_delete_attempt(self, bucket_name):
        """尝试删除一个非空桶：点击删除、在确认弹窗中确认，等待后端返回结果。"""
        self._ensure_bucket_list()
        # 桶列表行可能是平铺删除按钮或"更多"下拉，统一使用 click_action
        try:
            self.click_action(bucket_name, "删除")
        except Exception:
            # fallback：直接定位行内删除/更多下拉
            row = self.page.locator(".el-table__row").filter(has_text=bucket_name).first
            self._click_row_dropdown_item(row, "删除")
        # 删除确认弹窗出现后点击"确定"，再由后端决定是删除成功还是返回失败
        self._confirm_delete_dialog()
        self.page.wait_for_timeout(3000)

    def assert_oss_delete_error_dialog(self, message="删除失败"):
        """断言当前存在包含指定文案的错误提示/弹窗（含确认后的错误提示、toast、结果弹窗）。"""
        self.page.wait_for_timeout(1500)
        candidates = [
            ".one-dialog-box:visible",
            ".sugon-dialog-box:visible",
            ".el-message--error",
            ".el-message-box:visible",
            ".cv-message-box:visible",
            ".cv-message-box__wrapper:visible",
            ".el-dialog:visible",
        ]
        for sel in candidates:
            tip = self.page.locator(sel).first
            if tip.count() > 0 and tip.is_visible():
                text = tip.inner_text()
                if message in text:
                    # 结果弹窗可能遮挡后续操作，尝试关闭
                    try:
                        close_btn = tip.get_by_text("关闭", exact=True).first
                        if close_btn.count() > 0 and close_btn.is_visible():
                            close_btn.click()
                            self.page.wait_for_timeout(800)
                    except Exception:
                        pass
                    return
        # 兜底：在常见的消息容器文本中查找
        msg = self.page.locator(".el-message__content, .el-message").first
        if msg.count() > 0 and msg.is_visible() and message in msg.inner_text():
            return
        raise AssertionError(f"未找到包含 {message} 的错误提示或弹窗")

    def oss_bucket_cancel_delete_object(self, bucket_name, object_name):
        """对已删除对象执行取消删除操作。"""
        self.oss_bucket_click_deleted_objects_tab(bucket_name)
        self.page.wait_for_timeout(3000)
        row = self.page.locator(".el-table__row").filter(has_text=object_name).first
        if row.count() == 0:
            raise AssertionError(f"已删除对象列表中未找到 {object_name}")
        self._click_row_action_button(row, "取消删除")
        self.page.wait_for_timeout(2000)
        confirm = self.page.get_by_text("确定", exact=True).first
        if confirm.count() > 0:
            confirm.click()
        self.page.wait_for_timeout(5000)

    def oss_bucket_permanent_delete_object(self, bucket_name, object_name, single=True):
        """对已删除对象执行彻底删除操作。"""
        self.oss_bucket_click_deleted_objects_tab(bucket_name)
        self.page.wait_for_timeout(3000)
        if single:
            row = self.page.locator(".el-table__row").filter(has_text=object_name).first
            if row.count() == 0:
                raise AssertionError(f"已删除对象列表中未找到 {object_name}")
            self._click_row_action_button(row, "彻底删除")
            self.page.wait_for_timeout(2000)
            confirm = self.page.get_by_text("确定", exact=True).first
            if confirm.count() > 0:
                confirm.click()
        else:
            self.oss_bucket_check_deleted_object_row(bucket_name, object_name)
            btn = self.page.get_by_text("彻底删除", exact=True).first
            if btn.count() > 0:
                btn.click()
            self.page.wait_for_timeout(2000)
            confirm = self.page.get_by_text("确定", exact=True).first
            if confirm.count() > 0:
                confirm.click()
        self.page.wait_for_timeout(5000)
