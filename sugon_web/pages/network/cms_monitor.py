import math
import time

from sugon_web.common.base import BasePage
from sugon_web.common.playwright import expect
from sugon_web.config.config import Config
from sugon_web.assertions.network.monitor import MonitorAssertionMixin


class MonitorMixin(MonitorAssertionMixin, BasePage):
    """CMS云监控服务页面对象。

    用于操作监控服务下的负载均衡监控详情页，包括：
    - 导航到SLB监控详情页
    - 切换时间范围（实时/历史）
    - 切换监控对象（实例/监听器）
    - 选择监听器
    - 验证监控图表
    """

    def click_slb_in_list(self, slb_name, slb_uuid=None):
        """在CMS监控服务的SLB列表页中点击指定SLB名称进入详情页。

        Args:
            slb_name: 负载均衡实例名称
            slb_uuid: 负载均衡uuid，可选。若提供则直接使用，否则从
                表格行数据的 row.uuid 获取。
        """
        list_url_path = "/cloud-server-slb"

        # 等待列表加载完成并定位目标行
        row_loc = None
        deadline = time.time() + 10
        while time.time() < deadline:
            row_loc = self.get_by_role("cell", name=slb_name).locator("a")
            if row_loc.count() > 0 and row_loc.is_visible():
                break
            time.sleep(1)
        if row_loc:
            row_loc.click()

        # 获取 uuid：优先使用传入参数，否则从表格行 Vue 数据读取
        uuid = slb_uuid
        if not uuid:
            uuid = self.page.evaluate(
                """
                ([rowSelector, name]) => {
                    const rows = document.querySelectorAll(rowSelector);
                    for (const row of rows) {
                        if (row.textContent.includes(name)) {
                            // 尝试从 Vue 组件实例读取行数据
                            let vue = row.__vue__;
                            while (vue) {
                                const rowData = vue.row || vue.$props?.row;
                                if (rowData && rowData.uuid) {
                                    return rowData.uuid;
                                }
                                vue = vue.$parent;
                            }
                        }
                    }
                    return null;
                }
                """,
                ["tr.el-table__row", slb_name],
            )

        if not uuid:
            raise AssertionError(
                f"无法获取SLB '{slb_name}' 的uuid，无法导航到详情页"
            )

        # 直接通过 Vue Router push 导航（与前端 gotoPage 行为一致）
        detail_path = f"/cloud-server-slb-detail?id={uuid}&type=nfv&name={slb_name}"
        self.page.evaluate(
            """
            (detailPath) => {
                const app = document.querySelector('#app');
                if (app && app.__vue__ && app.__vue__.$router) {
                    app.__vue__.$router.push(detailPath);
                } else {
                    // 兜底：修改 hash 触发路由
                    window.location.hash = '#' + detailPath;
                }
            }
            """,
            detail_path,
        )

        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

        # 验证是否已成功导航到详情页
        if list_url_path in self.page.url and "detail" not in self.page.url:
            raise AssertionError(
                f"导航到SLB详情页失败，当前URL: {self.page.url}"
            )

        self.logger.info(f"在CMS列表页进入SLB详情页: {slb_name}")

    # ------------------------------------------------------------------
    # 导航
    # ------------------------------------------------------------------

    def goto_slb_monitor_detail(self, slb_name, slb_uuid=None, project_id=None, slb_type="nfv"):
        """导航到负载均衡基础版的监控详情页（CMS监控服务）。

        当前环境 /cms/ 入口会由前端重定向到 /prom/，而 /prom/ 下
        SLB 相关页面存在权限限制，因此实际通过 /vpc/ 路径访问
        监控详情页（与步骤3点击"查看监控"后的页面一致）。

        注意：/cloud-server-slb-detail 路由由 globalLink 动态加载，
        直接 URL 访问可能导致 Vue Router 无法匹配而显示空白页。
        方法内会增加页面加载状态检测。

        Args:
            slb_name: 负载均衡名称
            slb_uuid: 负载均衡uuid，可选
            project_id: 项目ID，可选
            slb_type: SLB类型，如"nfv"、"normal"，默认"nfv"

        Returns:
            bool: 页面是否成功加载
        """
        base_url = Config.get("base_url").rstrip("/")
        monitor_url = (
            f"{base_url}/vpc/#/cloud-server-slb-detail"
            f"?id={slb_uuid}&type={slb_type}&name={slb_name}"
        )
        if project_id:
            monitor_url += f"&project_id={project_id}"

        self.page.goto(monitor_url)
        self.page.wait_for_load_state("domcontentloaded", timeout=30000)
        self.wait_for_page_ready()
        # 等待Vue组件异步渲染完成（globalLink动态加载路由需要较长时间）
        self.page.wait_for_timeout(8000)

        # 检测页面是否正确加载（Vue动态路由可能未匹配）
        if self._is_monitor_page_ready():
            self.logger.info(f"进入监控详情页: {slb_name}")
            return True

        self.logger.warning(
            f"直接URL访问监控详情页未正确加载，"
            f"可能需要通过VPC列表页点击'查看监控'进入: {slb_name}"
        )
        return False

    def wait_for_monitor_page_ready(self, timeout=30000):
        """等待监控详情页关键元素出现。

        轮询等待页面上的radio按钮或图表容器可见，
        用于在导航到监控详情页后确认页面已正确加载。

        Args:
            timeout: 最大等待时间（毫秒），默认30000
        """
        deadline = time.time() + timeout / 1000
        while time.time() < deadline:
            try:
                radio = self.locator("label.el-radio-button").first
                if radio.count() > 0 and radio.is_visible():
                    self.logger.info("监控详情页关键元素已可见")
                    return True
            except Exception:
                pass
            time.sleep(1)
        self.logger.warning("等待监控详情页关键元素超时")
        return False

    def _is_monitor_page_ready(self):
        """检测监控详情页是否已正确加载。

        不仅检查元素是否存在，还检查是否可见，避免将隐藏元素或
        其他页面的残留元素误判为页面已加载。
        """
        indicators = [
            ".vpn-detail-box",
            ".render-parent-box",
            "label.el-radio-button",
            ".monitor-date-picker",
        ]
        for selector in indicators:
            try:
                loc = self.locator(selector)
                count = loc.count()
                if count > 0:
                    # 检查至少一个元素可见
                    for i in range(min(count, 3)):
                        try:
                            if loc.nth(i).is_visible():
                                return True
                        except Exception:
                            continue
            except Exception:
                pass
        return False

    # ------------------------------------------------------------------
    # 时间范围选择
    # ------------------------------------------------------------------

    def select_time_range(self, range_name="实时"):
        """选择监控时间范围。

        页面加载时默认即为"实时"模式，通常无需手动选择。
        若需要切换，通过radio点击实现。

        Args:
            range_name: 时间范围名称，如"实时"、"近1小时"、"近3小时"等
        """
        # 页面加载后默认radioType=-1即为实时，先检查当前是否已是目标状态
        # el-radio-button 会渲染 label[role=radio] 和 input[type=radio] 两个元素，
        # 使用 filter 定位到可见的 label 元素避免 strict mode violation
        radio = self.locator("label.el-radio-button").filter(has_text=range_name).first
        if radio.count() > 0 and radio.is_visible():
            is_checked = radio.evaluate(
                "el => el.classList.contains('is-checked') || "
                "el.getAttribute('aria-checked') === 'true'"
            )
            if is_checked:
                self.logger.info(f"当前已是目标时间范围: {range_name}，跳过点击")
                return
            radio.click()
            self.page.wait_for_timeout(1000)
            self.logger.info(f"选择监控时间范围: {range_name}")
        else:
            self.logger.warning(f"未找到时间范围radio: {range_name}")

    # ------------------------------------------------------------------
    # 监控对象切换
    # ------------------------------------------------------------------

    def select_object_tab(self, tab_name):
        """选择监控对象tab（实例/监听器/节点）。

        Args:
            tab_name: tab名称，如"实例"、"监听器"
        """
        # 先等待页面元素出现（Vue组件可能还在异步加载）
        deadline = time.time() + 30
        radio = None
        while time.time() < deadline:
            radio = self.locator("label.el-radio-button").filter(has_text=tab_name).first
            if radio.count() > 0 and radio.is_visible():
                break
            time.sleep(1)

        if not radio or radio.count() == 0:
            raise AssertionError(
                f"未找到监控对象tab '{tab_name}'，页面可能未正确加载。"
                f"当前URL: {self.page.url}"
            )

        # 检查是否已经是选中状态
        is_checked = radio.evaluate(
            "el => el.classList.contains('is-checked') || "
            "el.getAttribute('aria-checked') === 'true'"
        )
        if is_checked:
            self.logger.info(f"当前已是目标监控对象tab: {tab_name}，跳过点击")
            return

        radio.click()
        self.page.wait_for_timeout(3000)
        self.logger.info(f"选择监控对象tab: {tab_name}")

    def select_listener(self, listener_name):
        """在"监听器"tab下选择指定监听器。

        Args:
            listener_name: 监听器名称
        """
        # 监听器选择器是一个el-select下拉框
        # 先检查监听器标签是否可见
        listener_label = self.get_by_text("监听器：", exact=False)
        if listener_label.count() == 0 or not listener_label.is_visible():
            self.logger.warning("未找到监听器选择器标签，可能当前不在监听器tab")
            return
        '''
        page.locator("label").filter(has_text="监听器").click()
        page.locator("#cloud-container-content").get_by_role("textbox", name="请选择", exact=True).click()
        page.get_by_role("listitem").filter(has_text="tcp_8080").click()
        '''
        select_input = self.locator("#cloud-container-content").get_by_role("textbox", name="请选择", exact=True)
        if select_input.count() > 0 and select_input.is_visible():
            select_input.click()
            # 等待下拉框展开并加载选项
            self.page.wait_for_timeout(1000)
            option = self.locator("div.el-select-dropdown:visible li").filter(
                has_text=listener_name
            ).first
            # 轮询等待选项出现（监听器列表可能异步加载）
            deadline = time.time() + 10
            while time.time() < deadline:
                if option.count() > 0 and option.is_visible():
                    break
                time.sleep(0.5)
            if option.count() == 0:
                self.logger.warning(f"未找到监听器选项: {listener_name}，尝试使用当前已选监听器")
                # 关闭下拉框（按Escape）
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
                return
            option.click()
            self.page.wait_for_timeout(2000)
            self.logger.info(f"选择监听器: {listener_name}")
        else:
            self.logger.warning("未找到监听器选择器下拉框")

