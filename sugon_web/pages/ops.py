import re
import time
import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError, expect
from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger


class OpsPage(BasePage):
    service_name = "基础设施"

    def bind_mfip(self, ip: str, network="Autotest", project="默认项目"):
        """绑定 MFIP 并返回管理 IP。"""
        self.goto_service("基础设施")
        self.mfip_create(project, network, ip)
        self.assert_popup_success("执行成功")
        self.mfip_search(ip)
        return self.get_row_data(ip).get("管理IP地址")

    def _select_dropdown_and_wait_api(
        self,
        placeholder: str,
        value: str,
        locator_type: str = "listitem",
        api_url_pattern: str | None = None,
        timeout: int = 5000,
    ):
        """点击下拉框选择选项，并等待指定 API 接口返回。

        Args:
            placeholder: 下拉框的 placeholder 文本
            value: 需要选中的精确文本
            locator_type: 选项定位器类型，"title" 使用 get_by_title，"listitem" 使用下拉框内 listitem
            api_url_pattern: 需要等待响应的 API URL 包含的模式，None 表示不等待
            timeout: 接口等待超时时间（毫秒）
        """
        self.get_by_placeholder(placeholder).click()
        dropdown = self.page.locator(".el-select-dropdown:visible")

        if locator_type == "title":
            target_item = self.get_by_title(value)
        else:
            target_item = dropdown.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(value)}$"))
            expect(target_item).to_have_count(1, timeout=timeout)
        if api_url_pattern:
            try:
                with self.page.expect_response(
                    lambda response: (
                        response.request.method == "GET"
                        and api_url_pattern in response.url
                        and response.status == 200
                    ),
                    timeout=timeout
                ):
                    self.page.wait_for_timeout(1000)
                    target_item.click()
                logger.info(f"选择 '{value}' 后已捕获接口: {api_url_pattern}")
            except PlaywrightTimeoutError:
                logger.warning(f"选择 '{value}' 后未捕获接口 {api_url_pattern}")
                target_item.click()
        else:
            self.page.wait_for_timeout(2000)
            target_item.click()

    @submenu("平台网络")
    def mfip_create(self, project: str, network: str, ip: str, exact: bool = True):
        """创建 MFIP

        Args:
            project: 项目名称
            network: 网络名称
            ip: 管理IP地址
            exact: 是否精确匹配IP文本
        """
        self.btn_create.click()
        self._select_dropdown_and_wait_api("请选择项目", project, "title", api_url_pattern="/api/ops/vpc/networks")
        self._select_dropdown_and_wait_api("请选择网络", network, api_url_pattern="/ports")

        # 选择端口
        self.get_by_placeholder("请选择端口").click()
        self.page.wait_for_timeout(500)
        dropdown = self.page.locator(".el-select-dropdown:visible")
        option = dropdown.get_by_text(ip, exact=exact).first
        option.click()
        self.get_by_label("新建管理IP").get_by_text("确定").click()

    @submenu("平台网络")
    def mfip_delete(self, ip: str):
        """删除 MFIP"""
        self.click_action(ip, "删除")
        self.dialog_confirm.click()


    @submenu("平台网络")
    def mfip_search(self, ip: str):
        """查询 MFIP"""
        self.get_by_role("textbox", name="请选择").nth(1).click()
        self.get_by_text("固定IP", exact=True).click()
        self.search(ip)

    @submenu("物理机设备")
    @submenu("裸磁盘")
    def _check_disK(self):
        """检查环境是否有裸磁盘"""
        return self.get_by_text("没有查询到符合条件的记录").is_hidden()

    @submenu("物理机设备")
    @submenu("裸磁盘")
    def search_disk(self, search_type: str, search_value: str):
        """搜索裸磁盘"""
        self.get_by_placeholder("请选择").nth(1).click()
        # self.locator("span").filter(has_text=search_type).click()
        self.locator("li").filter(has_text=search_type).click()
        # self.get_by_placeholder("请输入搜索内容").fill(search_value)
        self.get_by_placeholder(f"搜索（{search_type}）").fill(search_value)
        self.get_by_text("搜索", exact=True).click()

    @submenu("物理机设备")
    @submenu("裸磁盘")
    def enable_disk_(self, node: str):
        """启用虚机所在节点的裸磁盘

        Args:
            node: 裸磁盘所在节点名称
        """
        logger.info(f"启用裸磁盘: {node}节点的裸磁盘")

        # 获取磁盘状态
        try:
            target_row = self.get_rows_by_text(node)
        except:
            pytest.skip(f"{node}没有查询到可用的裸磁盘")

        result = self.get_row_data_by_locator(target_row)

        self.logger.info(f"处理后的数据: {result}")
        status, _disk_name, _disk_size = result.get("状态"), result.get("名称"), result.get("容量")
        logger.info(f"磁盘状态: {status}, 磁盘名称: {_disk_name}, 磁盘容量: {_disk_size}")
        if status == "禁用":
            # 定位磁盘行并点击操作按钮
            self.click_action(_disk_name, "启用")
            # 确认启用
            self.dialog_confirm.click()
            logger.info(f"{node} 的裸磁盘启用请求已提交")
            return _disk_name, _disk_size
        elif status == "启用":
            logger.info(f"{node} 的裸磁盘已处于 {status} 状态")
            return _disk_name, _disk_size
        else:
            logger.info(f"{node} 的裸磁盘处于 {status} 状态")
            pytest.skip(f"{node} 的裸磁盘处于 {status} 状态")

    def enable_disk(self, search_type: str, search_value: str):
        """通过名称启用裸磁盘"""
        self.search_disk(search_type, search_value)
        names = self.get_column_data("名称")
        # data = ops_page.get_row_data("/dev/sdk")
        status = self.get_column_data("状态")
        if "禁用" in status:
            for name, sta in zip(names, status):
                if sta == "禁用":
                    self.click_action(name, "启用")
                    self.dialog_confirm.click()
                    self.assert_popup_success("请求成功！")
                    data = self.get_row_data(name)
                    _disk_size = data.get("容量")
                    self.logger.info(f"已启用第一个状态为禁用的磁盘: {name}")
                    return name, _disk_size
        else:
            pytest.skip("没有找到可启用的裸磁盘")

    # @submenu("物理机设备")
    @submenu("裸磁盘")
    def disable_disk(self, ndoe: str):
        """禁用裸磁盘"""
        self.click_action(ndoe, "禁用")
        self.dialog_confirm.click()

    @submenu("存储池")
    def create_storage_pool(self, name: str, device_type: str, storage_type: str = "本地磁盘"):
        """创建存储池
        Args:
            purpose: 存储池用途, 默认为"数据存储"
            name: 存储池名称
            device_type: 设备类型, 如"DISK-SSD-894.3G"
            storage_type: 存储类型, 默认为"本地磁盘"
        """

        # 点击新建按钮
        self.btn_create.click()

        # 取消选择存储类别 - 系统存储、镜像存储
        sys_loc = self.locator("label").filter(has_text="系统存储").locator("span").nth(1)
        if sys_loc.is_checked():
            sys_loc.click()
        im_loc = self.locator("label").filter(has_text="镜像存储").locator("span").nth(1)
        if im_loc.is_checked():
            im_loc.click()

        # 选择存储使用 - 数据存储
        sto_loc = self.locator("label").filter(has_text="数据存储").locator("span").nth(1)
        if not sto_loc.is_checked():
            sto_loc.click()

        # 填写名称
        self.get_by_placeholder("请输入名称").fill(name)

        # 填写别名
        self.get_by_placeholder("请输入别名").fill(name)

        # 选择类型
        self.locator("form div").filter(has_text="类型Xbd XStor Ceph 本地存储 Zbs").get_by_placeholder("请选择").click()
        self.locator("li").filter(has_text=storage_type).click()

        # 选择设备类型
        self.get_by_placeholder("请选择类型").click()
        self.locator("li").filter(has_text=device_type).click()
        time.sleep(1)

        # 填写数量
        loc = self.locator(".el-input-number__increase")
        logger.info(f"数量输入控件的class: {loc.get_attribute('class')}")
        if "is-disabled" in loc.get_attribute("class"):
            pytest.skip("数量输入控件被禁用，跳过测试")
        else:
            loc.click()
        # 确认创建
        self.get_by_label("新建存储池").locator("div").filter(has_text="确定").nth(3).click()

        logger.info(f"创建请求已提交: 名称={name}, 类型={storage_type}, 设备类型={device_type}")

    @submenu("存储池")
    def sync_storage_pool_config(self):
        """同步存储池配置"""
        logger.info("同步存储池配置")

        # 点击同步配置
        self.get_by_text("同步配置").nth(1).click()

        # 确认同步
        self.dialog_confirm.click()

        logger.info("存储池配置同步请求已提交")

    @submenu("存储池")
    def sync_pool_size(self, name: str):
        """同步存储池配置"""

        self.click_action(name, "同步容量")
        # 确认同步
        self.dialog_confirm.click()

        logger.info("存储池容量同步请求已提交")

    def storage_pool_operation(self, name: str, operation: str):
        """存储池操作
        Args:
            name: 存储池名称
            operation: 操作类型，如"启用"、"禁用"
        """

        self.click_action(name, operation)
        self.dialog_confirm.click()
        self.assert_popup_success("请求成功！")

    @submenu("存储池")
    def delete_storage_pool(self, name: str):
        """删除存储池"""
        logger.info(f"删除{name}存储池")

        # 点击存储池操作按钮，点击删除
        self.click_action(name, "删除")

        # 确认删除
        self.dialog_confirm.click()

        logger.info(f"{name}存储池删除请求已提交")

    # ---- switch group ----

    def _goto_switch_group(self):
        base = self.page.url.split("#")[0].rstrip("/")
        self.page.goto(base + "/#/index")
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)
        try:
            self.page.locator("text=基础设施").first.click()
        except Exception:
            self.page.evaluate("() => { document.evaluate(\"//*[contains(text(), '基础设施')]\", document).iterateNext()?.click(); }")
        self.page.wait_for_timeout(1500)
        try:
            self.page.locator("text=区域资源").first.click()
        except Exception:
            self.page.evaluate("() => { document.evaluate(\"//*[contains(text(), '区域资源')]\", document).iterateNext()?.click(); }")
        self.page.wait_for_timeout(1500)
        try:
            self.page.locator("text=交换机组").first.click()
        except Exception:
            self.page.evaluate("() => { document.evaluate(\"//*[contains(text(), '交换机组')]\", document).iterateNext()?.click(); }")
        self.page.wait_for_load_state("networkidle")
        self.page.wait_for_timeout(2000)

    def _sg_dropdown_action(self, name, action):
        self.page.wait_for_timeout(1000)
        row = None
        for r in self.page.locator("tbody tr").all():
            try:
                txt = r.text_content(timeout=3000)
                if txt and name in txt:
                    row = r
                    break
            except Exception:
                continue
        if not row:
            raise Exception(f"未找到资源行: {name}")
        # 点击"更多"展开下拉菜单
        more_btn = row.locator("button, .cloud-button-btn, a, span").filter(has_text=re.compile(r"更多|⋯|⋮"))
        if more_btn.count() == 0:
            more_btn = row.locator("button, .cloud-button-btn, a, span").filter(has_text="更多")
        if more_btn.count() > 0:
            try:
                more_btn.first.click()
                self.page.wait_for_timeout(800)
            except Exception:
                pass
        # 尝试标准点击（要求元素可见可交互）
        items = row.locator(".cloud-table-dropdown-item").filter(has_text=action)
        if items.count() > 0:
            try:
                items.first.wait_for(state="visible", timeout=3000)
                items.first.click()
                return
            except Exception:
                pass
        # 回退：JavaScript 移除隐藏类并点击
        result = self.page.evaluate(
            """([rowText, actionText]) => {
                for (const r of document.querySelectorAll('tbody tr')) {
                    if (r.textContent.includes(rowText)) {
                        for (const i of r.querySelectorAll('.cloud-table-dropdown-item')) {
                            i.classList.remove('cloud-table-dropdown-item-btn-hide');
                            i.style.display = 'block';
                            i.style.visibility = 'visible';
                        }
                        for (const i of r.querySelectorAll('.cloud-table-dropdown-item')) {
                            if (i.textContent.trim() === actionText) {
                                i.click();
                                return true;
                            }
                        }
                    }
                }
                return false;
            }""", [name, action])
        if not result:
            raise Exception(f"未找到操作 '{action}' 的入口，资源: {name}")

    def _confirm_sugon_dialog(self):
        for dlg in self.page.locator(".sugon-dialog").all():
            if dlg.is_visible():
                dlg.locator("button, .cloud-button-btn").filter(has_text="确定").first.click()
                return
        try:
            self.dialog_confirm.click()
        except Exception:
            self.page.locator("button, .cloud-button-btn").filter(has_text="确定").last.click()

    def switch_group_create(self, name):
        self._goto_switch_group()
        self.page.locator(".cloud-button--primary, .cloud-button-btn").filter(has_text="新建").first.click()
        self.page.locator('[role="dialog"]').filter(has_text="新建交换机组").last.locator("input").first.fill(name)
        self._confirm_sugon_dialog()

    def switch_group_bind_node(self, name, node_name):
        self._goto_switch_group()
        self._sg_dropdown_action(name, "绑定物理机")
        d = self.page.locator('[role="dialog"]').filter(has_text="绑定物理机").last
        for attempt in range(5):
            d.locator("input").first.click()
            self.page.wait_for_timeout(800)
            opts = self.page.locator(".el-select-dropdown:visible li")
            if opts.count() == 0:
                self.page.keyboard.press("Escape")
                if attempt < 4:
                    wait_sec = 30 if attempt < 2 else 60
                    logger.info(f"无可用节点，等待 {wait_sec}s 后重试 (attempt {attempt + 1}/5)...")
                    time.sleep(wait_sec)
                    self._goto_switch_group()
                    self._sg_dropdown_action(name, "绑定物理机")
                    d = self.page.locator('[role="dialog"]').filter(has_text="绑定物理机").last
                    continue
                raise Exception("无可用节点")
            opt = opts.filter(has_text=node_name)
            if opt.count() > 0:
                opt.first.click()
            else:
                first_opt = opts.first
                first_text = first_opt.text_content().strip()
                logger.info(f"首选节点 '{node_name}' 不可用，使用第一个可用节点: {first_text}")
                first_opt.click()
            break
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(300)
        self._confirm_sugon_dialog()

    def switch_group_unbind_node(self, name, node_name):
        self._goto_switch_group()
        self._sg_dropdown_action(name, "解绑物理机")
        d = self.page.locator('[role="dialog"]').filter(has_text="解绑物理机").last
        d.locator("input").first.click()
        self.page.wait_for_timeout(500)
        opts = self.page.locator(".el-select-dropdown:visible li")
        matched = opts.filter(has_text=node_name)
        if matched.count() > 0:
            matched.first.click()
        else:
            # 物理机列可能是多个节点名拼接（如 master02.cloud.localmaster01.cloud.local）
            # 提取第一个有效节点名进行匹配，否则回退到第一个可用选项
            extracted = None
            for opt in opts.all():
                txt = opt.text_content(timeout=3000).strip()
                if txt and txt in node_name:
                    extracted = txt
                    break
            if extracted:
                opts.filter(has_text=extracted).first.click()
            elif opts.count() > 0:
                first_text = opts.first.text_content(timeout=3000).strip()
                logger.info(f"未找到匹配 '{node_name}' 的选项，回退选择第一个: {first_text}")
                opts.first.click()
            else:
                raise Exception(f"解绑对话框无可用节点选项")
        # 多选下拉框点击选项后不会自动关闭，需要按 Escape 关闭后再点确定
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        d.locator("button, .cloud-button-btn").filter(has_text="确定").first.click()

    def switch_group_delete(self, name):
        self._goto_switch_group()
        self._sg_dropdown_action(name, "删除")
        self._confirm_sugon_dialog()
        self.page.wait_for_timeout(2000)

    def clean_all_switch_groups(self):
        self._goto_switch_group()
        self.page.wait_for_timeout(1000)
        names = []
        for r in self.page.locator("tbody tr").all():
            cells = r.locator("td")
            if cells.count() > 1:
                try:
                    n = cells.nth(1).text_content(timeout=3000).strip()
                except Exception:
                    continue
                # 只清理测试创建的交换机组，避免误删环境资源
                if n and n.startswith("test-") and len(n) < 100 and n not in names:
                    names.append(n)
        for n in names:
            # 循环解绑，直到物理机列为空（可能绑定多个节点）
            for unbind_attempt in range(5):
                self._goto_switch_group()
                try:
                    rd = self.get_row_data(n)
                    pm = rd.get("物理机", "")
                except Exception:
                    pm = ""
                if not pm or pm == "--" or pm == "—":
                    break
                try:
                    self.switch_group_unbind_node(n, pm)
                    logger.info(f"等待120s解绑完成... (attempt {unbind_attempt + 1})")
                    time.sleep(120)
                except Exception as e:
                    logger.warning(f"解绑失败: {e}")
                    break
            # 验证解绑结果
            self._goto_switch_group()
            try:
                rd = self.get_row_data(n)
                pm_after = rd.get("物理机", "")
                if pm_after and pm_after != "--" and pm_after != "—":
                    logger.warning(f"解绑后物理机仍为 {pm_after}，可能解绑未生效")
                else:
                    logger.info(f"解绑验证成功，物理机变为: {pm_after}")
            except Exception:
                pass
            try:
                self.switch_group_delete(n)
                self.page.wait_for_timeout(1500)
            except Exception as e:
                logger.warning(f"删除交换机组失败: {e}")
