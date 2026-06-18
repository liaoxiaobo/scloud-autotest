import re
import time

from sugon_web.common.base import BasePage, submenu
from sugon_web.pages.container.cce_base import CceBaseMixin
from sugon_web.utils.logger import logger


class SsmPage(CceBaseMixin, BasePage):
    """服务治理 SSM 网格实例页面操作封装。"""

    service_name = "服务治理"

    # 网格实例状态相关
    _MESH_STATUS_COMPLETE = "安装完成"
    _MESH_STATUS_INSTALL_ERROR = "安装失败"

    @submenu("网格实例")
    def mesh_create(self, name, cluster, istio_version="1.16.2", flavor="32x",
                    plugins=None):
        """创建网格实例。

        Args:
            name: 网格实例名称。
            cluster: CCE 集群名称。
            istio_version: Istio 版本，默认 "1.16.2"。
            flavor: 规格，默认 "32x"，可选 32x/64x/128x/256x/512x/1024x。
            plugins: 可观测性插件列表，默认 None 表示不勾选任何插件。
        """
        # cl-button 自定义组件无原生 role=button，用 page-level get_by_text 定位
        # 按钮文案为 "+ 新建"，用非 exact 匹配
        self.page.get_by_text("新建").first.click()

        dialog = self.page.locator(".el-dialog").filter(has_text="新建")
        dialog.wait_for(state="visible", timeout=30000)

        # 网格名称
        name_item = dialog.locator(".el-form-item").filter(has_text="网格名称")
        name_item.locator("input").first.fill(name)

        # istio 版本
        version_item = dialog.locator(".el-form-item").filter(has_text="istio版本")
        version_item.locator(".el-select").first.click()
        self._select_option(istio_version)

        # kubernetes 集群
        cluster_item = dialog.locator(".el-form-item").filter(has_text="kubernetes集群")
        cluster_item.locator(".el-select").first.click()
        self._select_option(cluster)

        # 可观测性插件（暂不开启监控，默认不勾选）
        if plugins:
            self._select_plugins(dialog, plugins)

        # 规格选择
        self._select_flavor_card(dialog, flavor)

        # 提交
        submit_btn = dialog.get_by_text("立即创建", exact=True)
        submit_btn.click()
        self.wait_for_page_ready()

    @submenu("网格实例")
    def mesh_delete(self, name):
        """删除指定名称的网格实例。

        Args:
            name: 网格实例名称。
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("网格实例")
    def mesh_batch_delete(self, names):
        """批量删除网格实例。

        Args:
            names: 网格实例名称列表。
        """
        self.select_rows_by_names(names)
        self.btn_batch_delete.click()
        self.dialog_confirm.click()
        self.wait_for_page_ready()

    @submenu("网格实例")
    def mesh_edit(self, name, new_name=None, flavor=None):
        """修改网格实例。

        Args:
            name: 当前网格实例名称。
            new_name: 新的网格实例名称，不传则不修改。
            flavor: 新的规格，不传则不修改。
        """
        self.click_action(name, "修改")

        dialog = self.page.locator(".el-dialog").filter(has_text="修改")
        dialog.wait_for(state="visible", timeout=30000)

        if new_name:
            name_item = dialog.locator(".el-form-item").filter(has_text="网格名称")
            name_input = name_item.locator("input").first
            name_input.fill("")
            name_input.fill(new_name)

        if flavor:
            self._select_flavor_card(dialog, flavor)

        dialog.get_by_text("确定", exact=True).click()
        self.wait_for_page_ready()

    @submenu("网格实例")
    def mesh_check(self, name):
        """点击检测并返回弹窗内检测项文本。

        Args:
            name: 网格实例名称。

        Returns:
            str: 检测弹窗内的文本内容。
        """
        self.click_action(name, "检测")

        dialog = self.page.locator(".el-dialog").filter(has_text="检测")
        dialog.wait_for(state="visible", timeout=30000)

        # 等待检测接口返回（加载状态消失）
        loading_mask = dialog.locator(".el-loading-mask")
        if loading_mask.count() > 0 and loading_mask.is_visible():
            loading_mask.wait_for(state="hidden", timeout=60000)

        text = dialog.inner_text()
        self.dialog_close.click()
        self.wait_for_page_ready()
        return text

    def _refresh_mesh_list(self):
        """刷新网格实例列表。

        优先点击页面刷新按钮，未找到则尝试点击任意可见刷新图标，
        仍失败则重新导航到网格实例页面以刷新数据。
        """
        try:
            self.btn_refresh.click()
            self.wait_for_page_ready()
            logger.debug("页面刷新成功")
            return
        except Exception:
            pass

        try:
            refresh_icons = self.page.locator(".el-icon-refresh:visible")
            if refresh_icons.count() > 0:
                refresh_icons.first.click()
                self.wait_for_page_ready()
                logger.debug("通过刷新图标刷新页面成功")
                return
        except Exception:
            pass

        try:
            self.goto_service(self.service_name)
            self.goto_submenu("网格实例")
            logger.debug("通过重新导航刷新页面成功")
        except Exception as e:
            logger.warning(f"刷新网格实例列表失败: {e}")

    def mesh_assert_status(self, name, status="安装完成", timeout=1800,
                           refresh=True, refresh_interval=5):
        """断言网格实例状态达到预期，遇到安装失败立即退出。

        Args:
            name: 网格实例名称。
            status: 期望状态，默认 "安装完成"。
            timeout: 最长等待秒数，默认 1800。
            refresh: 是否自动刷新列表，默认 True。
            refresh_interval: 刷新间隔秒数，默认 5。
        """
        start_time = time.time()
        first_check = True
        matched = False
        last_status = "未知"

        while time.time() - start_time < timeout:
            try:
                if not first_check and refresh:
                    self._refresh_mesh_list()

                first_check = False
                target_row = self.get_row_by_name(name)
                current_text = target_row.inner_text()
                last_status = current_text

                if self._MESH_STATUS_INSTALL_ERROR in current_text:
                    raise AssertionError(
                        f"网格实例状态验证失败: {name} -> 检测到失败终态 '安装失败'"
                    )

                if status in current_text:
                    logger.info(f"网格实例状态验证成功: {name} -> {status}")
                    matched = True
                    break

            except AssertionError:
                raise
            except Exception as e:
                logger.debug(f"检查网格实例状态时出错: {e}")

            time.sleep(refresh_interval)

        if not matched:
            raise AssertionError(
                f"[StatusAssertion] 网格实例状态 | 状态收敛失败 | "
                f"{name} | 期望: '{status}' | 实际: '{last_status}' | 超时未收敛"
            )

    def get_mesh_row_data(self, name):
        """获取指定网格实例的列表行数据。

        Args:
            name: 网格实例名称。

        Returns:
            dict: 行数据字典，键为列名（名称/项目名称/创建时间/集群/版本/状态/错误信息）。
        """
        row = self.get_row_by_name(name)
        return self.get_row_data_by_locator(row)

    def _select_flavor_card(self, dialog, flavor):
        """在创建/修改弹窗中选择规格卡片。

        Args:
            dialog: 弹窗 Locator。
            flavor: 规格名称，如 "32x"。
        """
        valid_flavors = ["32x", "64x", "128x", "256x", "512x", "1024x"]
        if flavor not in valid_flavors:
            raise ValueError(f"不支持的规格: {flavor}，可选: {valid_flavors}")

        # 规格卡片是 div 容器，包含标题和CPU/内存信息
        # 先找包含规格标题的卡片，点击整个卡片
        card = dialog.locator(".flavor-card, [class*='flavor'], [class*='spec']").filter(
            has_text=re.compile(rf"^{flavor}$")
        )
        if card.count() > 0:
            card.first.click()
        else:
            # 兜底：直接找包含规格文本的元素点击
            card_title = dialog.get_by_text(flavor, exact=True).first
            card_title.click()
        self.page.wait_for_timeout(300)

    def _select_plugins(self, dialog, plugins):
        """在创建/修改弹窗中勾选可观测性插件。

        Args:
            dialog: 弹窗 Locator。
            plugins: 插件描述文本列表，如 ["Kiali", "Jaeger"]。
        """
        for plugin_desc in plugins:
            checkbox_label = dialog.locator(".el-checkbox").filter(
                has_text=re.compile(plugin_desc, re.IGNORECASE)
            )
            checkbox_input = checkbox_label.locator("input[type='checkbox']").first
            if not checkbox_input.is_checked():
                checkbox_label.click()
                self.page.wait_for_timeout(300)
