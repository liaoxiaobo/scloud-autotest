import re
import pytest
from time import sleep

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util
from sugon_web.utils.logger import logger


class RedisPage(BasePage):
    """Redis实例管理页面对象"""

    def ensure_instance_tab(self, name: str, tab_name: str = "节点"):
        """确保进入Redis实例的详情页特定标签"""
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        sleep(2)
        if tab_name and tab_name != "节点":
            self.get_by_role("tab", name=tab_name).click()
            sleep(1)

    @submenu("实例管理")
    def create_instance(self, name: str, instance_type: str = "集群", version: str = "6.2.17",
                        password: str = "admin1234@sugon", port: int = 6379,
                        network: str = "Autotest", subnet: str = "Autotest:10.",
                        disk_type: str = None, disk_size: int = 20):
        """
        创建Redis实例
        :param name: 实例名称
        :param instance_type：实例类型 (单机/主从/集群)
        :param version: 版本
        :param password: 密码
        :param port: 端口
        :param network: 网络
        :param subnet: 子网
        :param disk_type: 磁盘类型
        :param disk_size: 磁盘大小
        """
        self.btn_create.click()

        # --- 类型设置 ---
        self.get_by_role("radio", name=instance_type).click()
        db_util.input_name(self).fill(name)

        # 版本选择 (根据实际UI调整选择器)
        self.locator("div").filter(has_text=re.compile(r"^版本")).get_by_placeholder("请选择").click()
        self.locator(".el-select-dropdown__item").filter(has_text=version).click()

        # --- 基本设置 ---
        db_util.project_dropdown(self).click()
        db_util.project_autotest(self).click()

        # 密码
        self.get_by_placeholder("请输入默认用户管理员用户密码").fill(password)
        self.get_by_placeholder("请输入确认密码").fill(password)

        # 端口 (使用特定过滤避免与哨兵端口冲突)
        port_input = self.locator("div").filter(has_text=re.compile(r"^服务端口$")).get_by_role("spinbutton")
        port_input.click()
        port_input.fill(str(port))

        # --- 网络设置 ---
        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        # --- 存储设置 ---
        selected_disk_type = disk_type if disk_type else self.volume_type
        db_util.select_disk_type_like_doris(self, selected_disk_type)

        # 数据盘大小
        self.locator("div").filter(has_text=re.compile(r"^数据盘大小\(GiB\)$")).get_by_role("spinbutton").fill(str(disk_size))
        
        # 规格选择 (默认选择列表中的第一个规格)
        self.locator(".el-table__body-wrapper").get_by_role("radio").first.click()
        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name):
        """删除Redis实例"""
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_instances(self, names: list):
        """批量删除Redis实例"""
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()

        self.get_by_text("批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def restart_instance(self, name):
        """重启Redis实例"""
        self.click_action(name, "重启实例")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def reset_admin_password(self, name, new_password):
        """重置管理员密码"""
        self.click_action(name, "修改默认用户密码")
        dialog = self.get_by_role("dialog")
        pwd_input = dialog.locator("div").filter(has_text=re.compile(r"^新密码$")).get_by_role("textbox")
        pwd_input.wait_for(state="visible", timeout=5000)
        pwd_input.fill(new_password)
        confirm_pwd_input = dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox")
        confirm_pwd_input.wait_for(state="visible", timeout=5000)
        confirm_pwd_input.fill(new_password)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name, new_name):
        """修改Redis实例名称"""
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称")
        dialog.get_by_role("textbox").fill(new_name)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def toggle_password_free(self, name):
        """开启或关闭免密登录"""
        self.click_action(name, "开启免密")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def scale_instance(self, name, target_spec: str):
        """调整实例规格 (在列表页)"""
        self.click_action(name, "调整规格")
        dialog = self.get_by_label("调整规格")
        dialog.get_by_text(target_spec).click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def restart_node(self, name: str, node_name: str):
        """重启Redis节点"""
        self.ensure_instance_tab(name)
        self.click_action(node_name, "重启")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_disk_size(self, name: str, node_name: str, new_size: int):
        """修改Redis节点云硬盘大小"""
        self.ensure_instance_tab(name)
        self.click_action(node_name, "修改云硬盘大小")
        dialog = self.get_by_role("dialog")
        spin_button = dialog.get_by_role("spinbutton")
        spin_button.wait_for(state="visible", timeout=5000)
        spin_button.fill(str(new_size))
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_specification(self, name: str, specification_name: str):
        """修改Redis实例规格"""
        self.ensure_instance_tab(name)
        # 表格特殊，绕过 base.py 的封装，直接使用 playwright 定位对应节点的修改规格按钮。处理element-ui固定列导致的两个元素问题使用.first
        self.page.locator("tr").filter(has_text=re.compile(f"{name}-0")).get_by_text("修改规格", exact=True).first.click()
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def upgrade_instance(self, name: str, target_type: str = None):
        """
        升级Redis实例
        :param name: 实例名称
        :param target_type: 目标实例类型（"高可用" 或 "集群"），如果为None则不进行选择操作直接提交（适用于默认选中的情况）
        """
        self.click_action(name, "升级")
        
        if target_type:
            # 尝试使用更通用的定位方式，避免依赖动态ID
            # 优先尝试通过文本定位 label，然后点击
            try:
                self.page.locator("label").filter(has_text=target_type).click()
            except:
                # 如果失败，尝试直接点击包含该文本的元素
                self.get_by_text(target_type, exact=True).click()

        self.dialog_confirm.click()

    @submenu("实例管理")
    def add_shard(self, name: str):
        """为Redis实例添加分片"""
        self.ensure_instance_tab(name)
        self.get_by_text("添加分片").first.click()
        self.get_by_label("添加分片").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def redis_hot_migration(self, name: str, node_name: str, bandwidth="50%", cpu_auto=True):
        """Redis节点热迁移"""
        self.ensure_instance_tab(name)
        self.click_action(node_name, "热迁移")
        sleep(2)

        # 选择目标物理机
        self.locator("form div").filter(has_text="目标物理机").get_by_placeholder("请选择").click()
        sleep(1)
        
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        options = dropdown.locator("li.el-select-dropdown__item")
        
        checked_host = None
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

        if bandwidth:
            self.locator("div").filter(has_text=re.compile(r"^迁移速率")).get_by_placeholder("请选择").click()
            sleep(1)
            self.locator("li").filter(has_text=bandwidth).click()
            logger.info(f"已选择迁移速率: {bandwidth}")

        if cpu_auto:
            switch_locator = self.get_by_role("switch").locator("span")
            if switch_locator.is_visible():
                switch_locator.click()
                logger.info("已点击CPU自动收敛开关")

        self.get_by_role("dialog").get_by_text("确定").click()
        logger.info(f"已点击确定按钮，开始热迁移 {node_name}")
        return checked_host

    @submenu("实例管理")
    def switch_network(self, name: str, network: str = "Autotest", subnet: str = "subnet:10.", selection_type: str = "快速选择"):
        """
        切换Redis实例网络
        :param name: 实例名称
        :param network: 网络名称
        :param subnet: 子网名称
        :param selection_type: 选择类型 ("快速选择" 或 "手动输入")
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_text("切换网络").first.click()

        dialog = self.get_by_label("切换网络")
        switch_network_form = dialog.locator(".el-form-item").filter(has_text=re.compile(r"切换网络"))

        # 选择网络
        switch_network_form.get_by_placeholder("请选择").first.click()
        self.page.locator("li").filter(has_text=re.compile(rf"^{network}$")).nth(1).click()

        # 选择子网
        switch_network_form.get_by_placeholder("请选择").nth(1).click()
        self.page.get_by_text(subnet).nth(1).click()

        # 获取当前可用的IP列表
        dialog.get_by_placeholder("请选择IP地址").click()
        sleep(2)
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        ip_options = dropdown.locator("li.el-select-dropdown__item").all_inner_texts()
        ip_list = [ip.strip() for ip in ip_options if ip.strip()]
        logger.info(f"获取到可用IP列表: {ip_list}")

        if selection_type == "快速选择":
            dialog.locator("label").filter(has_text="快速选择").click()
            # 重新点击下拉框以重新获得焦点或显示列表
            dialog.get_by_placeholder("请选择IP地址").click()
            self.page.locator("li.el-select-dropdown__item").filter(has_text=ip_list[0]).first.click()
        else:
            # 手动输入
            # 隐藏下拉框
            self.page.keyboard.press("Escape")
            dialog.locator("label").filter(has_text="手动输入").click()
            dialog.get_by_placeholder("请输入IP地址").fill(ip_list[0])

        # 节点IP选择 (展开节点列表)
        arrow_up = self.page.locator(".el-form-item__content > .el-icon-arrow-up")
        if arrow_up.is_visible():
            arrow_up.click()

        # 为每个节点输入IP，必须是IP列表中的
        # Redis集群（带分片）通常有多个节点，第一个IP给实例，后续IP分配给节点
        rows = dialog.locator("tr.el-table__row").all()
        for i, row in enumerate(rows):
            if i + 1 < len(ip_list):
                target_ip = ip_list[i + 1]
                row.get_by_role("textbox").click()
                row.get_by_role("textbox").fill(target_ip)
                logger.info(f"为Redis节点 {i} 分配可用IP: {target_ip}")
            else:
                logger.error(f"可用IP不足，无法为节点 {i} 分配IP")

        # 确定
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def create_user(self, name: str, user_name: str, password: str, privileges: str = "只读"):
        """新建用户"""
        self.ensure_instance_tab(name, "用户")
        self.btn_create.click()
        dialog = self.get_by_role("dialog")
        dialog.locator("form div").filter(has_text="用户名").get_by_role("textbox").fill(user_name)
        dialog.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(password)
        dialog.locator("div").filter(has_text=re.compile(r"^权限")).locator("i").click()
        self.page.locator("li").filter(has_text=privileges).click()
        dialog.get_by_text("确定").click()
        
    @submenu("实例管理")
    def delete_user(self, name: str, user_name: str):
        """删除用户"""
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
        sleep(2)
        self.click_action(user_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_users(self, name: str, user_names: list):
        """
        在指定实例下批量删除用户
        :param name: 实例名称
        :param user_names: 用户名列表
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
        sleep(2)

        for user_name in user_names:
            self.get_by_role("row", name=re.compile(user_name)).locator("span").nth(1).click()

        self.locator("div.cloud-button-btn").filter(has_text="批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def modify_user(self, name: str, user_name: str, new_password: str):
        """修改用户"""
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="用户").click()
        sleep(2)
        self.click_action(user_name, "修改用户")
        dialog = self.get_by_role("dialog")
        dialog.locator("div").filter(has_text=re.compile(r"^密码$")).get_by_role("textbox").fill(new_password)
        dialog.locator("div").filter(has_text=re.compile(r"^确认密码$")).get_by_role("textbox").fill(new_password)
        dialog.get_by_text("确定").click()

    @submenu("实例管理")
    def add_whitelist(self, name: str, ip_address: str):
        """添加白名单"""
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        sleep(2)
        self.get_by_text("添加", exact=True).click()
        self.get_by_placeholder("例：10.0.12.0/").fill(ip_address)
        self.get_by_label("添加白名单").get_by_text("确定").click()

    @submenu("实例管理")
    def delete_whitelist(self, name: str, ip_address: str):
        """移除白名单"""
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        sleep(2)
        self.locator("span").filter(has_text=ip_address).locator("i").click()
        self.get_by_label("移除").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def batch_delete_whitelist(self, name: str, ip_addresses: list):
        """批量删除白名单"""
        self.locator("#cloud-container-content").get_by_text(name).first.click()
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
        为Redis实例重置白名单
        :param name: 实例名称
        """
        self.locator("#cloud-container-content").get_by_text(name).first.click()
        self.get_by_role("tab", name="白名单").click()
        sleep(2)
        # MySQL 和 Redis 对于重置白名单按钮可能在页面呈现或文案一致
        self.locator("div.cloud-button-btn").filter(has_text="重置白名单").click()
        self.get_by_label("重置白名单").get_by_text("确定", exact=True).click()
    @submenu("实例管理")
    def instance_ip_binding(self, name: str, network: str = None):
        """
        为Redis实例绑定弹性IP (在实例详情页)
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        """
        self.ensure_instance_tab(name)
        self.get_by_text("绑定公网IP").first.click()
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()

        # 选择第一个状态为“关闭”的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()

        return ip_address

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        """
        为Redis实例解绑弹性IP
        :param name: 实例名称
        """
        self.ensure_instance_tab(name)
        self.get_by_text("解绑公网IP").first.click()
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def node_ip_binding(self, name: str, network: str = None):
        """
        为Redis节点绑定弹性IP
        :param name: 实例名称
        :param network: 网络名称 (仅绑定时需要)
        """
        self.ensure_instance_tab(name)
        self.click_action(f"{name}-0", "绑定公网IP")
        self.get_by_label("绑定公网IP", exact=True).get_by_placeholder("请选择").click()
        self.get_by_text(network).click()

        # 选择第一个状态为“关闭”的IP
        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        self.get_by_label("绑定公网IP", exact=True).get_by_text("确定").click()

        return ip_address

    @submenu("实例管理")
    def node_ip_unbinding(self, name: str):
        """
        为Redis节点解绑弹性IP
        :param name: 实例名称
        """
        self.ensure_instance_tab(name)
        self.click_action(f"{name}-0", "解绑公网IP")
        self.get_by_label("解绑公网IP").get_by_text("确定", exact=True).click()
