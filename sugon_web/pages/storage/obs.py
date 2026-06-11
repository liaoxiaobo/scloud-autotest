import re
from playwright.sync_api import expect
from sugon_web.assertions.storage import ObsAssertionMixin
from sugon_web.common.base import BasePage, submenu
from sugon_web.config.config import Config


class ObsPage(ObsAssertionMixin, BasePage):
    """对象存储专业版页面对象。"""
    service_name = "对象存储专业版"

    @property
    def _input_bucket_name(self):
        """桶名称输入框"""
        return self.get_by_placeholder("请输入桶名称")

    @property
    def _input_bucket_capacity(self):
        """桶容量输入框"""
        return self.get_by_placeholder("请输入桶容量")

    @property
    def _btn_cancel_page(self):
        """创建页取消按钮，限定在底部按钮栏内。"""
        return self.page.locator(".btn-box").get_by_text("取消", exact=True)

    def select_top_nav_project(self, org_name="默认组织", project_name="默认项目"):
        """通过顶部导航栏选择项目。

        Args:
            org_name: 组织名称，支持字符串或列表（多级组织路径）。默认"默认组织"。
            project_name: 项目名称，默认"默认项目"
        """
        # 等待页面完全加载，避免按钮在 DOM 重建时被 detached
        self.page.wait_for_timeout(2000)
        # 重试：等待项目按钮出现、匹配、并点击（兼容页面过渡期间的 DOM 重建）
        for attempt in range(3):
            try:
                top_project_btn = self.page.locator(".project_btn").filter(
                    has_text=re.compile(r"请选择项目|" + re.escape(project_name))
                )
                if top_project_btn.count() == 0:
                    top_project_btn = self.page.locator(".project_btn")
                expect(top_project_btn.first).to_be_visible(timeout=5000)
                top_project_btn.first.click()
                break
            except Exception:
                if attempt == 2:
                    raise
                self.page.wait_for_timeout(2000)
        self.page.wait_for_timeout(1000)

        panel = self.page.locator(".project_dialog").first
        expect(panel).to_be_visible(timeout=10000)
        # 等待组织树异步加载完成
        self.page.wait_for_timeout(2000)

        # 在左侧组织树中选择组织（支持多级路径）
        org_names = [org_name] if isinstance(org_name, str) else org_name

        # 使用 JS 直接操作 DOM，避免 Playwright locator 对隐藏元素的限制
        for i, target in enumerate(org_names):
            is_leaf = (i == len(org_names) - 1)
            self.page.evaluate("""
                (args) => {
                    const [target, isLeaf] = args;
                    const tree = document.querySelector('.department_tree');
                    if (!tree) return;
                    const items = tree.querySelectorAll('.one-tree-msg-text-content');
                    for (let item of items) {
                        if (item.innerText.trim() === target) {
                            const parent = item.closest('.one-tree-msg');
                            if (!parent) return;
                            const icon = parent.querySelector('.one-tree-jiantou');
                            if (!isLeaf && icon) icon.click();
                            else parent.click();
                            break;
                        }
                    }
                }
            """, [target, is_leaf])
            self.page.wait_for_timeout(3000)

        # 等待项目列表异步加载
        self.page.wait_for_timeout(3000)
        project_items = self.page.locator(".project_item")
        if project_items.count() > 0:
            selected = False
            for i in range(project_items.count()):
                item = project_items.nth(i)
                item_text = item.inner_text()
                if project_name in item_text:
                    item.locator(".el-radio").click()
                    selected = True
                    break
            if not selected:
                project_items.first.locator(".el-radio").click()
        else:
            no_project = panel.locator("text=此部门下没有项目")
            if no_project.count() > 0:
                panel.locator(".dialog_footer").get_by_text("取消", exact=True).click()
                self.page.wait_for_timeout(300)
            raise AssertionError(
                f"环境缺少可用项目：组织路径'{org_names}'下没有项目'{project_name}'")

        # 点击确定
        panel.locator(".dialog_footer").get_by_text("确定", exact=True).click()
        self.page.wait_for_timeout(800)
        self.wait_for_page_ready()

    def _get_selected_region_name(self):
        """获取创建页面上已选中的区域名称。"""
        radio_group = self.locator(".radio-group")
        buttons = radio_group.locator(".el-radio-button")
        try:
            expect(buttons.first).to_be_visible(timeout=10000)
        except Exception:
            return None
        active_btn = radio_group.locator(".el-radio-button.is-active")
        if active_btn.count() > 0:
            return active_btn.first.inner_text().strip()
        for i in range(buttons.count()):
            btn = buttons.nth(i)
            cls = btn.get_attribute("class") or ""
            if "is-active" in cls:
                return btn.inner_text().strip()
        return None

    def _get_storage_class_state(self, label):
        """获取指定存储类别选项的可用状态。"""
        radio_label = self.get_by_text(label, exact=True)
        try:
            parent = radio_label.locator("xpath=..")
            class_attr = parent.get_attribute("class") or ""
            return "is-disabled" not in class_attr
        except Exception:
            return False

    def obs_bucket_create(self, name, capacity=None, object_limit=None):
        """创建桶。

        Args:
            name: 桶名称
            capacity: 桶容量，None 表示使用页面默认值（推荐，避免不同环境配额差异）
            object_limit: 对象数量限制，None 表示不限制（默认）
        """
        self.logger.info(f"[DEBUG] obs_bucket_create called for {name} (capacity={capacity})")
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        self.goto_submenu("桶列表")
        self.page.wait_for_timeout(2000)

        # 先检查桶是否已存在，避免"重复创建桶名称"错误
        # 使用搜索框进行可靠查找（支持分页场景）
        try:
            search_input = self.page.locator(
                'input[type="text"]'
            ).filter(
                has=self.page.get_by_placeholder(
                    re.compile(r"搜索|请输入")
                )
            )
            if search_input.count() > 0:
                search_input.first.fill(name)
                self.page.wait_for_timeout(1500)
                search_input.first.press("Enter")
                self.page.wait_for_timeout(2000)
                # 搜索后检查是否有结果
                found_after_search = self.page.evaluate(
                    """
                    (name) => {
                        const rows = document.querySelectorAll('.el-table__row');
                        for (const row of rows) {
                            if (row.innerText.includes(name)) return true;
                        }
                        return false;
                    }
                    """,
                    name,
                )
                if found_after_search:
                    self.logger.warning(f"桶 {name} 已存在，跳过创建")
                    # 清空搜索框，避免影响后续操作
                    search_input.first.clear()
                    self.page.wait_for_timeout(500)
                    return
                # 清空搜索框
                search_input.first.clear()
                self.page.wait_for_timeout(500)
        except Exception as e:
            self.logger.debug(f"搜索桶名前置检查异常: {e}")

        self.btn_create.click()
        self.wait_for_page_ready()
        self._input_bucket_name.fill(name)

        # 仅在显式传入 capacity 时覆盖页面默认值
        # 不同环境配额规则可能不同，使用页面默认值可避免"超出取值范围"错误
        if capacity is not None:
            self._input_bucket_capacity.fill(capacity)
            self.page.wait_for_timeout(300)

        # 设置对象数量限制
        if object_limit is not None:
            # 选择"限制"单选按钮
            limit_radio = self.page.get_by_text("限制", exact=True).first
            limit_radio.click()
            self.page.wait_for_timeout(500)
            # 填写对象数量
            object_input = self.page.get_by_placeholder("请输入对象数量").first
            object_input.fill(str(object_limit))
            self.page.wait_for_timeout(300)

        self.btn_submit.click()
        # 等待创建处理完成：最长30秒，轮询检测是否离开创建页
        for _ in range(30):
            self.page.wait_for_timeout(1000)
            current_url = self.page.url
            if "create" not in current_url and "edit" not in current_url:
                break
        else:
            # 仍停留在创建页，检查是否有错误提示
            error_msg = self.page.evaluate(
                """
                () => {
                    const selectors = '.el-message--error, .cv-message-error, .error-tip, .el-form-item__error, .el-notification__content, .tips, .hint';
                    const els = document.querySelectorAll(selectors);
                    const msgs = [];
                    for (const el of els) {
                        const text = el.innerText.trim();
                        if (text) msgs.push(text);
                    }
                    return msgs.join(' | ');
                }
                """
            )
            # 若创建失败，尝试直接访问桶详情页确认是否已存在
            # 某些环境下中文字符匹配不可靠，改用URL存在性验证
            if error_msg:
                self.logger.warning(f"桶 {name} 创建页提示: {error_msg}")
                try:
                    from sugon_web.config.config import Config
                    base_url = Config.get("base_url").rstrip("/")
                    self.page.goto(f"{base_url}/obs/#/store/list")
                    self.wait_for_page_ready()
                    self.page.wait_for_timeout(5000)
                    # 使用搜索框精确查找
                    search_input = self.page.locator(
                        'input[type="text"]'
                    ).filter(
                        has=self.page.get_by_placeholder(
                            re.compile(r"搜索|请输入")
                        )
                    )
                    if search_input.count() > 0:
                        self.logger.info(f"找到搜索框，尝试搜索桶 {name}")
                        search_input.first.fill(name)
                        self.page.wait_for_timeout(2000)
                        search_input.first.press("Enter")
                        self.page.wait_for_timeout(3000)
                        found = self.page.evaluate(
                            """(name) => {
                                const rows = document.querySelectorAll('.el-table__row');
                                for (const row of rows) {
                                    if (row.innerText.includes(name)) return true;
                                }
                                return false;
                            }""",
                            name,
                        )
                        self.logger.info(f"搜索结果: found={found}")
                        if found:
                            self.logger.warning(f"桶 {name} 搜索确认已存在，视为创建成功")
                            return
                    else:
                        self.logger.warning("未找到搜索框，尝试JS直接查找")
                        # 无搜索框时直接遍历DOM
                        found = self.page.evaluate(
                            """(name) => {
                                const rows = document.querySelectorAll('.el-table__row');
                                for (const row of rows) {
                                    if (row.innerText.includes(name)) return true;
                                }
                                const links = document.querySelectorAll('a, .cell a, .blue-link');
                                for (const el of links) {
                                    if (el.textContent.trim() === name) return true;
                                }
                                return false;
                            }""",
                            name,
                        )
                        self.logger.info(f"JS查找结果: found={found}")
                        if found:
                            self.logger.warning(f"桶 {name} JS查找确认已存在，视为创建成功")
                            return
                except Exception as e:
                    self.logger.warning(f"二次确认桶存在性异常: {e}")
            raise AssertionError(
                f"桶 {name} 创建后仍停留在创建页"
                + (f"，错误信息: {error_msg}" if error_msg else "")
            )
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)
        # 返回桶列表页（SPA导航，避免page.goto导致状态丢失）
        self.goto_submenu("桶列表")
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()
        # 轮询等待新桶出现在列表中（最多20秒）
        for attempt in range(20):
            found = self.page.evaluate(
                """
                (name) => {
                    const rows = document.querySelectorAll('.el-table__row');
                    for (const row of rows) {
                        if (row.innerText.trim() === name || row.innerText.includes(name)) return true;
                    }
                    const links = document.querySelectorAll('a, .blue-link, .cell a');
                    for (const el of links) {
                        if (el.textContent.trim() === name) return true;
                    }
                    return false;
                }
                """,
                name,
            )
            if found:
                self.logger.info(f"桶 {name} 已出现在列表中")
                break
            self.logger.info(f"桶 {name} 未在列表中，等待...({attempt + 1}/20)")
            self.page.wait_for_timeout(1000)
        else:
            self.logger.warning(f"桶 {name} 创建后未在列表中找到，可能创建失败或延迟较大")

    def obs_bucket_create_cancel(self, name, capacity="10"):
        """进入创建桶页面、填写信息后点击取消。

        Args:
            name: 桶名称
            capacity: 桶容量，默认 10GB
        """
        self.btn_create.click()
        self.wait_for_page_ready()
        self._input_bucket_name.fill(name)
        self._input_bucket_capacity.fill(capacity)
        self._btn_cancel_page.click()
        self.wait_for_page_ready()

    def obs_bucket_enter_detail(self, name):
        """点击桶名称进入桶详情页。

        Args:
            name: 桶名称
        Raises:
            Exception: 无法找到或点击桶名称时抛出
        """
        self.page.wait_for_timeout(500)
        current_url = self.page.url

        # 若已在目标桶的详情页，直接返回
        # 桶详情页URL: .../store/list/detail/.../name/...
        # 注意：对象详情页URL(.../store/list/objectdetail/...)包含/detail/子串，
        # 必须用 /store/list/detail/ 精确匹配，避免误判
        if name in current_url and "/store/list/detail/" in current_url:
            self.logger.info(f"已在桶 {name} 的详情页，跳过重复进入")
            return

        # 防护：若当前页面不在对象存储服务下，先导航回桶列表
        if "/obs" not in current_url:
            self.logger.warning(
                f"当前页面不在对象存储服务({current_url})，尝试导航回桶列表"
            )
            from sugon_web.config.config import Config
            base_url = Config.get("base_url").rstrip("/")
            self.page.goto(f"{base_url}/obs/#/store/list")
            self.wait_for_page_ready()
            self.page.wait_for_timeout(2000)
        # 若在 OBS 服务下但不在桶列表页（且不是详情页），先切到桶列表
        # 注意：对象详情页URL也包含 /store/list，需要额外排除
        elif "/store/list" not in current_url or "/objectdetail/" in current_url:
            self.logger.info(
                f"当前不在桶列表页({current_url})，切换至桶列表"
            )
            self.goto_submenu("桶列表")
            self.page.wait_for_timeout(3000)

        # 等待表格加载完成（至少有一行数据或出现"暂无数据"）
        for _ in range(30):
            try:
                rows = self.page.locator(".el-table__body-wrapper tr").count()
                if rows > 0:
                    break
                empty = self.page.locator(".el-table__empty-text").count()
                if empty > 0:
                    break
            except Exception:
                pass
            self.page.wait_for_timeout(100)

        # 使用表格行定位点击桶名称，比全局 text 匹配更可靠
        for attempt in range(3):
            try:
                # 策略1：通过 get_row_by_name + _get_interactive_row 点击链接
                row = self.get_row_by_name(name)
                interactive_row = self._get_interactive_row(row)
                name_link = interactive_row.locator("a").filter(
                    has_text=re.compile(rf"^{re.escape(name)}$")
                ).first
                if name_link.count() > 0:
                    name_link.click(timeout=10000)
                else:
                    name_cell = interactive_row.locator("td").filter(
                        has_text=re.compile(rf"^{re.escape(name)}$")
                    ).first
                    if name_cell.count() > 0:
                        name_cell.click(timeout=10000)
                    else:
                        interactive_row.locator("td").nth(1).click(timeout=10000)
                self.page.wait_for_timeout(2500)
                current = self.page.url
                if "/store/list/detail/" in current or name in current:
                    return
                self.logger.warning(
                    f"点击桶 {name} 后 URL 未变化({current})，重试"
                )
            except Exception as e:
                self.logger.info(f"策略1失败: {e}")
                # 策略2：直接使用 Playwright role 定位链接
                try:
                    link = self.page.get_by_role("link", name=name).first
                    if link.count() > 0:
                        link.click(timeout=10000)
                        self.page.wait_for_timeout(2500)
                        current = self.page.url
                        if "/store/list/detail/" in current or name in current:
                            return
                        self.logger.warning(
                            f"策略2点击桶 {name} 后 URL 未变化({current})"
                        )
                except Exception as e2:
                    self.logger.info(f"策略2失败: {e2}")
                if attempt < 2:
                    self.logger.info(
                        f"桶 {name} 定位失败，重新导航到桶列表重试({attempt + 1}/2)"
                    )
                    # 使用 goto_submenu 而非 page.reload()，避免丢失项目选择状态
                    self.goto_submenu("桶列表")
                    self.page.wait_for_timeout(3000)
                    self.wait_for_page_ready()
                    # 等待表格加载
                    for _ in range(50):
                        try:
                            if self.page.locator(".el-table__body-wrapper tr").count() > 0:
                                break
                            if self.page.locator(".el-table__empty-text").count() > 0:
                                break
                        except Exception:
                            pass
                        self.page.wait_for_timeout(100)
                else:
                    self.logger.warning(f"桶 {name} 表格行定位最终失败")

        # 最终兜底：直接 URL 导航到桶详情页
        self.logger.warning(f"表格行定位桶 {name} 均失败，尝试直接 URL 导航")
        from sugon_web.config.config import Config
        base_url = Config.get("base_url").rstrip("/")
        # 使用正确的桶详情页 URL 格式（含 /list/ 路径）
        self.page.goto(f"{base_url}/obs/#/store/list/detail/{name}")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(5000)
        # 验证是否到达详情页（兼容可能的 hash 路由延迟）
        current_url = self.page.url
        if f"/detail/{name}" in current_url or name in current_url:
            self.logger.info(f"URL 导航进入桶 {name} 详情页成功: {current_url}")
            return
        raise RuntimeError(
            f"无法进入桶 {name} 详情页（表格行定位和 URL 导航均失败，"
            f"当前URL: {self.page.url}）"
        )

    def obs_bucket_modify_quota(self, name, capacity=None, object_limit=None):
        """修改桶配额（桶容量和/或对象数量限制）。

        在桶列表中找到指定桶，点击"更多"->"桶配额"，
        在弹窗中修改容量和/或对象数量限制。

        Args:
            name: 桶名称
            capacity: 桶容量值（如 "1"、"10"），None 表示不修改
            object_limit: 对象数量限制，None 表示不修改；
                         传入字符串 "unlimited" 表示设为无限制
        """
        self.goto_submenu("桶列表")
        self.page.wait_for_timeout(1000)

        # 点击"桶配额"操作（使用 click_action 处理下拉菜单）
        self.click_action(name, "桶配额")
        self.page.wait_for_timeout(2000)

        # 获取弹窗
        dialog = self._find_visible_dialog("桶配额")
        assert dialog is not None, "未找到可见的'桶配额'弹窗"
        expect(dialog).to_be_visible(timeout=10000)

        # 修改桶容量
        if capacity is not None:
            capacity_input = dialog.get_by_placeholder("请输入桶容量").first
            expect(capacity_input).to_be_visible(timeout=10000)
            capacity_input.fill("")
            capacity_input.fill(str(capacity))
            self.page.wait_for_timeout(500)

        # 修改对象数量限制
        if object_limit is not None:
            if object_limit == "unlimited":
                # 选择"不限制"
                no_limit_radio = dialog.get_by_text("不限制", exact=True).first
                expect(no_limit_radio).to_be_visible(timeout=10000)
                no_limit_radio.click()
            else:
                # 选择"限制"并填写数量
                limit_radio = dialog.get_by_text("限制", exact=True).first
                expect(limit_radio).to_be_visible(timeout=10000)
                limit_radio.click()
                self.page.wait_for_timeout(500)
                object_input = dialog.get_by_placeholder("请输入对象数量").first
                expect(object_input).to_be_visible(timeout=10000)
                object_input.fill("")
                object_input.fill(str(object_limit))
            self.page.wait_for_timeout(500)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def _obs_bucket_quota_dialog_read(self, name):
        """打开桶配额弹窗读取当前值，然后关闭弹窗。

        Args:
            name: 桶名称

        Returns:
            tuple: (capacity_value, object_limit_value) 或 (None, None)
        """
        self.goto_submenu("桶列表")
        self.page.wait_for_timeout(1000)
        self.click_action(name, "桶配额")
        self.page.wait_for_timeout(2000)

        dialog = self._find_visible_dialog("桶配额")
        if dialog is None:
            return None, None

        capacity_value = None
        object_limit_value = None

        try:
            capacity_input = dialog.get_by_placeholder("请输入桶容量").first
            if capacity_input.count() > 0:
                capacity_value = capacity_input.input_value()
        except Exception:
            pass

        try:
            object_input = dialog.get_by_placeholder("请输入对象数量").first
            if object_input.count() > 0 and object_input.is_visible():
                object_limit_value = object_input.input_value()
            else:
                # 输入框不可见，说明选中了"不限制"
                # 通过检查"限制"单选按钮是否未选中来确认
                limit_radio = dialog.get_by_text("限制", exact=True).first
                if limit_radio.count() > 0:
                    is_limit_checked = limit_radio.evaluate(
                        "el => el.parentElement.classList.contains('is-checked') || el.parentElement.parentElement.classList.contains('is-checked')"
                    )
                    if not is_limit_checked:
                        object_limit_value = "不限制"
                else:
                    # 找不到"限制"按钮，也视为不限制
                    object_limit_value = "不限制"
        except Exception:
            pass

        # 关闭弹窗
        try:
            dialog.get_by_text("取消", exact=True).first.click()
            self.page.wait_for_timeout(3000)
            self.wait_for_page_ready()
        except Exception:
            pass

        return capacity_value, object_limit_value

    def obs_bucket_capacity_get(self, name):
        """获取桶的容量配额值。

        通过打开"桶配额"弹窗读取容量输入框的当前值，
        读取完成后若之前在桶详情页则自动返回详情页。

        Args:
            name: 桶名称

        Returns:
            str: 容量值，如 "1"、"10" 或 None
        """
        # 通过检测桶详情页URL特征判断是否在详情页
        # 注意区分 /store/list/detail/ (桶详情) 和 /store/list/objectdetail/ (对象详情)
        was_in_detail = "/store/list/detail/" in self.page.url
        self.logger.info(f"obs_bucket_capacity_get: was_in_detail={was_in_detail}, url={self.page.url}")
        capacity_value, _ = self._obs_bucket_quota_dialog_read(name)
        if was_in_detail:
            self.logger.info(f"obs_bucket_capacity_get: 尝试返回桶详情页")
            self.obs_bucket_enter_detail(name)
            self.page.wait_for_timeout(1500)
            self.logger.info(f"obs_bucket_capacity_get: 返回后 url={self.page.url}")
        return capacity_value

    def obs_bucket_object_limit_get(self, name):
        """获取桶的对象数量限制值。

        通过打开"桶配额"弹窗读取对象数量限制的当前设置，
        读取完成后若之前在桶详情页则自动返回详情页。

        Args:
            name: 桶名称

        Returns:
            str: 限制值，如 "10" 或 "不限制"，未找到返回 None
        """
        # 通过检测桶详情页URL特征判断是否在详情页
        # 注意区分 /store/list/detail/ (桶详情) 和 /store/list/objectdetail/ (对象详情)
        was_in_detail = "/store/list/detail/" in self.page.url
        self.logger.info(f"obs_bucket_object_limit_get: was_in_detail={was_in_detail}, url={self.page.url}")
        _, object_limit_value = self._obs_bucket_quota_dialog_read(name)
        if was_in_detail:
            self.logger.info(f"obs_bucket_object_limit_get: 尝试返回桶详情页")
            self.obs_bucket_enter_detail(name)
            self.page.wait_for_timeout(1500)
            self.logger.info(f"obs_bucket_object_limit_get: 返回后 url={self.page.url}")
        return object_limit_value

    def obs_object_tab_click(self):
        """在桶详情页点击"对象"菜单项进入对象列表。"""
        # 桶详情页使用左侧菜单导航，先等待菜单渲染
        self.page.wait_for_timeout(2000)
        # 优先匹配 .el-menu-item 中的 "对象"
        object_menu = self.page.locator(".el-menu-item").get_by_text("对象", exact=True)
        if object_menu.count() == 0:
            # 兜底：不限定菜单范围直接查找
            object_menu = self.page.get_by_text("对象", exact=True).first
        object_menu.click()
        self.page.wait_for_timeout(1500)

    def obs_object_upload(self, file_path):
        """在对象列表页上传对象。

        Args:
            file_path: 本地文件路径
        """
        # 点击上传对象按钮
        self.page.get_by_text("上传对象", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 在弹窗中设置文件
        file_input = self.page.locator("#obsUploadInput")
        if file_input.count() == 0:
            file_input = self.page.locator('input[type="file"]')
        file_input.set_input_files(file_path)
        self.page.wait_for_timeout(1500)

        # 点击立即上传
        self.page.get_by_text("立即上传", exact=True).first.click()
        self.page.wait_for_timeout(3000)

        # 关闭可能弹出的任务列表面板（避免遮挡对象列表操作列）
        self._close_task_list_panel_if_exists()

    def obs_object_upload_check_capacity_blocked(self, file_path):
        """检查上传对象是否因桶容量不足被阻止。

        打开上传弹窗、选择文件后，检查"立即上传"按钮是否被禁用
        或是否显示容量不足警告。

        Args:
            file_path: 本地文件路径

        Returns:
            bool: True 表示上传被阻止，False 表示可以上传
        """
        # 点击上传对象按钮
        self.page.get_by_text("上传对象", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 在弹窗中设置文件
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="上传对象"
        ).first
        file_input = self.page.locator("#obsUploadInput")
        if file_input.count() == 0:
            file_input = self.page.locator('input[type="file"]')
        file_input.set_input_files(file_path)
        self.page.wait_for_timeout(2000)

        # 检查"立即上传"按钮是否被禁用
        upload_btn = dialog.get_by_text("立即上传", exact=True).first
        is_disabled = False
        try:
            is_disabled = upload_btn.is_disabled()
        except Exception:
            pass

        # 检查是否显示容量不足警告
        warning_visible = False
        warning_locator = dialog.locator("div").filter(
            has_text="文件超出桶可用容量大小"
        )
        if warning_locator.count() > 0:
            try:
                warning_visible = warning_locator.first.is_visible()
            except Exception:
                pass

        # 关闭上传弹窗
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        return is_disabled or warning_visible

    def _close_task_list_panel_if_exists(self):
        """关闭右侧任务列表面板（如果存在）。"""
        # 策略1：通过标题定位面板并点击关闭按钮
        task_panel = self.page.locator(".el-drawer, .cv-drawer, [role='dialog']").filter(
            has=self.page.get_by_text("任务列表", exact=True)
        )
        if task_panel.count() > 0:
            try:
                # 尝试点击面板右上角的关闭按钮
                close_btn = task_panel.first.locator(".el-drawer__headerbtn, .el-dialog__headerbtn, .drawer-close, .close-btn").first
                if close_btn.count() > 0:
                    close_btn.click()
                    self.page.wait_for_timeout(500)
                    return
            except Exception:
                pass
        # 策略2：按 Escape 键关闭
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

    @submenu("桶列表")
    def obs_bucket_delete(self, name):
        """删除桶。

        兼容空桶删除确认框与非空桶错误提示框，找不到"确定"时静默通过，
        由调用方负责后续状态验证。

        Args:
            name: 桶名称
        """
        self.click_action(name, "删除")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 尝试处理弹出的对话框（确认框或错误提示框）
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

    def obs_bucket_batch_delete(self, names):
        """批量删除桶。

        在桶列表页勾选多个桶，点击更多操作-批量删除，确认删除。

        Args:
            names: 桶名称列表
        """
        self.select_rows_by_names(names)
        self.page.wait_for_timeout(1000)

        # 点击更多操作下拉
        more_btn = self.page.get_by_text("更多操作", exact=True)
        expect(more_btn.first).to_be_visible(timeout=10000)
        more_btn.first.click()
        self.page.wait_for_timeout(1000)

        # 点击批量删除
        batch_delete = self.page.locator(".el-dropdown-menu").get_by_text("批量删除", exact=True)
        expect(batch_delete.first).to_be_visible(timeout=10000)
        batch_delete.first.click()
        self.page.wait_for_timeout(2000)

        # 等待删除桶弹窗出现
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="删除桶"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(5000)
        self.wait_for_page_ready()

    def _obs_bucket_empty(self, name):
        """清空桶内所有对象（用于测试清理）。

        与测试用例 body 中清理逻辑保持完全一致：
        先 goto_service + select_top_nav_project 重建页面上下文，
        再进入桶详情对象列表执行删除，确保操作按钮可渲染。

        Args:
            name: 桶名称
        """
        self.goto_service("对象存储专业版")
        self.select_top_nav_project(
            org_name=["sugoncloud", "智能云事业部"],
            project_name="公共测试",
        )
        self.goto_submenu("桶列表")
        self.obs_bucket_enter_detail(name)
        self.obs_object_tab_click()
        self.page.wait_for_timeout(3000)

        deleted_count = 0
        for attempt in range(50):
            try:
                object_names = self.get_column_data("名称")
                if not object_names:
                    break

                # 过滤掉表头残留和大小信息列
                targets = [
                    n for n in object_names
                    if n not in ["", "暂无数据", "名称"]
                    and not re.match(r'^[\d.]+\s*(GB|MB|KB|B)$', n)
                ]
                if not targets:
                    break

                # 删除第一个目标对象（普通对象或文件夹）
                target = targets[0]
                removed = False

                # 策略1：尝试普通对象删除
                try:
                    self.obs_object_delete(target)
                    removed = True
                    deleted_count += 1
                except Exception as e:
                    self.logger.warning(f"对象删除 '{target}' 失败: {e}")
                    self.page.keyboard.press("Escape")
                    self.page.wait_for_timeout(1000)

                # 策略2：若对象删除未成功，尝试文件夹删除
                if not removed:
                    try:
                        self.obs_folder_delete(target)
                        removed = True
                        deleted_count += 1
                    except Exception as e2:
                        self.logger.warning(f"文件夹删除 '{target}' 失败: {e2}")
                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(1000)

                # 若两种策略均未删除成功，跳出循环避免无限重试
                if not removed:
                    self.logger.warning(
                        f"无法删除 '{target}'，停止清空桶 {name}"
                    )
                    break

                # 等待列表自动刷新
                self.page.wait_for_timeout(2500)

            except Exception as e:
                self.logger.warning(f"清空桶操作异常: {e}")
                break

        self.logger.info(f"桶 {name} 清空完成，共删除 {deleted_count} 个对象")

        # 验证桶是否为空
        self.page.wait_for_timeout(2000)
        remaining = [
            n for n in self.get_column_data("名称")
            if n and n not in ["", "暂无数据", "名称"]
            and not re.match(r'^[\d.]+\s*(GB|MB|KB|B)$', n)
        ]

        if remaining:
            raise RuntimeError(
                f"桶 {name} 清空后仍包含 {len(remaining)} 个对象: {remaining}"
            )

        # 清空后回到桶列表，避免后续操作在详情页失败
        self.goto_submenu("桶列表")
        self.page.wait_for_timeout(1000)

    def _obs_bucket_cleanup_old(self, max_delete=8):
        """清理历史测试残留桶（先清空对象再删除）。

        逐个进入桶、删除对象、删除桶，避免批量删除时因桶非空失败。

        Args:
            max_delete: 最多删除数量，默认 8
        """
        self.goto_submenu("桶列表")
        self.page.wait_for_timeout(2000)
        try:
            column_data = self.get_column_data("名称")
            targets = [
                n for n in column_data
                if n.startswith("autotest-") or n.startswith("bucket-mirror-")
            ][:max_delete]
            for name in targets:
                try:
                    self._obs_bucket_empty(name)
                    self.obs_bucket_delete(name)
                    self.page.wait_for_timeout(2000)
                except Exception:
                    pass
        except Exception:
            pass
        # 关闭可能残留的任何弹窗
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(1000)

    def _click_object_action(self, name, action_text):
        """在对象列表中点击指定对象的操作按钮（处理 drawer 内定位）。

        优先使用 Playwright 标准点击，失败时回退到 JS 直接触发。

        Args:
            name: 对象名称
            action_text: 操作按钮文本（如"下载"、"分享"）
        """
        # 策略1：Playwright locator + force=True（先 hover 行以渲染操作按钮）
        row = self.page.locator(".el-table__body-wrapper tr, .table-main tr, .el-table tr").filter(
            has_text=re.compile(re.escape(name))
        )
        if row.count() > 0:
            # 先 hover 行，触发 Vue 条件渲染操作按钮
            row.first.hover()
            self.page.wait_for_timeout(800)
            # 在行内查找操作按钮
            btn = row.first.locator("button, a, div.cloud-table-dropdown-item-btn, span").filter(
                has_text=action_text
            ).first
            if btn.count() > 0:
                try:
                    btn.click(force=True)
                    self.page.wait_for_timeout(3000)
                    return
                except Exception:
                    pass

        # 策略2：JS dispatchEvent（触发 MouseEvent，更贴近真实用户点击）
        result = self.page.evaluate("""
            (args) => {
                const [name, actionText] = args;
                const rows = document.querySelectorAll('.el-table__body-wrapper tr, .table-main tr, .el-table tr');
                for (let row of rows) {
                    if (row.innerText.includes(name)) {
                        // 模拟 hover 以渲染操作按钮
                        row.dispatchEvent(new MouseEvent('mouseenter', { bubbles: true }));
                        // 优先查找 .cloud-table-dropdown-item-btn（cl-table-dropdown-item 的根 DOM）
                        const items = row.querySelectorAll('.cloud-table-dropdown-item-btn, .cloud-table-dropdown-item');
                        for (let item of items) {
                            if (item.innerText.trim() === actionText) {
                                item.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                                return 'dispatched-item';
                            }
                        }
                        // 查找 cl-button 的 DOM
                        const btns = row.querySelectorAll('.cloud-button-btn, button, a');
                        for (let btn of btns) {
                            if (btn.innerText.trim() === actionText) {
                                btn.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                                return 'dispatched-btn';
                            }
                        }
                        // 兜底：查找任何包含操作文本的元素
                        const allEls = row.querySelectorAll('div, span, button, a');
                        for (let el of allEls) {
                            if (el.innerText.trim() === actionText) {
                                el.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                                return 'dispatched-el';
                            }
                        }
                    }
                }
                return 'not-found';
            }
        """, [name, action_text])
        self.page.wait_for_timeout(3000)
        if result != 'not-found':
            return result

        # 策略3：直接通过 Vue 实例调用 handle 方法（绕过 DOM 事件绑定）
        result = self.page.evaluate("""
            (args) => {
                const [name, actionText] = args;

                function findVueInstance(root, predicate) {
                    if (!root) return null;
                    if (predicate(root)) return root;
                    for (let child of root.$children || []) {
                        const found = findVueInstance(child, predicate);
                        if (found) return found;
                    }
                    return null;
                }

                // 从页面根元素查找 Vue app 实例
                const appEl = document.querySelector('#app') || document.querySelector('[id^="app"]');
                const app = appEl && appEl.__vue__;
                if (!app) return 'no-app';

                // 查找包含 tableOptions（含 handle 列）的 Vue 组件
                const vm = findVueInstance(app, (vm) => {
                    const opts = vm.tableOptions || vm.options;
                    if (opts && Array.isArray(opts)) {
                        const handleCol = opts.find(c => c.key === 'handle');
                        return handleCol && handleCol.buttons &&
                               handleCol.buttons.some(b => b.text === actionText && typeof b.handle === 'function');
                    }
                    return false;
                });

                if (!vm) return 'no-vm';

                // 在组件的 tableData 中找到目标行（支持多种匹配方式）
                const tableData = vm.tableData || [];
                const row = tableData.find(r => {
                    const key = r.key || '';
                    const formatKey = r.obs_format_key || '';
                    return key === name || formatKey === name ||
                           key.includes(name) || formatKey.includes(name);
                });
                if (!row) return 'no-row';

                // 获取 handle 列按钮配置并直接调用 handle
                const opts = vm.tableOptions || vm.options;
                const handleCol = opts.find(c => c.key === 'handle');
                const btn = handleCol.buttons.find(b => b.text === actionText);

                if (btn && typeof btn.handle === 'function') {
                    btn.handle(row);
                    return 'handle-called';
                }
                return 'no-handle';
            }
        """, [name, action_text])
        self.page.wait_for_timeout(3000)
        return result

    def obs_object_download(self, name):
        """点击对象列表中的下载按钮。

        使用 click_action 以兼容下拉菜单模式。

        Args:
            name: 对象名称
        """
        self.click_action(name, "下载")
        self.page.wait_for_timeout(3000)

    def obs_object_share_open(self, name):
        """点击对象列表中的分享按钮，打开分享弹窗。

        Args:
            name: 对象名称
        """
        self._click_object_action(name, "分享")
        self.page.wait_for_timeout(1500)

    def _get_share_dialog(self, is_folder=False):
        """获取分享弹窗的 locator（使用精确条件避免匹配到隐藏弹窗）。

        Args:
            is_folder: 是否为文件夹分享弹窗，默认False（文件分享）
        """
        title = "分享文件夹" if is_folder else "分享文件"
        return self.page.locator(".cv-dialog, .el-dialog").filter(
            has=self.page.get_by_text(title, exact=True)
        ).filter(
            has=self.page.get_by_placeholder("请输入URL有效期")
        ).first

    def obs_object_share_set_expiration(self, minutes):
        """在分享弹窗中设置 URL 有效期。

        Args:
            minutes: 有效期分钟数
        """
        dialog = self._get_share_dialog(is_folder=False)
        expect(dialog.first).to_be_visible(timeout=10000)
        expire_input = dialog.first.get_by_placeholder("请输入URL有效期")
        expire_input.fill(str(minutes))
        self.page.wait_for_timeout(500)

    def obs_object_share_create_link(self):
        """在分享弹窗中点击创建分享链接，返回分享链接文本。"""
        dialog = self._get_share_dialog(is_folder=False)
        expect(dialog.first).to_be_visible(timeout=10000)
        create_btn = dialog.first.get_by_text("创建分享链接", exact=True)
        create_btn.click()
        self.page.wait_for_timeout(3000)
        link_textarea = dialog.first.locator('textarea[readonly]')
        expect(link_textarea.first).to_be_visible(timeout=10000)
        link_text = link_textarea.first.input_value()
        return link_text

    def obs_object_share_copy_link(self):
        """在分享弹窗中点击复制链接。"""
        dialog = self._get_share_dialog(is_folder=False)
        dialog.first.get_by_text("复制链接", exact=True).click()
        self.page.wait_for_timeout(500)

    def obs_object_share_open_url(self):
        """在分享弹窗中点击打开URL，返回新页面。"""
        dialog = self._get_share_dialog(is_folder=False)
        link_textarea = dialog.first.locator('textarea[readonly]')
        link_text = link_textarea.first.input_value()
        dialog.first.get_by_text("打开URL", exact=True).click()
        self.page.wait_for_timeout(2000)
        return link_text

    def obs_object_share_close(self):
        """关闭分享弹窗。"""
        dialog = self._get_share_dialog(is_folder=False)
        close_btn = dialog.first.locator(".el-dialog__headerbtn, .dialog-footer").get_by_text("关闭", exact=True)
        if close_btn.count() == 0:
            close_btn = dialog.first.get_by_text("取消", exact=True)
        if close_btn.count() > 0:
            close_btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(800)

    # ---- 文件夹分享方法 ----

    def obs_folder_share_open(self, folder_name):
        """点击文件夹列表中的分享按钮，打开分享弹窗。

        使用 BasePage.click_action 处理平铺按钮或下拉菜单模式，
        点击后验证弹窗是否出现。

        Args:
            folder_name: 文件夹名称
        """
        self.click_action(folder_name, "分享")
        self.page.wait_for_timeout(2000)

        # 验证分享弹窗是否出现
        dialog = self._get_share_dialog(is_folder=True)
        expect(dialog.first).to_be_visible(timeout=10000)

    def obs_folder_share_set_expiration(self, minutes):
        """在文件夹分享弹窗中设置 URL 有效期（分钟）。

        Args:
            minutes: 有效期分钟数
        """
        dialog = self._get_share_dialog(is_folder=True)
        expect(dialog.first).to_be_visible(timeout=10000)
        expire_input = dialog.first.get_by_placeholder("请输入URL有效期")
        expire_input.fill(str(minutes))
        self.page.wait_for_timeout(500)

    def obs_folder_share_set_code(self, code):
        """在文件夹分享弹窗中设置提取码。

        Args:
            code: 6位数字提取码
        """
        dialog = self._get_share_dialog(is_folder=True)
        expect(dialog.first).to_be_visible(timeout=10000)
        code_input = dialog.first.get_by_placeholder("请输入6位数字提取码")
        code_input.fill(str(code))
        self.page.wait_for_timeout(500)

    def obs_folder_share_create_link(self):
        """在文件夹分享弹窗中点击创建分享链接，返回分享链接和提取码。

        Returns:
            (share_link, extracted_code) 元组
        """
        dialog = self._get_share_dialog(is_folder=True)
        expect(dialog.first).to_be_visible(timeout=10000)
        create_btn = dialog.first.get_by_text(re.compile(r"(创建|更新)分享链接"))
        create_btn.click()
        self.page.wait_for_timeout(3000)
        textarea = dialog.first.locator('textarea[readonly]')
        expect(textarea.first).to_be_visible(timeout=10000)
        content = textarea.first.input_value()
        url_match = re.search(r'URL:\s*(.+)', content)
        code_match = re.search(r'提取码:\s*(.+)', content)
        share_link = url_match.group(1).strip() if url_match else None
        extracted_code = code_match.group(1).strip() if code_match else None
        return share_link, extracted_code

    def obs_folder_share_copy_link(self):
        """在文件夹分享弹窗中点击复制链接。"""
        dialog = self._get_share_dialog(is_folder=True)
        dialog.first.get_by_text("复制链接", exact=True).click()
        self.page.wait_for_timeout(500)

    def obs_folder_share_open_url(self):
        """在文件夹分享弹窗中点击打开URL。"""
        dialog = self._get_share_dialog(is_folder=True)
        dialog.first.get_by_text("打开URL", exact=True).click()
        self.page.wait_for_timeout(2000)

    def obs_folder_share_close(self):
        """关闭文件夹分享弹窗。"""
        dialog = self._get_share_dialog(is_folder=True)
        close_btn = dialog.first.get_by_text("关闭", exact=True)
        if close_btn.count() == 0:
            close_btn = dialog.first.locator(".el-dialog__headerbtn").get_by_text("关闭", exact=True)
        if close_btn.count() > 0:
            close_btn.first.click()
        else:
            self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(800)

    def obs_object_delete(self, name):
        """删除对象。

        Args:
            name: 对象名称
        """
        # 先关闭可能存在的弹窗（避免干扰 dialog_confirm 定位）
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        # 使用 _click_object_action（先 hover 行触发操作按钮渲染）
        self._click_object_action(name, "删除")
        self.wait_for_page_ready()
        # 等待删除对话框渲染
        self.page.wait_for_timeout(3000)

        # 对象删除确认弹窗：只定位当前可见对话框，避免匹配到残留旧弹窗
        try:
            dialog = self.page.locator(
                ".cv-dialog:visible, .el-dialog:visible, .el-message-box:visible"
            ).first
            dialog.wait_for(state="visible", timeout=10000)
            confirm_btn = dialog.get_by_text("确定", exact=True).first
            if confirm_btn.count() > 0:
                try:
                    confirm_btn.click(force=True)
                except Exception:
                    confirm_btn.evaluate("el => el.click()")
            else:
                dialog.evaluate("""
                    (dialog) => {
                        const btn = dialog.querySelector('.cl-dialog-footer, .el-dialog__footer, .dialog-footer, .el-message-box__btns');
                        if (btn) {
                            const confirm = btn.querySelector('button, .cloud-button-btn');
                            if (confirm && confirm.innerText.includes('确定')) {
                                confirm.click();
                                return 'clicked';
                            }
                        }
                        return 'not-found';
                    }
                """)
        except Exception:
            try:
                self.dialog_confirm.click(force=True)
            except Exception:
                self.dialog_confirm.evaluate("el => el.click()")
        self.wait_for_page_ready()

    def obs_object_enter_detail(self, name):
        """点击对象名称进入对象详情页。

        Args:
            name: 对象名称
        """
        self.page.get_by_text(name, exact=True).first.click()
        self.wait_for_page_ready()

    def obs_object_upload_with_metadata(self, file_path, metadata_list):
        """上传对象并设置元数据。

        包含完整的分步向导交互：添加文件 -> 设置元数据 -> 立即上传。

        Args:
            file_path: 本地文件绝对路径
            metadata_list: 元数据列表，每项为 {"key": ..., "value": ...} 格式
        """
        # 点击上传对象按钮
        self.page.get_by_text("上传对象", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 在弹窗中设置文件
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="上传对象"
        ).first
        file_input = self.page.locator("#obsUploadInput")
        if file_input.count() == 0:
            file_input = self.page.locator('input[type="file"]')
        file_input.set_input_files(file_path)
        self.page.wait_for_timeout(1500)

        # 点击下一步：配置元数据（可选）
        next_btn = dialog.get_by_text(re.compile(r"下一步")).first
        next_btn.click()
        self.page.wait_for_timeout(1500)

        # 添加元数据
        for metadata in metadata_list:
            add_btn = dialog.locator(".upload-step-add").first
            add_btn.click()
            self.page.wait_for_timeout(500)

            key_inputs = dialog.locator(
                'input[placeholder="请填写元数据名称"]'
            )
            key_inputs.last.fill(metadata["key"])

            value_inputs = dialog.locator(
                'input[placeholder="请填写元数据的值"]'
            )
            value_inputs.last.fill(metadata["value"])
            self.page.wait_for_timeout(300)

        # 点击立即上传
        dialog.get_by_text("立即上传", exact=True).first.click()
        self.page.wait_for_timeout(5000)

        # 关闭任务列表面板
        self._close_task_list_panel_if_exists()

    def obs_object_detail_click_metadata_tab(self):
        """在对象详情页点击"元数据"tab。"""
        metadata_tab = self.page.locator(".el-tabs__item").filter(
            has_text=re.compile(r"元数据")
        ).first
        metadata_tab.click()
        self.page.wait_for_timeout(1500)

    def obs_object_metadata_get_value(self, key):
        """获取对象详情页元数据列表中指定名称对应的值。

        Args:
            key: 元数据名称
        Returns:
            元数据值字符串，若不存在则返回 None
        """
        rows = self.page.locator(".cv-default-table .el-table__row").filter(
            has_text=key
        )
        if rows.count() == 0:
            return None
        value_cell = rows.first.locator("td").nth(1)
        return value_cell.inner_text().strip()

    def obs_object_metadata_edit(self, key, new_value):
        """编辑对象元数据的值。

        在对象详情页-元数据tab中，找到指定名称的元数据行，
        点击编辑按钮，在弹窗中修改值并确认。

        Args:
            key: 要编辑的元数据名称
            new_value: 新的元数据值
        """
        # 定位包含指定key的元数据行
        rows = self.page.locator(".cv-default-table .el-table__row").filter(
            has_text=key
        )
        assert rows.count() > 0, f"未找到元数据 '{key}'"
        target_row = rows.first

        # 点击该行操作列的"编辑"按钮
        edit_btn = target_row.locator("button, .el-link, a").filter(
            has_text=re.compile(r"编辑")
        ).first
        expect(edit_btn).to_be_visible(timeout=10000)
        edit_btn.click()
        self.page.wait_for_timeout(1500)

        # 在编辑弹窗中修改值
        dialog = self._find_visible_dialog("编辑元数据")
        assert dialog is not None, "未找到'编辑元数据'弹窗"

        value_input = dialog.get_by_placeholder("请输入值").first
        expect(value_input).to_be_visible(timeout=10000)
        value_input.fill(new_value)
        self.page.wait_for_timeout(500)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_object_metadata_add(self, key, value):
        """为存量对象添加元数据。

        在对象详情页-元数据tab中，点击添加按钮，
        在弹窗中填写元数据名称和值并确认。

        Args:
            key: 元数据名称
            value: 元数据值
        """
        # 点击"增加"按钮
        add_btn = self.page.get_by_text("增加", exact=True).first
        expect(add_btn).to_be_visible(timeout=10000)
        add_btn.click()
        self.page.wait_for_timeout(1500)

        # 获取弹窗
        dialog = self._find_visible_dialog("新建元数据")
        assert dialog is not None, "未找到'新建元数据'弹窗"

        # 填写元数据名称
        name_input = dialog.get_by_placeholder("请输入名称").first
        expect(name_input).to_be_visible(timeout=10000)
        name_input.fill(key)
        self.page.wait_for_timeout(500)

        # 填写元数据值
        value_input = dialog.get_by_placeholder("请输入值").first
        expect(value_input).to_be_visible(timeout=10000)
        value_input.fill(value)
        self.page.wait_for_timeout(500)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_object_metadata_delete(self, key):
        """删除对象元数据。

        在对象详情页-元数据tab中，找到指定名称的元数据行，
        点击删除按钮，在确认弹窗中点击确定。

        Args:
            key: 要删除的元数据名称
        """
        # 定位包含指定key的元数据行
        rows = self.page.locator(".cv-default-table .el-table__row").filter(
            has_text=key
        )
        assert rows.count() > 0, f"未找到元数据 '{key}'"
        target_row = rows.first

        # 点击该行操作列的"删除"链接
        delete_link = target_row.locator(".el-link").filter(
            has_text=re.compile(r"删除")
        ).first
        expect(delete_link).to_be_visible(timeout=10000)
        delete_link.click()
        self.page.wait_for_timeout(1500)

        # 确认删除弹窗
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="删除元数据"
        ).first
        if dialog.count() > 0:
            dialog.get_by_text("确定", exact=True).first.click()
            self.page.wait_for_timeout(2000)
        else:
            try:
                self.dialog_confirm.click()
                self.page.wait_for_timeout(2000)
            except Exception:
                self.logger.warning("删除元数据后未检测到确认弹窗，视为已删除")
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
        self.wait_for_page_ready()

    def obs_bucket_lifecycle_config_click(self):
        """在桶详情页点击生命周期管理的'点击配置'按钮，进入生命周期管理页面。"""
        lifecycle_card = self.page.locator(".safe-config-container").filter(
            has_text="生命周期管理"
        ).first
        expect(lifecycle_card).to_be_visible(timeout=10000)
        config_btn = lifecycle_card.get_by_text("点击配置", exact=True)
        config_btn.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_lifecycle_create_rule_all_objects(self, rule_name, expiration_days=1,
                                               fragment_days=1, start_time="17:00",
                                               end_time="18:00"):
        """创建'桶内所有对象'类型的生命周期规则并提交。

        完整交互流程：打开新建弹窗 -> 填写规则名称 -> 选择对象属性
        -> 设置过期删除天数 -> 开启并设置碎片过期删除天数
        -> 设置每日执行时间 -> 点击确定。

        Args:
            rule_name: 规则名称
            expiration_days: 对象过期删除天数，默认1
            fragment_days: 碎片过期删除天数，默认1
            start_time: 每日执行开始时间，默认"17:00"
            end_time: 每日执行结束时间，默认"18:00"
        """
        # 点击新建
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取弹窗
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建生命周期规则"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        # 填写规则名称
        dialog.get_by_placeholder("请输入规则名称").fill(rule_name)
        self.page.wait_for_timeout(300)

        # 选择对象属性：桶内所有对象
        all_objects_radio = dialog.get_by_text("桶内所有对象", exact=True)
        if all_objects_radio.count() > 0:
            all_objects_radio.click()
            # 等待 Vue 重新渲染表单（switch/input 会重建）
            self.page.wait_for_timeout(1500)

        # 设置对象过期删除天数
        expiration_item = dialog.locator(".el-form-item").filter(
            has_text="对象过期删除天数"
        ).first
        expiration_input = expiration_item.locator(".el-input__inner").first
        expiration_input.fill(str(expiration_days))
        self.page.wait_for_timeout(300)

        # 碎片过期删除天数：开启开关并设置值
        # 重新定位 form-item 和 switch（Vue 渲染后 DOM 可能已重建）
        fragment_item = dialog.locator(".el-form-item").filter(
            has_text="碎片过期删除天数"
        ).first
        switch = fragment_item.locator(".el-switch").first
        switch_class = switch.get_attribute("class") or ""
        if "is-checked" not in switch_class:
            # 点击 switch 的 core 区域（Element UI switch 的事件绑定区域）
            switch_core = switch.locator(".el-switch__core").first
            switch_core.click()
            # 等待 Vue 状态更新 + DOM 重建
            self.page.wait_for_timeout(1000)
            # 验证 switch 是否成功开启，若未成功则通过 JS 强制触发
            switch_class = switch.get_attribute("class") or ""
            if "is-checked" not in switch_class:
                switch.evaluate("el => el.click()")
                self.page.wait_for_timeout(500)
        # 重新定位 input（开关开启后 input 会重建为 enabled）
        fragment_input = fragment_item.locator(".el-input__inner").first
        # 若 input 仍为 disabled，通过 JS 强制启用
        aria_disabled = fragment_input.get_attribute("aria-disabled") or ""
        if aria_disabled == "true":
            fragment_input.evaluate(
                "el => { el.disabled = false; el.setAttribute('aria-disabled', 'false'); }"
            )
            self.page.wait_for_timeout(200)
        fragment_input.fill(str(fragment_days))
        self.page.wait_for_timeout(300)

        # 设置每日执行时间
        start_input = dialog.locator('input[placeholder="开始时间"]').first
        start_input.fill(start_time)
        self.page.wait_for_timeout(300)
        end_input = dialog.locator('input[placeholder="结束时间"]').first
        end_input.fill(end_time)
        self.page.wait_for_timeout(300)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)

        # 点击确定
        self.page.wait_for_timeout(500)
        confirm_btn = dialog.get_by_text("确定", exact=True).first
        expect(confirm_btn).to_be_visible(timeout=10000)
        confirm_btn.click()
        self.page.wait_for_timeout(5000)
        self.wait_for_page_ready()

    def obs_folder_create(self, folder_name):
        """在对象列表页新建文件夹。

        Args:
            folder_name: 文件夹名称
        """
        # 先关闭可能存在的弹窗
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 点击新建文件夹按钮
        self.page.get_by_text("新建文件夹", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取弹窗并输入文件夹名称（使用 :visible 避免匹配到隐藏的残留对话框）
        dialog = self.page.locator(".cv-dialog:visible, .el-dialog:visible").filter(
            has_text="新建文件夹"
        ).first
        expect(dialog).to_be_visible(timeout=10000)
        dialog.get_by_placeholder("请输入文件夹名称").fill(folder_name)
        self.page.wait_for_timeout(300)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        # 文件夹创建后列表异步刷新，新桶首次创建需更长时间
        self.page.wait_for_timeout(5000)
        self.wait_for_page_ready()
        self.page.wait_for_timeout(2000)

    def obs_object_enter_folder(self, folder_name):
        """在对象列表中点击文件夹名称，进入文件夹内部。

        Args:
            folder_name: 文件夹名称
        """
        self.page.get_by_text(folder_name, exact=True).first.click()
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1500)

    def obs_object_back_to_list(self, bucket_name):
        """从文件夹内部返回到桶的对象列表页。

        优先尝试点击页面返回按钮/面包屑，失败则通过导航重新进入桶详情页。

        Args:
            bucket_name: 桶名称，用于导航回退失败时重新进入
        """
        # 策略1：点击返回按钮或面包屑
        back_selectors = [
            ".el-page-header__left",
            ".breadcrumb-back",
            ".back-btn",
            ".el-breadcrumb",
        ]
        for selector in back_selectors:
            back_btn = self.page.locator(selector).first
            if back_btn.count() > 0 and back_btn.is_visible():
                try:
                    back_btn.click()
                    self.page.wait_for_timeout(1500)
                    self.wait_for_page_ready()
                    return
                except Exception:
                    continue

        # 策略2：通过导航重新进入桶的对象列表
        self.goto_submenu("桶列表")
        self.obs_bucket_enter_detail(bucket_name)
        self.obs_object_tab_click()

    def obs_object_batch_upload(self, file_paths):
        """在对象列表页批量上传多个文件。

        包含完整的交互流程：打开上传弹窗 -> 选择多个文件 -> 立即上传 -> 关闭任务列表。

        Args:
            file_paths: 本地文件路径列表
        """
        # 点击上传对象按钮
        self.page.get_by_text("上传对象", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取上传弹窗
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="上传对象"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        # 设置多个文件（批量上传）
        file_input = self.page.locator("#obsUploadInput")
        if file_input.count() == 0:
            file_input = self.page.locator('input[type="file"]')
        file_input.set_input_files(file_paths)
        self.page.wait_for_timeout(2000)

        # 点击立即上传
        dialog.get_by_text("立即上传", exact=True).first.click()
        # 大文件批量上传需要较长时间等待后台处理完成
        self.page.wait_for_timeout(25000)

        # 关闭任务列表面板
        self._close_task_list_panel_if_exists()

    def obs_folder_delete(self, folder_name):
        """删除指定文件夹。

        Args:
            folder_name: 文件夹名称
        """
        # 先关闭可能存在的弹窗
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 点击删除操作：先尝试 _click_object_action（hover 渲染），
        # 若未弹出确认对话框则回退到 click_action（处理下拉菜单模式）
        self._click_object_action(folder_name, "删除")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 检查是否有确认对话框出现
        has_dialog = self.page.locator(
            ".cv-dialog:visible, .el-dialog:visible, .el-message-box:visible"
        ).count() > 0
        if not has_dialog:
            # _click_object_action 未触发删除，回退到 click_action
            self.click_action(folder_name, "删除")
            self.wait_for_page_ready()
            self.page.wait_for_timeout(3000)

        # 确认删除：只定位当前可见对话框，避免匹配到残留旧弹窗
        try:
            dialog = self.page.locator(
                ".cv-dialog:visible, .el-dialog:visible, .el-message-box:visible"
            ).first
            dialog.wait_for(state="visible", timeout=10000)
            confirm_btn = dialog.get_by_text("确定", exact=True).first
            if confirm_btn.count() > 0:
                try:
                    confirm_btn.click(force=True)
                except Exception:
                    confirm_btn.evaluate("el => el.click()")
            else:
                dialog.evaluate("""
                    (dialog) => {
                        const btn = dialog.querySelector('.cl-dialog-footer, .el-dialog__footer, .dialog-footer, .el-message-box__btns');
                        if (btn) {
                            const confirm = btn.querySelector('button, .cloud-button-btn');
                            if (confirm && confirm.innerText.includes('确定')) {
                                confirm.click();
                                return 'clicked';
                            }
                        }
                        return 'not-found';
                    }
                """)
        except Exception:
            # fallback 到公共 dialog_confirm
            try:
                self.dialog_confirm.click(force=True)
            except Exception:
                self.dialog_confirm.evaluate("el => el.click()")
        self.wait_for_page_ready()

    # ---- 个人凭证方法 ----

    def obs_credential_click_create(self):
        """点击"新增访问密钥"或"新建"按钮打开新建弹窗。

        兼容旧版(index.vue: "新增访问密钥")和新版(index-new.vue: "新建")页面。
        """
        # 优先尝试新版按钮文本"新建"
        btn = self.page.get_by_text("新建", exact=True)
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)
            return

        # 回退到旧版按钮文本"新增访问密钥"
        btn = self.page.get_by_text("新增访问密钥")
        if btn.count() > 0:
            btn.first.click()
            self.page.wait_for_timeout(1500)
            return

        raise AssertionError("未找到'新建'或'新增访问密钥'按钮")

    def obs_credential_create_dialog_fill(self, description):
        """在新建访问密钥弹窗中填写描述信息。

        Args:
            description: 描述文本
        """
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建访问密钥"
        ).first
        expect(dialog).to_be_visible(timeout=10000)
        desc_input = dialog.get_by_placeholder("请输入访问密钥信息，非必填")
        desc_input.fill(description)
        self.page.wait_for_timeout(500)

    def _find_visible_dialog(self, text):
        """查找包含指定文本的可见对话框。

        兼容 Element UI 在 DOM 中保留隐藏对话框的情况。
        通过 JS 直接检查 computedStyle 判定可见性，避免 Playwright
        is_visible() 对 dialog wrapper 状态判断不准的问题。
        """
        for _ in range(50):
            visible_idx = self.page.evaluate(
                """
                (text) => {
                    const allDialogs = document.querySelectorAll('.cv-dialog, .el-dialog');
                    let matchedIdx = -1;
                    for (let i = 0; i < allDialogs.length; i++) {
                        const d = allDialogs[i];
                        if (d.textContent.includes(text)) {
                            matchedIdx++;
                            const style = window.getComputedStyle(d);
                            const wrapper = d.closest('.el-dialog__wrapper, .v-modal');
                            const wStyle = wrapper ? window.getComputedStyle(wrapper) : null;
                            if (style.display !== 'none' && style.visibility !== 'hidden' &&
                                (!wStyle || (wStyle.display !== 'none' && wStyle.visibility !== 'hidden'))) {
                                return matchedIdx;
                            }
                        }
                    }
                    return -1;
                }
                """,
                text,
            )
            if visible_idx >= 0:
                dialogs = self.page.locator(".cv-dialog, .el-dialog").filter(
                    has_text=text
                )
                try:
                    return dialogs.nth(visible_idx)
                except Exception:
                    pass
            self.page.wait_for_timeout(300)
        return None

    def obs_credential_create_dialog_confirm(self):
        """点击确定按钮创建访问密钥，等待成功弹窗并提取 AK/SK。

        Returns:
            tuple: (ak, sk) 访问密钥对
        """
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建访问密钥"
        ).first
        expect(dialog).to_be_visible(timeout=10000)
        confirm_btn = dialog.get_by_text("确定", exact=True).first
        expect(confirm_btn).to_be_visible(timeout=10000)
        confirm_btn.click()
        self.page.wait_for_timeout(12000)

        # 等待创建成功弹窗
        success_dialog = self._find_visible_dialog("创建密钥成功")
        assert success_dialog is not None, "未找到可见的'创建密钥成功'弹窗"
        expect(success_dialog).to_be_visible(timeout=10000)

        # 提取 AK
        ak = None
        ak_areas = success_dialog.locator(".auth-message-area").filter(
            has_text="Access Key ID"
        )
        if ak_areas.count() > 0:
            ak_p = ak_areas.first.locator("p").nth(1)
            ak = ak_p.inner_text().strip()

        # 提取 SK
        sk = None
        sk_areas = success_dialog.locator(".auth-message-area").filter(
            has_text="Secret Access Key"
        )
        if sk_areas.count() > 0:
            sk_p = sk_areas.first.locator("p").nth(1)
            sk = sk_p.inner_text().strip()

        return ak, sk

    def obs_credential_close_success_dialog(self):
        """关闭"创建密钥成功"弹窗。"""
        success_dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="创建密钥成功"
        ).first
        expect(success_dialog).to_be_visible(timeout=10000)
        success_dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(1500)
        self.wait_for_page_ready()

    def obs_credential_delete(self, ak):
        """根据 Access Key ID 删除访问密钥。

        Args:
            ak: Access Key ID
        """
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 优先使用 click_action 处理下拉菜单模式
        try:
            self.click_action(ak, "删除")
        except Exception:
            # fallback: 使用 _click_object_action
            result = self._click_object_action(ak, "删除")
            if result == 'not-found':
                return  # 凭证不存在，无需删除

        self.page.wait_for_timeout(2000)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="删除访问密钥"
        ).first
        if dialog.count() > 0:
            dialog.get_by_text("确定", exact=True).first.click()
            self.page.wait_for_timeout(3000)
        else:
            # 无确认弹窗则尝试通用确定按钮，仍失败则视为已删除
            try:
                self.dialog_confirm.click()
                self.page.wait_for_timeout(3000)
            except Exception:
                self.logger.warning("删除凭证后未检测到确认弹窗，视为已删除")
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
        self.wait_for_page_ready()

    def obs_credential_stop(self, ak):
        """停用指定 Access Key ID 的访问密钥。

        Args:
            ak: Access Key ID
        """
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 优先使用 click_action 处理下拉菜单模式
        try:
            self.click_action(ak, "停用")
        except Exception:
            # fallback: 使用 _click_object_action
            result = self._click_object_action(ak, "停用")
            if result == 'not-found':
                return  # 凭证不存在或已停用，无需操作

        self.page.wait_for_timeout(2000)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="停用访问密钥"
        ).first
        if dialog.count() > 0:
            dialog.get_by_text("确定", exact=True).first.click()
            self.page.wait_for_timeout(3000)
        else:
            # 无确认弹窗则尝试通用确定按钮
            try:
                self.dialog_confirm.click()
                self.page.wait_for_timeout(3000)
            except Exception:
                self.logger.warning("停用凭证后未检测到确认弹窗，视为已停用")
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(500)
        self.wait_for_page_ready()

    # ---- 桶存储策略方法 ----

    def obs_bucket_storage_policy_config_click(self):
        """在桶详情页点击存储策略卡片的'点击配置'按钮，进入存储策略管理页面。"""
        policy_card = self.page.locator(".safe-config-container").filter(
            has_text="存储策略"
        ).first
        expect(policy_card).to_be_visible(timeout=10000)
        config_btn = policy_card.get_by_text("点击配置", exact=True)
        config_btn.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_storage_policy_create(self, rule_name, object_attr="桶内所有对象",
                                   storage_class=None, priority=None):
        """在存储策略管理页面新建存储策略。

        Args:
            rule_name: 策略名称
            object_attr: 对象属性，"桶内所有对象"或"桶内特定对象"，默认"桶内所有对象"
            storage_class: 存储类别，None表示使用默认值（标准存储）
            priority: 策略优先级（1-32），None表示随机选择可用优先级
        """
        # 兼容新版("新建")和旧版("添加存储策略")按钮
        add_btn = self.page.get_by_text("新建", exact=True)
        if add_btn.count() == 0:
            add_btn = self.page.get_by_text("添加存储策略")
        add_btn.first.click()
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建存储策略"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        # 填写策略名称
        dialog.locator('input[placeholder*="请输入策略名称"]').fill(rule_name)
        self.page.wait_for_timeout(300)

        # 选择对象属性
        if object_attr == "桶内所有对象":
            dialog.get_by_text("桶内所有对象", exact=True).first.click()
        elif object_attr == "桶内特定对象":
            dialog.get_by_text("桶内特定对象", exact=True).first.click()
        self.page.wait_for_timeout(500)

        # 存储类别：若需指定则点击，否则使用默认值
        if storage_class:
            dialog.get_by_text(storage_class, exact=True).first.click()
            self.page.wait_for_timeout(300)

        # 策略优先级：若未指定则随机选择可用项
        if priority:
            priority_select = dialog.locator('input[placeholder="请选择策略优先级"]')
            priority_select.click()
            self.page.wait_for_timeout(500)
            self.page.evaluate(
                """
                (val) => {
                    const items = document.querySelectorAll('.el-select-dropdown__item');
                    for (let item of items) {
                        if (item.innerText.trim() === String(val) && !item.classList.contains('is-disabled')) {
                            item.click();
                            return 'clicked';
                        }
                    }
                    return 'not-found';
                }
                """,
                priority,
            )
            self.page.wait_for_timeout(500)
        else:
            # 随机选择一个可用的优先级
            priority_select = dialog.locator('input[placeholder="请选择策略优先级"]')
            priority_select.click()
            self.page.wait_for_timeout(500)
            self.page.evaluate(
                """
                () => {
                    const items = document.querySelectorAll('.el-select-dropdown__item');
                    const available = [];
                    for (let item of items) {
                        if (!item.classList.contains('is-disabled')) {
                            available.push(item);
                        }
                    }
                    if (available.length > 0) {
                        const idx = Math.floor(Math.random() * available.length);
                        available[idx].click();
                        return available[idx].innerText.trim();
                    }
                    return 'no-available';
                }
                """
            )
            self.page.wait_for_timeout(500)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_storage_policy_assert_contain(self, rule_name):
        """断言存储策略列表中包含指定策略名称。

        Args:
            rule_name: 策略名称
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=rule_name)
        expect(rows.first).to_be_visible(timeout=10000)

    def obs_storage_policy_get_row_data(self, rule_name):
        """获取存储策略列表中指定策略名称的行数据。

        Args:
            rule_name: 策略名称
        Returns:
            行数据字典，若不存在则返回 None
        """
        return self.get_row_data(rule_name)

    # ---- 桶ACL方法 ----

    def obs_bucket_acl_config_click(self):
        """在桶详情页点击桶ACLs卡片的'点击配置'按钮，进入ACL配置页面。"""
        # 先确保页面基础加载完成
        self.wait_for_page_ready()
        self.page.wait_for_timeout(1500)

        # 卡片可能异步渲染，使用重试查找
        acl_card = None
        for attempt in range(3):
            acl_card = self.page.locator(".safe-config-container").filter(
                has_text="桶ACLs"
            ).first
            try:
                expect(acl_card).to_be_visible(timeout=15000)
                break
            except Exception as e:
                self.logger.info(
                    f"桶ACLs卡片查找尝试 {attempt + 1}/3 失败: {e}"
                )
                if attempt < 2:
                    self.wait_for_page_ready()
                    self.page.wait_for_timeout(2000)
                else:
                    raise

        config_btn = acl_card.get_by_text("点击配置", exact=True)
        config_btn.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_bucket_acl_create(self, project_id, read_permission=True,
                               object_read_permission=True, write_permission=False):
        """在桶ACL配置页面新建ACL权限。

        Args:
            project_id: 项目ID
            read_permission: 是否勾选桶读取权限，默认True
            object_read_permission: 是否勾选对象读权限，默认True
            write_permission: 是否勾选桶写入权限，默认False
        """
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建ACL权限"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        dialog.get_by_placeholder("请输入项目ID").fill(project_id)
        self.page.wait_for_timeout(500)

        if read_permission:
            dialog.get_by_text("读取权限", exact=True).first.click()
            self.page.wait_for_timeout(500)

        if object_read_permission:
            dialog.get_by_text("对象读权限", exact=True).first.click()
            self.page.wait_for_timeout(500)

        if write_permission:
            dialog.get_by_text("写入权限", exact=True).first.click()
            self.page.wait_for_timeout(500)

        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_bucket_acl_delete(self, project_name):
        """删除指定项目的ACL配置。

        Args:
            project_name: 项目名称
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=project_name)
        if rows.count() == 0:
            return

        delete_btn = rows.first.locator("button, a, .el-link").filter(
            has_text="删除"
        ).first
        if delete_btn.count() > 0:
            delete_btn.click()
            self.page.wait_for_timeout(2000)

            confirm_dialog = self.page.locator(
                ".cv-dialog, .el-dialog"
            ).filter(has_text="删除").first
            if confirm_dialog.count() > 0:
                confirm_dialog.get_by_text("确定", exact=True).first.click()
                self.page.wait_for_timeout(3000)
                self.wait_for_page_ready()

    def obs_bucket_acl_assert_contain(self, project_name):
        """断言ACL列表或公共访问权限列表中包含指定项目/用户。

        Args:
            project_name: 项目名称或"所有用户"
        """
        # 策略1：在公共访问权限表格中查找（适用于"所有用户"）
        public_table = self.page.locator(".table-main").filter(
            has_text="公共访问权限"
        ).first
        if public_table.count() > 0 and public_table.is_visible():
            rows = public_table.locator("tr").filter(has_text=project_name)
            if rows.count() > 0 and rows.first.is_visible():
                return

        # 策略2：在ACL权限列表表格中查找
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=project_name)
        expect(rows.first).to_be_visible(timeout=10000)

    def obs_bucket_acl_public_edit(self, user_type="所有用户",
                                    read_permission=True,
                                    object_read_permission=True,
                                    write_permission=False,
                                    acl_read_permission=False,
                                    acl_write_permission=False):
        """编辑桶ACLs公共访问权限（所有用户或平台注册用户）。

        在桶ACL配置页面的公共访问权限列表中，找到指定用户类型行，
        点击编辑，勾选/取消指定权限后确定。

        Args:
            user_type: 用户类型，"所有用户" 或 "平台注册用户"，默认"所有用户"
            read_permission: 是否勾选桶读取权限，默认True
            object_read_permission: 是否勾选对象读权限，默认True
            write_permission: 是否勾选桶写入权限，默认False
            acl_read_permission: 是否勾选ACL读取权限，默认False
            acl_write_permission: 是否勾选ACL写入权限，默认False
        """
        self.page.wait_for_timeout(2000)
        # 找到公共访问权限表格
        public_table = self.page.locator(".table-main").filter(
            has_text="公共访问权限"
        ).first
        expect(public_table).to_be_visible(timeout=10000)

        # 找到指定用户类型的行
        target_row = public_table.locator("tr").filter(
            has_text=user_type
        ).first
        expect(target_row).to_be_visible(timeout=5000)

        # 点击编辑按钮（兼容平铺按钮和下拉菜单）
        try:
            edit_btn = target_row.locator("button, a, .el-link").filter(
                has_text="编辑"
            ).first
            if edit_btn.count() > 0 and edit_btn.is_visible():
                edit_btn.click()
            else:
                raise Exception("未找到可见的编辑按钮")
        except Exception:
            # fallback: 使用 click_action 处理下拉菜单模式
            self.click_action(user_type, "编辑")
        self.page.wait_for_timeout(1500)

        dialog = self._find_visible_dialog("编辑ACL权限")
        assert dialog is not None, "未找到可见的'编辑ACL权限'弹窗"
        expect(dialog).to_be_visible(timeout=10000)

        def _toggle_checkbox_in_section(section, label, want_checked):
            """在指定 form-item 区域内根据期望状态勾选或取消复选框。"""
            if section is None or section.count() == 0:
                return
            checkbox = section.get_by_text(label, exact=True).first
            if checkbox.count() == 0:
                return
            checkbox_input = checkbox.locator("xpath=../span/input")
            if checkbox_input.count() > 0:
                is_checked = checkbox_input.evaluate("el => el.checked")
                if is_checked != want_checked:
                    try:
                        # force=True 绕过 disabled/enable 检测
                        checkbox.click(force=True)
                    except Exception:
                        # 降级：JS 直接点击父级 label
                        checkbox.locator("xpath=..").evaluate(
                            "el => el.click()"
                        )
                    self.page.wait_for_timeout(800)

        # 分别定位桶访问权限和ACL访问权限区域，避免重复标签串扰
        bucket_access_section = dialog.locator(".el-form-item").filter(
            has_text="桶访问权限"
        ).first
        acl_section = dialog.locator(".el-form-item").filter(
            has_text="ACL访问权限"
        ).first

        # 桶访问权限
        _toggle_checkbox_in_section(bucket_access_section, "读取权限", read_permission)
        _toggle_checkbox_in_section(bucket_access_section, "对象读权限", object_read_permission)
        _toggle_checkbox_in_section(bucket_access_section, "写入权限", write_permission)

        # ACL访问权限
        _toggle_checkbox_in_section(acl_section, "读取权限", acl_read_permission)
        _toggle_checkbox_in_section(acl_section, "写入权限", acl_write_permission)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)

        # 验证弹窗已关闭，若未关闭则尝试补救
        for _ in range(10):
            still_open = self.page.evaluate(
                """
                () => {
                    const dialogs = document.querySelectorAll('.cv-dialog, .el-dialog');
                    for (let d of dialogs) {
                        if (d.textContent.includes('编辑ACL权限')) {
                            const style = window.getComputedStyle(d);
                            const wrapper = d.closest('.el-dialog__wrapper, .v-modal');
                            const wStyle = wrapper ? window.getComputedStyle(wrapper) : null;
                            if (style.display !== 'none' && style.visibility !== 'hidden' &&
                                (!wStyle || (wStyle.display !== 'none' && wStyle.visibility !== 'hidden'))) {
                                return true;
                            }
                        }
                    }
                    return false;
                }
                """
            )
            if not still_open:
                break
            self.page.wait_for_timeout(500)
        else:
            # 弹窗仍未关闭，尝试 Escape
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(1000)

        self.wait_for_page_ready()

    # ---- 对象ACL方法 ----

    def obs_object_acl_tab_click(self):
        """在对象详情页点击'对象ACLs' tab，确保ACL内容可见。

        对象详情页默认 activeName='acl'，但为确保页面状态正确，
        显式点击对象ACLs tab。
        """
        acl_tab = self.page.locator(".el-tabs__item").filter(
            has_text="对象ACLs"
        ).first
        if acl_tab.count() > 0 and acl_tab.is_visible():
            acl_tab.click()
            self.page.wait_for_timeout(1500)
        self.wait_for_page_ready()

    def obs_object_acl_create(self, project_id, read_permission=True,
                               write_permission=False):
        """在对象ACL配置页面新建ACL权限。

        Args:
            project_id: 项目ID
            read_permission: 是否勾选对象读取权限，默认True
            write_permission: 是否勾选ACL写入权限，默认False
        """
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="新建ACL权限"
        ).first
        expect(dialog).to_be_visible(timeout=10000)

        dialog.get_by_placeholder("请输入项目ID").fill(project_id)
        self.page.wait_for_timeout(500)

        if read_permission:
            dialog.get_by_text("读取权限", exact=True).first.click()
            self.page.wait_for_timeout(500)

        if write_permission:
            dialog.get_by_text("写入权限", exact=True).first.click()
            self.page.wait_for_timeout(500)

        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_object_acl_public_edit(self, user_type="所有用户",
                                    object_read_permission=False,
                                    acl_read_permission=False,
                                    acl_write_permission=False):
        """编辑对象ACLs公共访问权限（所有用户或平台注册用户）。

        在对象ACL配置页面的公共访问权限列表中，找到指定用户类型行，
        点击编辑，勾选/取消指定权限后确定。

        Args:
            user_type: 用户类型，"所有用户" 或 "平台注册用户"，默认"所有用户"
            object_read_permission: 是否勾选对象读取权限，默认False
            acl_read_permission: 是否勾选ACL读取权限，默认False
            acl_write_permission: 是否勾选ACL写入权限，默认False
        """
        self.page.wait_for_timeout(2000)
        # 找到公共访问权限表格
        public_table = self.page.locator(".table-main").filter(
            has_text="公共访问权限"
        ).first
        expect(public_table).to_be_visible(timeout=10000)

        # 找到指定用户类型的行
        target_row = public_table.locator("tr").filter(
            has_text=user_type
        ).first
        expect(target_row).to_be_visible(timeout=5000)

        # 点击编辑按钮（兼容平铺按钮和下拉菜单）
        try:
            edit_btn = target_row.locator("button, a, .el-link").filter(
                has_text="编辑"
            ).first
            if edit_btn.count() > 0 and edit_btn.is_visible():
                edit_btn.click()
            else:
                raise Exception("未找到可见的编辑按钮")
        except Exception:
            self.click_action(user_type, "编辑")
        self.page.wait_for_timeout(1500)

        dialog = self._find_visible_dialog("编辑ACL权限")
        assert dialog is not None, "未找到可见的'编辑ACL权限'弹窗"
        expect(dialog).to_be_visible(timeout=10000)

        def _toggle_checkbox_in_section(section, label, want_checked):
            """在指定 form-item 区域内根据期望状态勾选或取消复选框。

            通过遍历 section 内所有 checkbox input，用 JS 匹配 label 文本，
            确保操作的是正确的复选框。
            """
            if section is None or section.count() == 0:
                return
            checkbox_inputs = section.locator("input[type='checkbox']").all()
            for inp in checkbox_inputs:
                label_text = inp.evaluate(
                    """
                    el => {
                        const id = el.id;
                        if (id) {
                            const lbl = document.querySelector(`label[for="${id}"]`);
                            if (lbl) return lbl.innerText.trim();
                        }
                        const parent = el.closest('label');
                        if (parent) return parent.innerText.trim();
                        const sibling = el.parentElement?.nextElementSibling;
                        if (sibling) return sibling.innerText.trim();
                        return '';
                    }
                    """
                )
                if label_text == label or label in label_text:
                    is_checked = inp.evaluate("el => el.checked")
                    if is_checked != want_checked:
                        # 优先点击 label 以触发 Element UI change 事件
                        inp.evaluate("""
                            el => {
                                const id = el.id;
                                if (id) {
                                    const lbl = document.querySelector(`label[for="${id}"]`);
                                    if (lbl) { lbl.click(); return; }
                                }
                                const parent = el.closest('label');
                                if (parent) { parent.click(); return; }
                                el.click();
                            }
                        """)
                        self.page.wait_for_timeout(800)
                        # 验证状态确实改变
                        new_checked = inp.evaluate("el => el.checked")
                        if new_checked != want_checked:
                            self.logger.warning(
                                f"复选框点击后状态未改变: {label} "
                                f"期望={want_checked}, 实际={new_checked}, 重试"
                            )
                            inp.evaluate("el => el.click()")
                            self.page.wait_for_timeout(800)
                    break

        # 分别定位对象访问权限和ACL访问权限区域
        object_access_section = dialog.locator(".el-form-item").filter(
            has_text="对象访问权限"
        ).first
        acl_section = dialog.locator(".el-form-item").filter(
            has_text="ACL访问权限"
        ).first

        # 对象访问权限
        _toggle_checkbox_in_section(
            object_access_section, "读取权限", object_read_permission
        )

        # ACL访问权限
        _toggle_checkbox_in_section(
            acl_section, "读取权限", acl_read_permission
        )
        _toggle_checkbox_in_section(
            acl_section, "写入权限", acl_write_permission
        )

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(8000)

        # 验证弹窗已关闭，若未关闭则尝试补救
        for _ in range(10):
            still_open = self.page.evaluate(
                """
                () => {
                    const dialogs = document.querySelectorAll('.cv-dialog, .el-dialog');
                    for (let d of dialogs) {
                        if (d.textContent.includes('编辑ACL权限')) {
                            const style = window.getComputedStyle(d);
                            const wrapper = d.closest('.el-dialog__wrapper, .v-modal');
                            const wStyle = wrapper ? window.getComputedStyle(wrapper) : null;
                            if (style.display !== 'none' && style.visibility !== 'hidden' &&
                                (!wStyle || (wStyle.display !== 'none' && wStyle.visibility !== 'hidden'))) {
                                return true;
                            }
                        }
                    }
                    return false;
                }
                """
            )
            if not still_open:
                break
            self.page.wait_for_timeout(500)
        else:
            # 多重补救：Escape → 点击取消 → 点击遮罩层
            self.page.keyboard.press("Escape")
            self.page.wait_for_timeout(1000)
            try:
                cancel_btn = self.page.locator(
                    ".cv-dialog, .el-dialog"
                ).filter(has_text="编辑ACL权限").first.locator(
                    "button, .el-button"
                ).filter(has_text="取消").first
                if cancel_btn.count() > 0 and cancel_btn.is_visible():
                    cancel_btn.click()
                    self.page.wait_for_timeout(1500)
            except Exception:
                pass
            # 最后尝试点击遮罩层关闭
            self.page.evaluate("""
                () => {
                    const wrappers = document.querySelectorAll('.el-dialog__wrapper, .v-modal');
                    for (const w of wrappers) {
                        const style = window.getComputedStyle(w);
                        if (style.display !== 'none' && style.visibility !== 'hidden') {
                            w.click();
                        }
                    }
                }
            """)
            self.page.wait_for_timeout(1000)

        self.wait_for_page_ready()

    def obs_object_acl_delete(self, project_name):
        """删除指定项目的对象ACL配置。

        Args:
            project_name: 项目名称
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=project_name)
        if rows.count() == 0:
            return

        delete_btn = rows.first.locator("button, a, .el-link").filter(
            has_text="删除"
        ).first
        if delete_btn.count() > 0:
            delete_btn.click()
            self.page.wait_for_timeout(2000)

            confirm_dialog = self.page.locator(
                ".cv-dialog, .el-dialog"
            ).filter(has_text="删除").first
            if confirm_dialog.count() > 0:
                confirm_dialog.get_by_text("确定", exact=True).first.click()
                self.page.wait_for_timeout(3000)
                self.wait_for_page_ready()

    def obs_object_acl_assert_contain(self, project_name):
        """断言对象ACL列表中包含指定项目。

        Args:
            project_name: 项目名称
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=project_name)
        expect(rows.first).to_be_visible(timeout=10000)

    # ---- 访问代理方法 ----

    def obs_proxy_open_create_dialog(self):
        """点击新建按钮，打开自定义域名弹窗。

        Returns:
            Locator: 弹窗定位器
        """
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="自定义域名"
        ).first
        expect(dialog).to_be_visible(timeout=10000)
        return dialog

    def obs_proxy_fill_dialog(self, dialog, domain_name, vpc_name=None):
        """在自定义域名弹窗中填写信息。

        Args:
            dialog: 弹窗定位器
            domain_name: 内网访问域名
            vpc_name: VPC名称，None表示随机选择第一个可用选项

        Returns:
            str: 选择的VPC名称
        """
        # 填写内网访问域名
        dialog.get_by_placeholder("请输入内网访问域名").fill(domain_name)
        self.page.wait_for_timeout(300)

        # 选择VPC
        vpc_select = dialog.locator('input[placeholder="请选择"]')
        expect(vpc_select.first).to_be_visible(timeout=10000)
        vpc_select.first.click()

        # 等待下拉框选项渲染，使用轮询等待而非固定等待
        self.page.wait_for_timeout(300)
        options = self.page.locator(".el-select-dropdown__item")
        assert options.count() > 0, "没有可用的VPC选项"

        selected_vpc = None
        if vpc_name:
            option = options.filter(has_text=vpc_name).first
            expect(option).to_be_visible(timeout=10000)
            selected_vpc = vpc_name
            option.click()
        else:
            selected_vpc = options.first.inner_text().strip()
            # 使用JS直接点击避免下拉框关闭导致元素不可见
            options.first.evaluate("el => el.click()")
        # 关闭下拉框：点击弹窗标题区域，避免遮挡确定按钮
        dialog.locator(".el-dialog__header, .cv-dialog-header").first.click()
        self.page.wait_for_timeout(500)
        return selected_vpc

    def obs_proxy_submit_dialog(self, dialog):
        """点击确定提交自定义域名弹窗。

        提交后重新导航到访问代理页面，确保列表数据已刷新。

        Args:
            dialog: 弹窗定位器
        """
        dialog.get_by_text("确定", exact=True).first.click()
        # 等待弹窗完全关闭（包括遮罩层）
        self.page.wait_for_timeout(5000)
        # 确认遮罩层已消失
        mask = self.page.locator(".el-dialog__wrapper, .v-modal")
        try:
            if mask.count() > 0:
                mask.first.wait_for(state="hidden", timeout=10000)
        except Exception:
            pass
        self.wait_for_page_ready()
        # 重新导航到访问代理页面，强制刷新列表数据
        self.goto_submenu("访问代理")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

    def _close_proxy_dialog(self):
        """强制关闭访问代理创建/编辑对话框（JS方式）。

        用于obs_proxy_create后确保对话框完全关闭，
        避免close_dialog_if_exists无法识别特定Vue对话框的问题。
        """
        self.page.evaluate(
            """
            () => {
                function findVueInstance(root, predicate) {
                    if (!root) return null;
                    if (predicate(root)) return root;
                    for (let child of root.$children || []) {
                        const found = findVueInstance(child, predicate);
                        if (found) return found;
                    }
                    return null;
                }
                const appEl = document.querySelector('#app') || document.querySelector('[id^="app"]');
                const app = appEl && appEl.__vue__;
                if (!app) return;
                const proxyPage = findVueInstance(app, (vm) => {
                    return vm.$refs && vm.$refs.createDialog;
                });
                if (proxyPage && proxyPage.$refs.createDialog) {
                    proxyPage.$refs.createDialog.dialogVisible = false;
                }
                // 同时尝试点击关闭按钮
                const closeBtns = document.querySelectorAll('.el-dialog__headerbtn, .cv-dialog-header .close-btn, .el-message-box__headerbtn');
                closeBtns.forEach(btn => btn.click());
            }
            """
        )
        self.page.wait_for_timeout(500)

    def obs_proxy_create(self, domain_name, vpc_name=None):
        """新建访问代理（自定义域名）。

        使用JS直接操作Vue实例完成表单填写和提交，
        避免UI交互不稳定导致的点击失败问题。

        Args:
            domain_name: 内网访问域名
            vpc_name: VPC名称，None表示随机选择第一个可用选项

        Returns:
            str: 选择的VPC名称
        """
        # 先确保没有残留的创建对话框
        self._close_proxy_dialog()
        self.close_dialog_if_exists()

        # 点击新建按钮打开弹窗
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(2000)

        # 通过JS直接操作Vue实例完成创建
        result = self.page.evaluate(
            """
            (args) => {
                const [domainName, targetVpcName] = args;

                function findVueInstance(root, predicate) {
                    if (!root) return null;
                    if (predicate(root)) return root;
                    for (let child of root.$children || []) {
                        const found = findVueInstance(child, predicate);
                        if (found) return found;
                    }
                    return null;
                }

                const appEl = document.querySelector('#app') || document.querySelector('[id^="app"]');
                const app = appEl && appEl.__vue__;
                if (!app) return { error: 'no-app' };

                // 查找访问代理页面组件
                const proxyPage = findVueInstance(app, (vm) => {
                    return vm.$refs && vm.$refs.createDialog;
                });
                if (!proxyPage) return { error: 'no-proxy-page' };

                const createDialog = proxyPage.$refs.createDialog;
                if (!createDialog) return { error: 'no-create-dialog' };

                // 等待弹窗可见
                if (!createDialog.dialogVisible) return { error: 'dialog-not-visible' };

                // 获取项目ID
                const projectId = localStorage.getItem('ProjectId') || '';

                // 获取VPC列表，增加轮询等待
                let vpcOptions = createDialog.VpcOptions || [];
                let waitCount = 0;
                while (vpcOptions.length === 0 && waitCount < 10) {
                    waitCount++;
                    if (typeof createDialog.getVpcList === 'function') {
                        createDialog.getVpcList();
                    }
                    // 同步等待一小段时间
                    const start = Date.now();
                    while (Date.now() - start < 500) {
                        vpcOptions = createDialog.VpcOptions || [];
                        if (vpcOptions.length > 0) break;
                    }
                }
                if (vpcOptions.length === 0) {
                    return { error: 'vpc-list-empty' };
                }

                // 选择VPC
                let selectedVpc = vpcOptions[0];
                if (targetVpcName) {
                    const found = vpcOptions.find(v => v.name === targetVpcName);
                    if (found) selectedVpc = found;
                }

                // 设置表单数据
                createDialog.$set(createDialog.form, 'name', domainName);
                createDialog.$set(createDialog.form, 'project_id', projectId);
                createDialog.$set(createDialog.form, 'vpc', [selectedVpc.id]);

                // 调用确认方法提交
                createDialog.confirm();

                // 确保对话框关闭（confirm可能是异步的）
                setTimeout(() => {
                    if (createDialog.dialogVisible) {
                        createDialog.dialogVisible = false;
                    }
                }, 300);

                return {
                    vpcName: selectedVpc.name,
                    vpcId: selectedVpc.id,
                    projectId: projectId
                };
            }
            """,
            [domain_name, vpc_name],
        )

        # 如果VPC列表为空，在当前对话框内等待重试（不重新打开）
        if isinstance(result, dict) and result.get("error") == "vpc-list-empty":
            self.page.wait_for_timeout(3000)
            result = self.page.evaluate(
                """
                (args) => {
                    const [domainName, targetVpcName] = args;

                    function findVueInstance(root, predicate) {
                        if (!root) return null;
                        if (predicate(root)) return root;
                        for (let child of root.$children || []) {
                            const found = findVueInstance(child, predicate);
                            if (found) return found;
                        }
                        return null;
                    }

                    const appEl = document.querySelector('#app') || document.querySelector('[id^="app"]');
                    const app = appEl && appEl.__vue__;
                    if (!app) return { error: 'no-app' };

                    const proxyPage = findVueInstance(app, (vm) => {
                        return vm.$refs && vm.$refs.createDialog;
                    });
                    if (!proxyPage) return { error: 'no-proxy-page' };

                    const createDialog = proxyPage.$refs.createDialog;
                    if (!createDialog) return { error: 'no-create-dialog' };

                    if (!createDialog.dialogVisible) return { error: 'dialog-not-visible' };

                    const projectId = localStorage.getItem('ProjectId') || '';

                    let vpcOptions = createDialog.VpcOptions || [];
                    let waitCount = 0;
                    while (vpcOptions.length === 0 && waitCount < 15) {
                        waitCount++;
                        if (typeof createDialog.getVpcList === 'function') {
                            createDialog.getVpcList();
                        }
                        const start = Date.now();
                        while (Date.now() - start < 500) {
                            vpcOptions = createDialog.VpcOptions || [];
                            if (vpcOptions.length > 0) break;
                        }
                    }
                    if (vpcOptions.length === 0) {
                        return { error: 'vpc-list-empty-after-retry' };
                    }

                    let selectedVpc = vpcOptions[0];
                    if (targetVpcName) {
                        const found = vpcOptions.find(v => v.name === targetVpcName);
                        if (found) selectedVpc = found;
                    }

                    createDialog.$set(createDialog.form, 'name', domainName);
                    createDialog.$set(createDialog.form, 'project_id', projectId);
                    createDialog.$set(createDialog.form, 'vpc', [selectedVpc.id]);

                    createDialog.confirm();

                    setTimeout(() => {
                        if (createDialog.dialogVisible) {
                            createDialog.dialogVisible = false;
                        }
                    }, 300);

                    return {
                        vpcName: selectedVpc.name,
                        vpcId: selectedVpc.id,
                        projectId: projectId
                    };
                }
                """,
                [domain_name, vpc_name],
            )

        assert not isinstance(result, dict) or not result.get("error"), (
            f"访问代理创建失败: {result}"
        )

        # 等待提交完成和弹窗关闭
        self.page.wait_for_timeout(5000)

        # 强制关闭可能残留的对话框
        self._close_proxy_dialog()
        self.close_dialog_if_exists()

        self.wait_for_page_ready()

        # 重新导航到访问代理页面刷新列表
        self.goto_submenu("访问代理")
        self.wait_for_page_ready()
        self.page.wait_for_timeout(3000)

        # 轮询等待代理出现在列表中（后端创建是异步的，列表刷新可能延迟）
        for attempt in range(30):
            locator = self.page.get_by_text(domain_name, exact=True)
            if locator.count() > 0 and locator.first.is_visible():
                self.logger.info(f"访问代理 {domain_name} 已出现在列表中")
                break
            self.logger.info(
                f"访问代理 {domain_name} 未在列表中，等待...({attempt + 1}/30)"
            )
            self.page.wait_for_timeout(1000)
        else:
            self.logger.warning(
                f"访问代理 {domain_name} 创建后未在列表中找到，可能后端延迟较大"
            )

        return result.get("vpcName") if isinstance(result, dict) else None

    def obs_proxy_assert_contain(self, domain_name, timeout_seconds=30):
        """断言访问代理列表中包含指定域名。

        使用页面文本直接搜索，支持轮询重试，避免表格结构不稳定
        或后端异步刷新导致的断言失败。

        Args:
            domain_name: 内网访问域名
            timeout_seconds: 轮询超时时间，默认30秒
        """
        # 轮询等待域名出现在列表中
        for attempt in range(timeout_seconds):
            self.page.wait_for_timeout(1000)
            locator = self.page.get_by_text(domain_name, exact=True)
            if locator.count() > 0 and locator.first.is_visible():
                self.logger.info(f"断言通过: 访问代理列表中找到域名 {domain_name}")
                return
            self.logger.info(
                f"访问代理列表中未找到 {domain_name}，重试...({attempt + 1}/{timeout_seconds})"
            )
            # 每次重试后刷新页面（导航回当前页强制刷新列表）
            if (attempt + 1) % 5 == 0:
                self.goto_submenu("访问代理")
                self.wait_for_page_ready()

        # 若域名未找到，再判断是否列表为空（避免 false positive）
        empty_text = self.page.locator(".el-table__empty-text")
        if empty_text.count() > 0 and empty_text.first.is_visible():
            assert False, f"访问代理列表为空，未找到域名: {domain_name}"
        assert False, f"访问代理列表中未找到域名: {domain_name}"

    def obs_proxy_expand_detail(self, domain_name):
        """展开指定域名的访问代理详细信息。

        点击内网访问域名所在行的展开按钮（">"），
        展开后显示协议类型/请求方式/Url的嵌套表格。

        Args:
            domain_name: 内网访问域名
        """
        # 找到包含域名的行
        row = self.get_row_by_name(domain_name)
        # 展开按钮在行首的 expand 列
        expand_icon = row.locator(".el-table__expand-icon").first
        if expand_icon.count() > 0:
            # 检查当前是否已展开
            cls = expand_icon.get_attribute("class") or ""
            if "el-table__expand-icon--expanded" not in cls:
                # 使用JS直接触发点击，避免元素不可见问题
                expand_icon.evaluate("el => el.click()")
                self.page.wait_for_timeout(1500)
        else:
            # fallback：使用JS点击行首单元格触发展开
            row.locator("td").first.evaluate("el => el.click()")
            self.page.wait_for_timeout(1500)

    def obs_proxy_get_endpoint_urls(self, domain_name):
        """获取展开详情中的Endpoint URL记录。

        展开指定域名的详情后，读取嵌套表格中所有行的数据。

        Args:
            domain_name: 内网访问域名

        Returns:
            list: 每条记录为 {"type": str, "methods": str, "endPoint": str}
        """
        # 先展开详情
        self.obs_proxy_expand_detail(domain_name)

        # 获取展开区域内的嵌套表格行
        # 展开内容紧跟在域名行后面，通过 expanded-cell 定位
        expanded_cells = self.page.locator(".el-table__expanded-cell")
        results = []
        for i in range(expanded_cells.count()):
            cell = expanded_cells.nth(i)
            # 检查该展开单元格是否包含目标域名的引用（通过查找嵌套表格）
            sub_rows = cell.locator(".el-table__row")
            if sub_rows.count() == 0:
                continue
            for j in range(sub_rows.count()):
                sub_row = sub_rows.nth(j)
                cells = sub_row.locator("td")
                if cells.count() >= 3:
                    results.append({
                        "type": cells.nth(0).inner_text().strip(),
                        "methods": cells.nth(1).inner_text().strip(),
                        "endPoint": cells.nth(2).inner_text().strip(),
                    })
            # 找到第一个有数据的展开单元格即可
            if results:
                break
        return results

    def obs_proxy_delete(self, domain_name):
        """删除指定访问代理。

        Args:
            domain_name: 内网访问域名
        """
        self.close_dialog_if_exists()
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

        # 点击删除操作
        self.click_action(domain_name, "删除")
        self.page.wait_for_timeout(2000)

        # 确认删除
        dialog = self.page.locator(".cv-dialog, .el-dialog").filter(
            has_text="删除"
        ).first
        if dialog.count() > 0:
            dialog.get_by_text("确定", exact=True).first.click()
        else:
            self.dialog_confirm.click()

        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    # ---- 数据回源方法 ----

    def obs_bucket_endpoint_get(self, protocol="https"):
        """获取桶详情页 EndPoint 的 URL 地址。

        优先在"基础配置"页面查找 EndPoint 信息；
        若当前不在该页面，自动切换后重试。
        使用 JS 遍历 DOM 查找 EndPoint 标签附近的 URL，避免正则匹配到 HTML 中的无关链接。

        Args:
            protocol: 协议类型，"https" 或 "http"，默认 "https"

        Returns:
            str: URL 地址（不含桶名路径），如 "https://xxx:port" 或 "http://xxx:port"
        """
        # 辅助函数：通过 JS 在渲染后的 DOM 中搜索 EndPoint 附近的 URL
        def _js_extract():
            return self.page.evaluate("""
                () => {
                    const urlPattern = /https?:\\/\\/[^\\s]+/;
                    // 1. 查找包含 EndPoint/Endpoint 文本的元素
                    const walker = document.createTreeWalker(
                        document.body, NodeFilter.SHOW_TEXT, null, false
                    );
                    let node;
                    while (node = walker.nextNode()) {
                        const text = node.textContent.trim();
                        if (text === 'EndPoint' || text === 'Endpoint') {
                            // 向上查找父元素，搜索 URL
                            let el = node.parentElement;
                            for (let i = 0; i < 5 && el; i++, el = el.parentElement) {
                                const match = el.textContent.match(urlPattern);
                                if (match) {
                                    // 确保匹配的 URL 不是元素标签名或脚本内容
                                    const clean = match[0].replace(/[()]+$/, '');
                                    if (clean.startsWith('http')) return clean;
                                }
                            }
                        }
                    }
                    // 2. 兜底：搜索所有可见元素的文本内容
                    const allEls = document.querySelectorAll('div, span, p, td, li');
                    for (const el of allEls) {
                        const text = el.textContent;
                        if ((text.includes('EndPoint') || text.includes('Endpoint')) && text.includes('http')) {
                            const match = text.match(urlPattern);
                            if (match) {
                                const clean = match[0].replace(/[()]+$/, '');
                                if (clean.startsWith('http')) return clean;
                            }
                        }
                    }
                    return null;
                }
            """)

        # 辅助函数：通过 Playwright 定位器提取
        def _locator_extract():
            selectors = [
                self.page.locator(".cl-item-col").filter(has_text="EndPoint").first,
                self.page.locator(".el-form-item").filter(has_text="EndPoint").first,
                self.page.locator(".cl-form-item").filter(has_text="EndPoint").first,
                self.page.locator(".el-descriptions-item").filter(has_text="EndPoint").first,
                self.page.locator(".el-descriptions__cell").filter(has_text="EndPoint").first,
                self.page.locator(".info-item").filter(has_text="EndPoint").first,
                self.page.locator(".info-row").filter(has_text="EndPoint").first,
                self.page.locator("[class*='endpoint']").first,
                self.page.get_by_text("EndPoint", exact=True).locator("xpath=..").first,
                self.page.get_by_text("Endpoint", exact=True).locator("xpath=..").first,
            ]
            endpoint_col = None
            for sel in selectors:
                try:
                    if sel.count() > 0 and sel.is_visible():
                        endpoint_col = sel
                        break
                except Exception:
                    continue

            if endpoint_col is None:
                return None

            # hover 问号图标读取 tooltip（严格按需求文档步骤1：获取 S3 HTTPS URL）
            question_icon = endpoint_col.locator(
                ".el-icon-question, .icon-question, [class*='question']"
            ).first
            try:
                expect(question_icon).to_be_visible(timeout=3000)
                question_icon.hover()
                self.page.wait_for_timeout(3000)
                # 兼容多种 tooltip 类型和文本匹配
                tooltip_selectors = [
                    ".el-tooltip__popper",
                    ".el-popper",
                    ".el-popover",
                    ".v-tooltip",
                    ".tippy-box",
                    "[class*='tooltip']",
                    "[class*='popover']",
                ]
                tooltip = None
                for sel in tooltip_selectors:
                    candidates = self.page.locator(sel).all()
                    for cand in candidates:
                        try:
                            if cand.is_visible() and (
                                "S3" in cand.inner_text()
                                or "协议" in cand.inner_text()
                                or "HTTP" in cand.inner_text()
                                or "https://" in cand.inner_text()
                            ):
                                tooltip = cand
                                break
                        except Exception:
                            continue
                    if tooltip:
                        break

                if tooltip:
                    tooltip_text = tooltip.inner_text()
                    self.logger.info(f"EndPoint tooltip 内容: {tooltip_text[:200]}")
                    # 尝试从表格中提取 S3 + HTTPS 的 URL
                    rows = tooltip.locator("tr")
                    for i in range(rows.count()):
                        row = rows.nth(i)
                        cells = row.locator("td, th")
                        if cells.count() >= 3:
                            type_text = cells.nth(0).inner_text().strip()
                            method_text = cells.nth(1).inner_text().strip()
                            url_text = cells.nth(2).inner_text().strip()
                            method_match = "HTTPS" if protocol == "https" else "HTTP"
                            if "S3" in type_text and method_match in method_text:
                                return url_text
                    # 兜底：从 tooltip 文本中直接提取 https:// 开头的 URL
                    url_match = re.search(r'(https?://[^\s<>"\']+)', tooltip_text)
                    if url_match:
                        return url_match.group(1)
            except Exception as e:
                self.logger.info(f"EndPoint tooltip 提取异常: {e}")
                pass

            # 直接读取元素文本
            for content_sel in [".cl-item-content", ".el-form-item__content", "span"]:
                try:
                    endpoint_text = endpoint_col.locator(content_sel).first.inner_text().strip()
                    if endpoint_text and endpoint_text != "未配置" and re.match(r'^https?://', endpoint_text):
                        return endpoint_text
                except Exception:
                    continue
            return None

        # 先尝试当前页面
        result = _locator_extract()
        if result:
            return result
        result = _js_extract()
        if result:
            return result

        # 切换到"基础配置"后重试
        basic_config = self.page.get_by_text("基础配置", exact=True).first
        if basic_config.count() > 0 and basic_config.is_visible():
            basic_config.click()
            self.page.wait_for_timeout(2000)
            self.wait_for_page_ready()
            result = _locator_extract()
            if result:
                return result
            result = _js_extract()
            if result:
                return result

        # 策略4：按项目惯例构造（其他 OBS 用例均使用固定 OBS API 主机）
        # Web UI 主机与 OBS API 主机不同，OBS HTTP 端点固定为 172.22.1.187:20480，HTTPS 为 20481
        default_port = "20481" if protocol == "https" else "20480"
        constructed = f"{protocol}://172.22.1.187:{default_port}"
        self.logger.info(f"UI 提取 EndPoint 失败，使用构造地址: {constructed}")
        return constructed

    def obs_bucket_datasource_config_click(self):
        """在桶详情页点击数据回源卡片的'点击配置'按钮，进入数据回源页面。"""
        datasource_card = self.page.locator(".safe-config-container").filter(
            has_text="数据回源"
        ).first
        expect(datasource_card).to_be_visible(timeout=10000)
        config_btn = datasource_card.get_by_text("点击配置", exact=True)
        config_btn.click()
        self.page.wait_for_timeout(2000)
        self.wait_for_page_ready()

    def obs_datasource_mirror_rule_create(self, source_domain, source_bucket,
                                           source_port="443"):
        """在数据回源页面新建镜像回源规则。

        按照需求配置：
        - 回源类型：镜像回源
        - 代理回源：不开启
        - 强制写入：不开启
        - HTTP header 传递规则：全部参数
        - 源站类型：公有类型
        - HTTP 状态码：默认 404
        - 对象名称前缀：不配置
        - 添加前后缀：不开启
        - 替换前缀：不配置
        - 携带请求字符串：不开启
        - 回源地址：路径样式，协议 HTTPS

        Args:
            source_domain: 源站域名（步骤1记录的域名）
            source_bucket: 源站桶名称（bucket01）
            source_port: 源站端口，默认 443
        """
        # 点击新建
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取弹窗（使用 _find_visible_dialog 避免匹配到隐藏弹窗）
        dialog = self._find_visible_dialog("规则")
        assert dialog is not None, "未找到可见的规则弹窗"
        expect(dialog).to_be_visible(timeout=10000)

        # 回源类型：镜像回源（默认就是 Mirror，确保选中）
        mirror_radio = dialog.get_by_text("镜像回源", exact=True)
        if mirror_radio.count() > 0:
            mirror_radio.click()
            self.page.wait_for_timeout(500)

        # 代理回源：不开启（默认 false）
        # 强制写入：不开启（默认 false）
        # HTTP header 传递规则：全部参数（默认 PassAll）
        pass_all_checkbox = dialog.get_by_text("全部参数", exact=True)
        if pass_all_checkbox.count() > 0:
            checkbox_input = pass_all_checkbox.locator("xpath=../span/input")
            if checkbox_input.count() > 0:
                is_checked = checkbox_input.evaluate("el => el.checked")
                if not is_checked:
                    pass_all_checkbox.click()
                    self.page.wait_for_timeout(500)

        # 源站类型：公有类型（默认 false）
        public_radio = dialog.get_by_text("公有类型", exact=True)
        if public_radio.count() > 0:
            public_radio.click()
            self.page.wait_for_timeout(500)

        # HTTP 状态码：默认 404，disabled 状态无需操作
        # 对象名称前缀：不配置（留空）
        # 添加前后缀：不开启（默认 false）
        # 替换前缀：不配置（留空）
        # 携带请求字符串：不开启（默认 false）

        # 回源地址类型：路径样式
        path_style_radio = dialog.get_by_text("路径样式", exact=True)
        if path_style_radio.count() > 0:
            path_style_radio.click()
            self.page.wait_for_timeout(1000)

        # 路径样式主站配置
        # 协议选择 HTTPS（若已默认选中则跳过）
        protocol_select = dialog.locator(".el-select").first
        if protocol_select.count() > 0:
            current_protocol = protocol_select.inner_text()
            if "HTTPS" not in current_protocol:
                protocol_select.click()
                self.page.wait_for_timeout(500)
                https_option = self.page.locator(".el-select-dropdown__item").filter(
                    has_text="HTTPS://"
                ).first
                if https_option.count() > 0:
                    https_option.click()
                    self.page.wait_for_timeout(500)

        # 填写域名（placeholder 为 "请输入桶域名"）
        domain_input = dialog.get_by_placeholder("请输入桶域名").first
        if domain_input.count() == 0:
            # fallback: 查找回源地址区域下的第一个文本输入框
            domain_input = dialog.locator(".el-input__inner").first
        expect(domain_input).to_be_visible(timeout=10000)
        domain_input.fill(source_domain)
        self.page.wait_for_timeout(300)

        # 填写端口（关键：必须使用 bucket01 S3 URL 中的端口号）
        port_filled = False
        # 策略1：通过 .el-form-item 容器包含"端口"文本直接定位（最可靠）
        port_form_item = dialog.locator(".el-form-item").filter(has_text="端口").first
        if port_form_item.count() > 0 and port_form_item.is_visible():
            port_input = port_form_item.locator("input").first
            if port_input.count() > 0 and port_input.is_visible():
                port_input.fill("")
                port_input.fill(source_port)
                port_filled = True
                self.logger.info(f"端口已填入 (el-form-item='端口'): {source_port}")
                self.page.wait_for_timeout(300)
        # 策略2：通过 placeholder 找端口输入框（兼容 text/number）
        if not port_filled:
            for placeholder_text in ["端口", "port", "Port", "请输入端口"]:
                port_input = dialog.get_by_placeholder(placeholder_text).first
                if port_input.count() > 0 and port_input.is_visible():
                    port_input.fill("")
                    port_input.fill(source_port)
                    port_filled = True
                    self.logger.info(f"端口已填入 (placeholder='{placeholder_text}'): {source_port}")
                    self.page.wait_for_timeout(300)
                    break
        # 策略3：通过 label 文本找端口输入框
        if not port_filled:
            for label_text in ["端口", "Port"]:
                label = dialog.locator("label, span, div").filter(has_text=label_text).first
                if label.count() > 0 and label.is_visible():
                    # 找 label 同级的 input（先尝试 sibling，再尝试 parent 下的所有 input）
                    for_input = label.locator("xpath=following-sibling::input").first
                    if for_input.count() == 0:
                        for_input = label.locator("xpath=../input").first
                    if for_input.count() == 0:
                        # 在 label 的父元素下找所有可见且可填写的 input
                        parent = label.locator("xpath=..")
                        if parent.count() > 0:
                            inputs = parent.locator("input").all()
                            for inp in inputs:
                                if inp.is_visible():
                                    input_type = inp.get_attribute("type") or "text"
                                    if input_type in ("text", "number", "tel", "password"):
                                        for_input = inp
                                        break
                    if for_input and hasattr(for_input, 'count') and for_input.count() > 0 and for_input.is_visible():
                        for_input.fill("")
                        for_input.fill(source_port)
                        port_filled = True
                        self.logger.info(f"端口已填入 (label='{label_text}'): {source_port}")
                        self.page.wait_for_timeout(300)
                        break
                if port_filled:
                    break
        # 策略4：找域名输入框后面同级且值看起来像端口的输入框
        if not port_filled:
            domain_parent = domain_input.locator("xpath=../..")
            if domain_parent.count() > 0:
                # 尝试所有 input 类型（text/number/tel）
                sibling_inputs = domain_parent.locator('input')
                for i in range(sibling_inputs.count()):
                    inp = sibling_inputs.nth(i)
                    if not inp.is_visible():
                        continue
                    val = inp.input_value().strip()
                    # 如果当前值是常见默认端口(443/80/8080)或空，则替换为 source_port
                    if val in ["", "443", "80", "8080"]:
                        inp.fill("")
                        inp.fill(source_port)
                        port_filled = True
                        self.logger.info(f"端口已填入 (sibling fallback): {source_port}")
                        self.page.wait_for_timeout(300)
                        break
        # 策略5：通过 Playwright 遍历弹窗中所有可见 input，找到值为 443/80/8080 的
        if not port_filled:
            try:
                all_inputs = dialog.locator("input").all()
                for inp in all_inputs:
                    try:
                        if not inp.is_visible():
                            continue
                        input_type = inp.get_attribute("type") or "text"
                        if input_type in ("radio", "checkbox", "hidden"):
                            continue
                        val = inp.input_value().strip()
                        if val in ("443", "80", "8080"):
                            inp.fill("")
                            inp.fill(source_port)
                            port_filled = True
                            self.logger.info(f"端口已填入 (Playwright value='{val}'): {source_port}")
                            self.page.wait_for_timeout(300)
                            break
                    except Exception:
                        continue
            except Exception as e:
                self.logger.warning(f"Playwright 填端口异常: {e}")

        if not port_filled:
            self.logger.warning(f"未能定位端口输入框，端口号 {source_port} 可能未正确填入")

        # 静态路径：不输入
        # 桶名称输入
        bucket_input = dialog.get_by_placeholder("请输入桶名称").first
        if bucket_input.count() > 0:
            bucket_input.fill(source_bucket)
            self.page.wait_for_timeout(300)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_datasource_redirect_rule_create(self, source_domain, source_bucket,
                                            source_port="80"):
        """在数据回源页面新建重定向回源规则。

        按照需求配置：
        - 回源类型：重定向回源
        - 重定向码：默认 307
        - 源站类型：公有类型
        - HTTP 状态码：默认 404
        - 对象名称前缀：不配置
        - 添加前后缀：不开启
        - 替换前缀：不配置
        - 携带请求字符串：不开启
        - 回源地址：路径样式
        - 路径样式主站：协议 HTTP

        Args:
            source_domain: 源站域名
            source_bucket: 源站桶名称
            source_port: 源站端口，默认 80（HTTP 协议）
        """
        # 点击新建
        self.page.get_by_text("新建", exact=True).first.click()
        self.page.wait_for_timeout(1500)

        # 获取弹窗
        dialog = self._find_visible_dialog("规则")
        assert dialog is not None, "未找到可见的规则弹窗"
        expect(dialog).to_be_visible(timeout=10000)

        # 回源类型：重定向回源
        redirect_radio = dialog.get_by_text("重定向回源", exact=True)
        if redirect_radio.count() > 0:
            redirect_radio.click()
            self.page.wait_for_timeout(500)

        # 重定向码：默认 307（disabled，无需操作）
        # 源站类型：公有类型（默认 false）
        public_radio = dialog.get_by_text("公有类型", exact=True)
        if public_radio.count() > 0:
            public_radio.click()
            self.page.wait_for_timeout(500)

        # HTTP 状态码：默认 404，disabled 状态无需操作
        # 对象名称前缀：不配置（留空）
        # 添加前后缀：不开启（默认 false）
        # 替换前缀：不配置（留空）
        # 携带请求字符串：不开启（默认 false）

        # 回源地址类型：路径样式
        path_style_radio = dialog.get_by_text("路径样式", exact=True)
        if path_style_radio.count() > 0:
            path_style_radio.click()
            self.page.wait_for_timeout(1000)

        # 路径样式主站配置
        # 协议选择 HTTP
        protocol_select = dialog.locator(".el-select").first
        if protocol_select.count() > 0:
            current_protocol = protocol_select.inner_text()
            if "HTTP" not in current_protocol:
                protocol_select.click()
                self.page.wait_for_timeout(500)
                http_option = self.page.locator(".el-select-dropdown__item").filter(
                    has_text="HTTP://"
                ).first
                if http_option.count() > 0:
                    http_option.click()
                    self.page.wait_for_timeout(500)

        # 填写域名
        domain_input = dialog.get_by_placeholder("请输入桶域名").first
        if domain_input.count() == 0:
            domain_input = dialog.locator(".el-input__inner").first
        expect(domain_input).to_be_visible(timeout=10000)
        domain_input.fill(source_domain)
        self.page.wait_for_timeout(300)

        # 填写端口（关键：必须使用 bucket01 S3 URL 中的端口号）
        port_filled = False
        try:
            # 策略1：通过 el-form-item='端口' 精确定位
            port_form_item = dialog.locator(".el-form-item").filter(
                has_text=re.compile(r"端口|Port")
            ).first
            if port_form_item.count() > 0 and port_form_item.is_visible():
                port_input = port_form_item.locator("input").first
                if port_input.count() > 0 and port_input.is_visible():
                    port_input.fill("")
                    port_input.fill(source_port)
                    port_filled = True
                    self.logger.info(f"端口已填入 (el-form-item='端口'): {source_port}")
                    self.page.wait_for_timeout(300)
            # 策略2：通过 placeholder 找端口输入框（兼容 text/number）
            if not port_filled:
                for placeholder_text in ["端口", "port", "Port", "请输入端口"]:
                    port_input = dialog.get_by_placeholder(placeholder_text).first
                    if port_input.count() > 0 and port_input.is_visible():
                        port_input.fill("")
                        port_input.fill(source_port)
                        port_filled = True
                        self.logger.info(f"端口已填入 (placeholder='{placeholder_text}'): {source_port}")
                        self.page.wait_for_timeout(300)
                        break
            # 策略3：通过 label 文本找端口输入框
            if not port_filled:
                for label_text in ["端口", "port", "Port"]:
                    try:
                        labels = dialog.locator("label").all()
                        for lbl in labels:
                            try:
                                if label_text in (lbl.text_content() or ""):
                                    for_id = lbl.get_attribute("for")
                                    if for_id:
                                        for_input = dialog.locator(f"#{for_id}").first
                                    else:
                                        parent = lbl.locator("xpath=..")
                                        for_input = parent.locator("input").first
                                    if for_input and hasattr(for_input, 'count') and for_input.count() > 0 and for_input.is_visible():
                                        for_input.fill("")
                                        for_input.fill(source_port)
                                        port_filled = True
                                        self.logger.info(f"端口已填入 (label='{label_text}'): {source_port}")
                                        self.page.wait_for_timeout(300)
                                        break
                                if port_filled:
                                    break
                            except Exception:
                                continue
                        if port_filled:
                            break
                    except Exception:
                        continue
            # 策略4：通过 domain_input 的兄弟节点查找
            if not port_filled and domain_input.count() > 0:
                try:
                    parent_form = domain_input.locator("xpath=ancestor::div[contains(@class,'el-form-item')]")
                    if parent_form.count() > 0:
                        next_items = parent_form.locator("xpath=following-sibling::div[contains(@class,'el-form-item')]")
                        for i in range(min(3, next_items.count())):
                            inp = next_items.nth(i).locator("input").first
                            if not inp.is_visible():
                                continue
                            val = inp.input_value().strip()
                            if val in ["", "443", "80", "8080"]:
                                inp.fill("")
                                inp.fill(source_port)
                                port_filled = True
                                self.logger.info(f"端口已填入 (sibling fallback): {source_port}")
                                self.page.wait_for_timeout(300)
                                break
                except Exception as e:
                    self.logger.debug(f"兄弟节点查找端口输入框失败: {e}")
            # 策略5：通过 Playwright 遍历弹窗中所有可见 input，找到值为 443/80/8080 的
            if not port_filled:
                try:
                    all_inputs = dialog.locator("input").all()
                    for inp in all_inputs:
                        try:
                            if not inp.is_visible():
                                continue
                            val = inp.input_value().strip()
                            if val in ("443", "80", "8080"):
                                inp.fill("")
                                inp.fill(source_port)
                                port_filled = True
                                self.logger.info(f"端口已填入 (Playwright value='{val}'): {source_port}")
                                self.page.wait_for_timeout(300)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    self.logger.warning(f"Playwright 填端口异常: {e}")
        except Exception as e:
            self.logger.warning(f"端口填写过程异常: {e}")

        if not port_filled:
            self.logger.warning(f"未能定位端口输入框，端口号 {source_port} 可能未正确填入")

        # 静态路径：不输入
        # 桶名称输入
        bucket_input = dialog.get_by_placeholder("请输入桶名称").first
        if bucket_input.count() > 0:
            bucket_input.fill(source_bucket)
            self.page.wait_for_timeout(300)

        # 点击确定
        dialog.get_by_text("确定", exact=True).first.click()
        self.page.wait_for_timeout(3000)
        self.wait_for_page_ready()

    def obs_datasource_rule_assert_contain(self, rule_type="镜像回源",
                                            source_type="公有类型"):
        """断言数据回源列表中包含指定规则。

        Args:
            rule_type: 回源类型，默认"镜像回源"
            source_type: 源站类型，默认"公有类型"
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=rule_type)
        expect(rows.first).to_be_visible(timeout=10000)

    def obs_datasource_rule_delete(self, rule_type="镜像回源"):
        """删除指定类型的数据回源规则。

        Args:
            rule_type: 回源类型，默认"镜像回源"
        """
        table = self.page.locator(
            ".cl-table-body, .el-table__body-wrapper"
        ).first
        rows = table.locator("tr").filter(has_text=rule_type)
        if rows.count() == 0:
            return

        # 点击行内的删除操作
        delete_btn = rows.first.locator("button, a, .el-link").filter(
            has_text="删除"
        ).first
        if delete_btn.count() > 0:
            delete_btn.click()
            self.page.wait_for_timeout(2000)

            confirm_dialog = self.page.locator(
                ".cv-dialog, .el-dialog"
            ).filter(has_text="删除").first
            if confirm_dialog.count() > 0:
                confirm_dialog.get_by_text("确定", exact=True).first.click()
                self.page.wait_for_timeout(3000)
                self.wait_for_page_ready()

    def obs_bucket_endpoint_url_extract(self, endpoint_text):
        """从 EndPoint 文本中提取域名和端口。

        处理格式如：
        - https://obs.xxx.com:20480
        - https://obs.xxx.com:20480 (vpc-name)
        - obs.xxx.com:20480

        Args:
            endpoint_text: EndPoint 原始文本

        Returns:
            tuple: (domain, port, protocol)
        """
        text = endpoint_text.strip()
        # 去掉括号内容
        text = re.sub(r'\s*\([^)]*\)', '', text)

        protocol = "https"
        if text.startswith("http://"):
            protocol = "http"
            text = text[7:]
        elif text.startswith("https://"):
            protocol = "https"
            text = text[8:]

        # 分割域名和端口
        if ":" in text:
            parts = text.rsplit(":", 1)
            domain = parts[0].strip()
            port = parts[1].strip()
        else:
            domain = text
            port = "443" if protocol == "https" else "80"

        return domain, port, protocol

