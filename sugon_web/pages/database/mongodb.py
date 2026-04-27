import re
import pytest
from time import sleep

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util
from sugon_web.utils.logger import logger


class MongoDBPage(BasePage):
    """MongoDB实例管理页面对象"""

    @submenu("实例管理")
    def create_instance(self, name: str, instance_type: str = "单机", version: str = "5.0",
                        password: str = "Admin1234#sugon", network: str = "Autotest",
                        subnet: str = "Autotest:10.", disk_type: str = None, disk_size: int = 20):
        """
        创建MongoDB实例
        :param name: 实例名称
        :param instance_type: 实例类型（单机/副本集/分片集群）
        :param version: 版本
        :param password: root管理员密码 (需包含大小写字母、数字、特殊字符!#$%^&*()_+=中的三种)
        :param network: 网络
        :param subnet: 子网
        :param disk_type: 磁盘类型
        :param disk_size: 磁盘大小
        """
        self.btn_create.click()

        # --- 类型设置 ---
        self.get_by_role("radio", name=instance_type).click()
        # 选择类型后，规格等选项可能是动态加载的，稍作等待
        sleep(2)
        
        # 基本设置 - 名称
        # 使用正则表达式匹配"名称"，避免匹配到其他包含"名称"的文本
        self.locator("div").filter(has_text=re.compile(r"^名称$")).get_by_role("textbox").fill(name)

        # 项目选择
        db_util.project_dropdown(self).click()
        db_util.project_autotest(self).click()

        # 密码
        self.get_by_placeholder("请输入root管理员用户密码").fill(password)
        db_util.input_confirm_password(self).fill(password)

        # --- 网络设置 ---
        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        # --- 存储设置 ---
        selected_disk_type = disk_type if disk_type else self.volume_type
        db_util.select_disk_type_like_doris(self, selected_disk_type)

        # 磁盘大小 
        # 不同的集群类型和录制场景下定位可能不同
        try:
            # 兼容单机/副本集 (数据盘大小) 和 分片集群 (Shard存储空间(GiB))
            storage_label = "Shard存储空间" if instance_type == "分片集群" else "数据盘大小"
            self.locator(".el-form-item").filter(has_text=re.compile(storage_label)).get_by_role("spinbutton").fill(str(disk_size))
        except:
            # 兜底：直接通过 el-input-number 查找
            self.locator(".el-input-number").get_by_role("spinbutton").first.fill(str(disk_size))

        # --- 规格选择 ---
        if instance_type == "分片集群":
            # 分片集群包含：Mongos规格、Shard规格、ConfigServer规格
            labels = ["Mongos规格", "Shard规格", "ConfigServer规格"]
            for label in labels:
                # 定位到对应表项容器，选择第一个规格 (通常是2核/4GiB)
                item = self.locator(".el-form-item").filter(has_text=re.compile(label))
                # 优先寻找 el-radio-button (方块样式的规格) 或普通的 el-radio
                group = item.locator(".el-radio-button, .el-radio").first
                group.click()
        else:
            # 单机或副本集，选择特定规格: mongodb.d6 mongodb.d6.large 2核 4GiB
            # 找到包含特定规格文本的行并点击对应的单选框
            self.page.locator("tr").filter(has_text=re.compile(r"mongodb\.d6\.large")).get_by_role("radio").click()

        # --- 确认创建 ---
        sleep(2)
        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name):
        """
        删除MongoDB实例
        :param name: 实例名称
        """
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_instances(self, names: list):
        """
        批量删除MongoDB实例
        :param names: 实例名称列表
        """
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()

        self.get_by_text("批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name: str, new_name: str):
        """
        修改MongoDB实例名称
        :param old_name: 旧实例名称
        :param new_name: 新实例名称
        """
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称").get_by_role("textbox")
        dialog.click()
        dialog.fill(new_name)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_root_password(self, name: str, new_password: str):
        """
        修改MongoDB实例的管理员密码
        :param name: 实例名称
        :param new_password: 新密码
        """
        self.click_action(name, "修改root密码")
        dialog = self.get_by_role("dialog")
        pwd_input = dialog.locator("div").filter(has_text=re.compile(r"^新密码$")).get_by_role("textbox")
        pwd_input.wait_for(state="visible", timeout=5000)
        pwd_input.fill(new_password)
        confirm_pwd_input = dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox")
        confirm_pwd_input.wait_for(state="visible", timeout=5000)
        confirm_pwd_input.fill(new_password)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_disk_size(self, name: str, new_size: int):
        """
        修改MongoDB节点磁盘大小
        :param name: 实例名称
        :param new_size: 新磁盘大小
        """
        node_name = f"{name}-0"
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "修改云硬盘大小")

        dialog = self.get_by_role("dialog")
        spin_button = dialog.get_by_role("spinbutton")
        spin_button.wait_for(state="visible", timeout=5000)
        spin_button.fill(str(new_size))
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_specification(self, name: str, specification_name: str):
        """
        修改MongoDB实例规格
        :param name: 实例名称
        :param specification_name: 新规格名称
        """
        node_name = f"{name}-0"
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "修改规格")
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def node_ip_binding(self, instance_name: str, node_name: str, network: str = None):
        """
        为MongoDB实例节点绑定弹性IP
        :param instance_name: 实例名称
        :param node_name: 节点名称
        :param network: 网络名称 (仅绑定时需要)
        :return: 绑定的IP地址
        """
        self.goto_detail_page(instance_name, node_name)
        self.click_action(node_name, "绑定公网IP")

        # 使用更精确的dialog定位
        dialog = self.get_by_label("绑定公网IP", exact=True)
        dialog.get_by_placeholder("请选择").click()
        self.get_by_text(network).click()

        # 选择第一个状态为"关闭"的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.dialog_confirm.click()

        return ip_address

    @submenu("实例管理")
    def node_ip_unbinding(self, instance_name: str, node_name: str):
        """
        为MongoDB节点解绑弹性IP
        :param instance_name: 实例名称
        :param node_name: 节点名称
        """
        self.goto_detail_page(instance_name, node_name)
        self.click_action(node_name, "解绑公网IP")
        self.get_by_role("dialog").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_secondary_node(self, name: str):
        """
        为MongoDB实例添加备节点
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_text("新建备节点").first.click()
        self.get_by_label("新建备节点").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_readonly_node(self, name: str):
        """
        为MongoDB实例添加只读节点
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_text("新建只读节点").first.click()
        self.get_by_label("新建只读节点").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_mongos_node(self, name: str):
        """
        为MongoDB分片集群添加Mongos节点
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_text("添加Mongos节点").first.click()
        self.get_by_label("添加Mongos节点").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def adjust_shards(self, name: str, shard_count: int = 3):
        """
        为MongoDB分片集群调整分片数量
        :param name: 实例名称
        :param shard_count: 分片数量
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_text("调整分片").first.click()
        dialog = self.get_by_label("调整分片")
        # 假设是一个 spinbutton 或带有特定 label 的单选/输入
        dialog.get_by_role("spinbutton").fill(str(shard_count))
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        """
        为MongoDB实例添加白名单
        :param name: 实例名称
        :param ip_address: IP地址或CIDR
        """
        self.locator(f"#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        self.get_by_text("添加", exact=True).click()
        self.get_by_placeholder("例：10.0.12.0/").fill(ip_address)
        self.get_by_label("添加白名单").get_by_text("确定").click()

    @submenu("实例管理")
    def delete_whitelist(self, name: str, ip_address: str):
        """
        为MongoDB实例删除单个白名单
        :param name: 实例名称
        :param ip_address: IP地址或CIDR
        """
        self.locator(f"#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        self.locator("span").filter(has_text=ip_address).locator("i").click()
        self.get_by_label("移除").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def batch_delete_whitelist(self, name: str, ip_addresses: list):
        """
        为MongoDB实例批量删除白名单
        :param name: 实例名称
        :param ip_addresses: IP地址或CIDR的列表
        """
        self.locator(f"#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        sleep(2)
        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        dialog = self.get_by_label("删除白名单")
        dialog.get_by_placeholder("请选择要删除的白名单").click()
        for ip in ip_addresses:
            self.page.locator("li", has_text=ip).click()
        dialog.locator(".el-dialog__header").click()
        self.page.locator("div.el-select-dropdown.label-select:visible").wait_for(state="hidden", timeout=5000)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def reset_whitelist(self, name: str):
        """
        为MongoDB实例重置白名单
        :param name: 实例名称
        """
        self.locator(f"#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def edit_instance_parameter(self, name: str, param_name: str, param_value: str):
        """
        编辑实例的参数值并应用
        :param name: 实例名称
        :param param_name: 参数名称
        :param param_value: 参数新值
        """
        self.locator(f"#cloud-container-content").get_by_text(name).first.click()
        sleep(3)
        self.get_by_role("tab", name="参数设置").click()

        # 使用更稳健的行定位方式
        self.page.locator("tr").filter(has_text=param_name).get_by_text("编辑").last.click()
        
        # 在弹窗中修改值
        dialog = self.get_by_label("编辑参数")
        spinbutton = dialog.get_by_role("spinbutton")
        spinbutton.click()
        spinbutton.fill(param_value)
        dialog.get_by_text("确定").click()
        # 应用更改
        self.get_by_text("应用", exact=True).click()
    @submenu("实例管理")
    def change_user_password(self, name: str, user_name: str, new_password: str):
        """
        修改用户密码
        :param name: 实例名称
        :param user_name: 用户名
        :param new_password: 新密码
        """
        self.locator(f"#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
        self.click_action(user_name, "修改用户")
        dialog = self.get_by_label("修改用户")
        dialog.locator("input[type=\"password\"]").fill(new_password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(new_password)
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def delete_user(self, name: str, user_name: str):
        """
        在指定实例下删除用户
        :param name: 实例名称
        :param user_name: 用户名
        """
        self.locator(f"#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
        self.click_action(user_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def enable_error_log(self, name: str):
        """
        为MongoDB实例开启错误日志
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="错误日志").click()
        self.get_by_text("立即开启").click()
        self.get_by_label("开启错误日志").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def disable_error_log(self, name: str):
        """
        为MongoDB实例关闭错误日志
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="错误日志").click()
        self.get_by_text("服务设置").first.click()
        self.get_by_role("switch").locator("span").click()
        self.get_by_label("服务设置").get_by_text("确定").click()

    @submenu("实例管理")
    def export_instance_parameters(self, name: str):
        """
        导出实例的参数
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(3)
        self.get_by_role("tab", name="参数设置").click()
        sleep(3)
        self.get_by_text("导出", exact=True).click()

    @submenu("实例管理")
    def mongodb_hot_migration(self, name, node_name, bandwidth="50%", cpu_auto=True):
        """
        MongoDB节点热迁移
        :param name: 实例名称
        :param node_name: 节点名称 (如 f"{name}-0")
        :param bandwidth: 迁移速率 (25%, 50%, 75%, 全速)
        :param cpu_auto: 是否开启CPU自动收敛
        """
        self.goto_detail_page(name, node_name)
        self.click_action(node_name, "热迁移")
        sleep(2)

        # 选择目标物理机
        # 定位目标物理机选择框并点击
        self.locator("form div").filter(has_text="目标物理机").get_by_placeholder("请选择").click()
        sleep(1)

        # 获取下拉列表中的所有选项
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        options = dropdown.locator("li.el-select-dropdown__item")

        checked_host = None
        # 尝试选择第一个可用的
        count = options.count()
        for i in range(count):
            opt = options.nth(i)
            if "is-disabled" not in opt.get_attribute("class"):
                checked_host = opt.inner_text().strip().split()[0]
                opt.click()
                logger.info(f"自动选择并点击可用的物理机: {checked_host}")
                break

        if not checked_host:
            self.get_by_role("dialog").get_by_text("取消").click()
            pytest.skip("没有可用的物理机可供迁移")

        # 选择迁移速率
        if bandwidth:
            self.locator("div").filter(has_text=re.compile(r"^迁移速率")).get_by_placeholder("请选择").click()
            sleep(1)
            self.locator("li").filter(has_text=bandwidth).click()
            logger.info(f"已选择迁移速率: {bandwidth}")

        # 设置CPU自动收敛
        if cpu_auto:
            switch_locator = self.get_by_role("switch").locator("span")
            if switch_locator.is_visible():
                switch_locator.click()
                logger.info("已点击CPU自动收敛开关")

        # 确认热迁移
        self.get_by_role("dialog").get_by_text("确定").click()
        logger.info(f"已点击确定按钮，开始热迁移 {node_name}")

        return checked_host
