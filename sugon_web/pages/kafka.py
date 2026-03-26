import re
from time import sleep

import pytest

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils import db_util
from sugon_web.utils.logger import logger


class KafkaPage(BasePage):
    """Kafka实例管理页面对象"""

    def ensure_instance_tab(self, name: str, tab_name: str = "节点"):
        """确保进入Kafka实例详情页指定标签"""
        if "/kafka-detail/" not in self.page.url:
            row = self.get_row_by_name(name)
            cells = row.locator("td")
            target = cells.nth(1) if cells.count() > 1 else row
            target.click()
            self.wait_for_page_ready()
            sleep(2)
        if tab_name and tab_name != "节点":
            self.get_by_role("tab", name=tab_name).click()
            self.wait_for_page_ready()
            sleep(1)

    @submenu("实例管理")
    def create_instance(self, name: str, version: str = "2.4.1", security_mode: bool = False,
                        password: str = "Kafka1234@sugon", cluster: str = "Autotest",
                        network: str = "Autotest", subnet: str = "Autotest:10.",
                        disk_type: str = None, disk_size: int = 10,
                        specification_name: str = "应用中间件标准型 kafka.d6.large 2核 4GiB"):
        """创建Kafka实例"""
        def select_visible_option(option_text: str):
            dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
            dropdown.wait_for(state="visible", timeout=5000)
            dropdown.locator("li.el-select-dropdown__item").filter(
                has_text=re.compile(rf"^{re.escape(option_text)}$")
            ).first.click()

        self.btn_create.click()
        self.wait_for_page_ready()
        sleep(1)

        # 基本信息
        self.get_by_placeholder("请输入名称").fill(name)

        version_dropdown = self.locator("div").filter(has_text=re.compile(r"^版本")).locator("input").first
        version_dropdown.click()
        select_visible_option(version)

        cluster_dropdown = self.locator("div").filter(has_text=re.compile(r"^集群")).locator("input").first
        cluster_dropdown.click()
        select_visible_option(cluster)

        # 安全模式（默认关闭）
        if security_mode:
            switch = self.locator("form").filter(has_text="安全模式").get_by_role("switch")
            if switch.get_attribute("aria-checked") in [None, "false"]:
                switch.click()

            try:
                self.get_by_placeholder("请输入admin管理员密码").fill(password)
                self.get_by_placeholder("请输入确认密码").fill(password)
            except Exception:
                password_inputs = self.locator("input[placeholder*='密码']")
                password_inputs.nth(0).fill(password)
                password_inputs.nth(1).fill(password)

        # 网络设置
        db_util.select_network(self, "请选择网络", network)
        db_util.select_network(self, "请选择子网", subnet)

        # 存储设置
        self.locator("div").filter(has_text=re.compile(r"^云硬盘类型")).locator("input").first.click()
        selected_disk_type = disk_type if disk_type else self.volume_type
        select_visible_option(selected_disk_type)
        self.locator("div").filter(has_text=re.compile(r"^云硬盘大小\(GiB\)$")).get_by_role("spinbutton").fill(str(disk_size))

        # 规格
        specification_row = self.get_by_role("row", name=re.compile(re.escape(specification_name)))
        if specification_row.count() > 0:
            specification_row.get_by_role("radio").click()
        else:
            self.locator(".el-table__body-wrapper").get_by_role("radio").first.click()

        self.btn_submit.click()

    @submenu("实例管理")
    def delete_instance(self, name: str):
        """删除Kafka实例"""
        self.click_action(name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_instances(self, names: list):
        """批量删除Kafka实例"""
        for name in names:
            self.get_by_role("row", name=re.compile(name)).locator("span").nth(1).click()
        self.get_by_text("批量删除").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def rename_instance(self, old_name: str, new_name: str):
        """修改Kafka实例名称"""
        self.click_action(old_name, "修改实例名称")
        dialog = self.get_by_label("修改实例名称")
        dialog.get_by_role("textbox").fill(new_name)
        self.dialog_confirm.click()

    @submenu("实例管理")
    def restart_instance(self, name: str):
        """重启Kafka实例"""
        self.click_action(name, "重启实例")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def restart_node(self, name: str, node_name: str):
        """重启Kafka节点"""
        self.ensure_instance_tab(name)
        self.click_action(node_name, "重启")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def instance_ip_binding(self, name: str, network: str):
        """实例绑定公网IP"""
        self.ensure_instance_tab(name)
        self.get_by_text("绑定公网IP").first.click()
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("body > div.el-select-dropdown:visible").last.get_by_text(network).click()
        self.wait_for_page_ready()

        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        dialog.get_by_text("确定", exact=True).click()
        return ip_address

    @submenu("实例管理")
    def instance_ip_unbinding(self, name: str):
        """实例解绑公网IP"""
        self.ensure_instance_tab(name)
        self.get_by_text("解绑公网IP").first.click()
        self.page.locator("div.el-dialog:visible").last.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def node_ip_binding(self, name: str, network: str):
        """节点绑定公网IP"""
        self.ensure_instance_tab(name)
        self.click_action(f"{name}-0", "绑定公网IP")
        dialog = self.page.locator("div.el-dialog:visible").last
        dialog.get_by_placeholder("请选择").click()
        self.page.locator("body > div.el-select-dropdown:visible").last.get_by_text(network).click()
        self.wait_for_page_ready()

        ip_row = self.page.locator("tr.el-table__row:has-text('关闭')").first
        ip_address = ip_row.locator("td").nth(1).inner_text()
        ip_row.locator("label[role='radio']").click()

        dialog.get_by_text("确定", exact=True).click()
        return ip_address

    @submenu("实例管理")
    def node_ip_unbinding(self, name: str):
        """节点解绑公网IP"""
        self.ensure_instance_tab(name)
        self.click_action(f"{name}-0", "解绑公网IP")
        self.page.locator("div.el-dialog:visible").last.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def change_specification(self, name: str, specification_name: str):
        """修改Kafka实例规格"""
        self.ensure_instance_tab(name)
        self.click_action(f"{name}-0", "修改规格")
        self.get_by_role("row", name=specification_name).get_by_role("radio").click()
        self.dialog_confirm.click()

    @submenu("实例管理")
    def change_disk_size(self, name: str, node_name: str, new_size: int):
        """修改Kafka节点云硬盘大小"""
        self.ensure_instance_tab(name)
        self.click_action(node_name, "修改云硬盘大小")
        dialog = self.get_by_role("dialog")
        spin_button = dialog.get_by_role("spinbutton")
        spin_button.wait_for(state="visible", timeout=5000)
        spin_button.fill(str(new_size))
        self.dialog_confirm.click()

    @submenu("实例管理")
    def edit_instance_parameter(self, name: str, param_name: str, param_value: str):
        """编辑Kafka实例参数（Kafka无应用按钮，仅弹窗确认）"""
        self.ensure_instance_tab(name, "参数配置")
        self.page.locator("tr").filter(has_text=param_name).get_by_text("编辑").last.click()

        dialog = self.page.locator("div.el-dialog:visible").last
        value_input = dialog.locator("div").filter(
            has_text=re.compile(r"^参数运行值")
        ).get_by_role("textbox")
        value_input.click()
        value_input.fill(param_value)
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def kafka_hot_migration(self, name: str, node_name: str, bandwidth: str = "50%", cpu_auto: bool = True):
        """Kafka节点热迁移"""
        self.ensure_instance_tab(name)
        self.click_action(node_name, "热迁移")
        self.wait_for_page_ready()
        sleep(2)

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

        if cpu_auto:
            switch_locator = self.get_by_role("switch").locator("span")
            if switch_locator.is_visible():
                switch_locator.click()

        self.get_by_role("dialog").get_by_text("确定").click()
        return checked_host

    @submenu("实例管理")
    def switch_network(self, name: str, network: str = "Autotest", subnet: str = "subnet:10.",
                       selection_type: str = "快速选择", node_count: int = 3):
        """切换Kafka实例网络，运行中时会先触发关闭服务，再次执行才进入网络切换"""
        self.ensure_instance_tab(name, "详情")
        self.get_by_label("详情").get_by_text("切换网络").click()

        # Kafka实例运行中时，首次点击“切换网络”会先弹出“关闭服务”确认框。
        close_service_dialog = self.get_by_label("关闭服务")
        if close_service_dialog.count() > 0:
            close_service_dialog.last.get_by_text("确定", exact=True).click()
            return "close_service"

        dialog = self.get_by_label("切换网络")

        dialog.get_by_placeholder("请选择").nth(2).click()
        self.page.locator("li").filter(has_text=re.compile(rf"^{network}$")).nth(1).click()

        dialog.get_by_placeholder("请选择").nth(3).click()
        self.page.get_by_text(subnet).nth(1).click()

        dialog.get_by_placeholder("请选择IP地址").click()
        sleep(2)
        dropdown = self.page.locator("body > div.el-select-dropdown:visible").last
        ip_options = dropdown.locator("li.el-select-dropdown__item").all_inner_texts()
        ip_list = [ip.strip() for ip in ip_options if ip.strip()]
        logger.info(f"Kafka切换网络可用IP列表: {ip_list}")

        if selection_type == "快速选择":
            dialog.locator("label").filter(has_text="快速选择").click()
            dialog.get_by_placeholder("请选择IP地址").click()
            self.page.locator("li.el-select-dropdown__item").filter(has_text=ip_list[0]).first.click()
        else:
            self.page.keyboard.press("Escape")
            dialog.locator("label").filter(has_text="手动输入").click()
            dialog.get_by_placeholder("请输入IP地址").fill(ip_list[0])

        arrow_up = self.page.locator(".el-form-item__content > .el-icon-arrow-up")
        if arrow_up.is_visible():
            arrow_up.click()

        rows = dialog.locator("tr.el-table__row").all()
        assign_rows = min(len(rows), node_count)
        for i in range(assign_rows):
            if i + 1 < len(ip_list):
                target_ip = ip_list[i + 1]
                row = rows[i]
                row.get_by_role("textbox").click()
                row.get_by_role("textbox").fill(target_ip)
                logger.info(f"为Kafka节点 {i + 1} 分配IP: {target_ip}")
            else:
                logger.error(f"Kafka切换网络可用IP不足，无法为第 {i + 1} 个节点分配IP")

        dialog.get_by_text("确定", exact=True).click()
        return "switch_network"

    @submenu("实例管理")
    def create_topic(self, name: str, topic_name: str, partition_count: int = 3,
                     replica_count: int = 1, retention_days: int = 7,
                     timestamp_type: str = "LogAppendTime", batch_max_mb: int = 1):
        """创建Topic"""
        self.ensure_instance_tab(name, "Topic管理")
        self.btn_create.click()

        dialog = self.get_by_role("dialog")
        dialog.locator("div").filter(has_text=re.compile(r"^Topic名称$")).get_by_role("textbox").fill(topic_name)
        dialog.locator("div").filter(has_text=re.compile(r"^分区数")).get_by_role("spinbutton").fill(str(partition_count))
        dialog.locator("div").filter(has_text=re.compile(r"^副本数")).get_by_role("spinbutton").fill(str(replica_count))
        dialog.locator("div").filter(has_text=re.compile(r"^消息保留时间")).get_by_role("spinbutton").fill(str(retention_days))
        dialog.locator("div").filter(has_text=re.compile(r"^消息时间戳类型")).get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=timestamp_type).first.click()
        dialog.locator("div").filter(has_text=re.compile(r"^批处理消息最大值")).get_by_role("spinbutton").fill(str(batch_max_mb))
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def edit_topic(self, name: str, topic_name: str, partition_count: int = 4,
                   retention_days: int = 8, timestamp_type: str = "CreateTime", batch_max_mb: int = 2):
        """修改Topic"""
        self.ensure_instance_tab(name, "Topic管理")

        try:
            self.click_action(topic_name, "修改")
        except Exception:
            self.click_action(topic_name, "编辑")

        dialog = self.get_by_role("dialog")
        dialog.locator("div").filter(has_text=re.compile(r"^分区数")).get_by_role("spinbutton").fill(str(partition_count))
        dialog.locator("div").filter(has_text=re.compile(r"^消息保留时间")).get_by_role("spinbutton").fill(str(retention_days))
        dialog.locator("div").filter(has_text=re.compile(r"^消息时间戳类型")).get_by_placeholder("请选择").click()
        self.page.locator("li").filter(has_text=timestamp_type).first.click()
        dialog.locator("div").filter(has_text=re.compile(r"^批处理消息最大值")).get_by_role("spinbutton").fill(str(batch_max_mb))
        dialog.get_by_text("确定", exact=True).click()

    @submenu("实例管理")
    def delete_topic(self, name: str, topic_name: str):
        """删除Topic"""
        self.ensure_instance_tab(name, "Topic管理")
        self.click_action(topic_name, "删除")
        self.dialog_confirm.click()

    @submenu("实例管理")
    def batch_delete_topics(self, name: str, topic_names: list):
        """批量删除Topic"""
        self.ensure_instance_tab(name, "Topic管理")

        for topic_name in topic_names:
            row = self.get_by_role("row", name=re.compile(topic_name))
            checkbox = row.locator(".el-checkbox").first
            if checkbox.count() > 0:
                checkbox.click()
            else:
                row.get_by_role("checkbox").check(force=True)

        self.btn_batch_delete.click()
        self.dialog_confirm.click()
