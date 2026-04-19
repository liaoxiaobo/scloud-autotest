import re
import time
import pytest
from playwright.sync_api import expect
from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger


class OpsPage(BasePage):

    @submenu("平台网络")
    def mfip_create(self, project: str, network: str, ip: str, exact=True):
        """创建 MFIP"""
        self.btn_create.click()
        self.get_by_placeholder("请选择项目").click()
        self.get_by_title(project).click()
        # 选择项目后会触发接口请求重绘网络列表，此处等待接口请求完成
        self.page.wait_for_load_state("networkidle")

        # 等待接口返回并渲染网络下拉列表
        self.get_by_placeholder("请选择网络").click()
        # 使用正则表达式精确匹配网络名称，并限制在当前可见的下拉框中，避免全局冲突
        dropdown = self.page.locator(".el-select-dropdown:visible")
        target_item = dropdown.get_by_role("listitem").filter(has_text=re.compile(rf"^{re.escape(network)}$"))
        # 接口返回后页面重绘可能存在延迟，导致短暂出现两个同名项，等待直到只有一个匹配项
        expect(target_item).to_have_count(1)
        target_item.click()
        self.get_by_placeholder("请选择端口").click()
        self.get_by_text(ip, exact=exact).click()
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