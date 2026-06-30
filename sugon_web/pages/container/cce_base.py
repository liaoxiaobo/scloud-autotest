import re

from sugon_web.common.base import BasePage


class CceBaseMixin(BasePage):
    """CCE 通用辅助方法。"""

    def _select_option(self, option_text, exact=True):
        """在已展开的 el-select 下拉菜单中选择指定选项。

        Args:
            option_text: 选项文本
            exact: 是否精确匹配（默认True）。对于label包含前后缀的选项（如云硬盘类型）可设为False使用子串匹配。
        """
        # 等待可见下拉菜单数量稳定为1，避免前一个dropdown关闭动画与新打开的dropdown重叠，导致.last选错
        self.page.wait_for_selector(".el-select-dropdown:visible", state="attached", timeout=10000)
        for _ in range(20):
            if self.page.locator(".el-select-dropdown:visible").count() == 1:
                break
            self.page.wait_for_timeout(100)

        # 在所有可见下拉菜单中查找包含目标选项的项（避免.last选错）
        if exact:
            pattern = re.compile(rf"^{re.escape(option_text)}$")
        else:
            pattern = option_text

        dropdowns = self.page.locator(".el-select-dropdown:visible").all()
        for dropdown in dropdowns:
            item = dropdown.locator(".el-select-dropdown__item").filter(has_text=pattern)
            if item.count() > 0:
                item.first.dispatch_event("click")
                # 等待下拉菜单关闭动画完成，避免遮挡后续操作
                self.page.wait_for_timeout(800)
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(200)
                return

        # 兜底：使用.last（兼容旧行为）
        dropdown = self.page.locator(".el-select-dropdown:visible").last
        dropdown.wait_for(state="visible", timeout=10000)
        item = dropdown.locator(".el-select-dropdown__item").filter(has_text=pattern)
        item.first.dispatch_event("click")
        self.page.wait_for_timeout(800)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(200)

    def _select_cluster_namespace(self, cluster_name, namespace="default"):
        """在 CCE 列表页顶部选择目标集群和命名空间。

        CCE 左侧菜单列表页（存储卷、命名空间、工作负载等）右上角普遍存在
        “集群/命名空间”选择器，其 DOM 结构见前端工程
        `sugoncloud-cce-web/src/page/cce/storage-volume-manage/index.vue` 中
        `rightHandles` 计算属性：
          <span>集群</span>
          <el-select value={cluster_id} onChange={cluster_change}> ... </el-select>
          <span>命名空间</span>
          <el-select class="table-search-select" value={namespace}> ... </el-select>
        若未选中目标集群/命名空间，后续新建弹窗可能因 cluster_id/namespace 错误
        导致下拉框无数据或操作对象错误。

        注意：切集群会触发异步 get_namespace()，期间命名空间可能被自动覆盖。
        本方法在切集群后等待命名空间值稳定，再按需选择目标命名空间，并二次
        校验结果是否收敛到目标值。

        Args:
            cluster_name: 目标集群名称（对应 el-option 的 label）
            namespace: 目标命名空间，默认 "default"
        """
        import time

        def _input_value(select):
            try:
                return select.locator(".el-input__inner").input_value()
            except Exception:
                return ""

        def _wait_value_stable(select, timeout=10):
            """等待下拉框 input_value 连续多次不变，用于等待异步加载完成。"""
            prev_value = None
            stable_count = 0
            deadline = time.time() + timeout
            while time.time() < deadline:
                current_value = _input_value(select)
                if current_value and current_value == prev_value:
                    stable_count += 1
                    if stable_count >= 3:
                        return current_value
                else:
                    stable_count = 0
                prev_value = current_value
                self.page.wait_for_timeout(300)
            raise TimeoutError(f"选择器值未在 {timeout}s 内稳定，最后值: {prev_value}")

        def _wait_value_equal(select, expected, timeout=10):
            """等待下拉框 input_value 等于期望值。"""
            deadline = time.time() + timeout
            while time.time() < deadline:
                if _input_value(select) == expected:
                    return
                self.page.wait_for_timeout(200)
            raise TimeoutError(f"选择器值未收敛到 {expected}")

        # 命名空间选择器有唯一 class，以其为锚点反向定位集群选择器
        namespace_select = self.page.locator(".table-search-select")
        namespace_select.wait_for(state="visible", timeout=10000)
        cluster_select = namespace_select.locator(
            "xpath=preceding-sibling::div[contains(@class,'el-select')][1]"
        )

        # 选择集群（若当前不是目标集群）
        if _input_value(cluster_select) != cluster_name:
            cluster_select.click()
            self._select_option(cluster_name, exact=False)
            # 切集群后会清空 namespace 并异步重新拉取命名空间列表，
            # 必须等待其自动选择并稳定，否则后续手动选 namespace 可能被异步回调覆盖
            namespace_select = self.page.locator(".table-search-select")
            namespace_select.wait_for(state="visible", timeout=10000)
            _wait_value_stable(namespace_select, timeout=10)
            self.wait_for_page_ready()

        # 选择命名空间（若当前不是目标命名空间）
        # 再次重新定位，防止 DOM 在切集群后已重建
        namespace_select = self.page.locator(".table-search-select")
        namespace_select.wait_for(state="visible", timeout=10000)
        if _input_value(namespace_select) != namespace:
            namespace_select.click()
            self._select_option(namespace, exact=False)
            _wait_value_equal(namespace_select, namespace, timeout=10)
            self.wait_for_page_ready()

    def _fill_cidr(self, label, cidr):
        """填写CIDR网段（分段输入框）。

        Args:
            label: 表单标签名称
            cidr: CIDR字符串，如"10.0.0.0/16"
        """
        # 解析CIDR
        parts = cidr.replace("/", ".").split(".")
        # 定位到该表单项下的可编辑输入框（排除 el-select 的 readonly 显示框）
        form_item = self.page.locator(".el-form-item").filter(has_text=label)
        inputs = form_item.locator("input:not([readonly])")
        for i, part in enumerate(parts):
            if i < inputs.count():
                inputs.nth(i).fill(part)

    def _select_flavor(self, flavor):
        """在规格表格中选择指定规格。

        Args:
            flavor: 规格名称，如"cce.d6.xlarge"
        """
        self.page.locator(".el-table__row").first.wait_for(state="visible", timeout=30000)
        row = self.page.locator(".el-table__row").filter(has_text=flavor)
        if row.count() == 0:
            row = self.page.locator(".el-table__row").first
        row.first.locator(".el-radio").dispatch_event("click")

    def _select_flavor_in_dialog(self, container, flavor):
        """在指定容器（如对话框）内的规格表格中选择指定规格。

        Args:
            container: 对话框容器 Locator
            flavor: 规格名称，如"cce.d6.xlarge"
        """
        container.locator(".el-table__row").first.wait_for(state="visible", timeout=30000)
        row = container.locator(".el-table__row").filter(has_text=flavor)
        if row.count() == 0:
            row = container.locator(".el-table__row").first
        row.first.locator(".el-radio").dispatch_event("click")
