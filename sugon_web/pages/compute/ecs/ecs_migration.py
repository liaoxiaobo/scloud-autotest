import random
import time
from time import sleep
import pytest

from sugon_web.common.base import BasePage, submenu
from sugon_web.utils.logger import logger

class EcsMigrationMixin(BasePage):
    """ECS 热迁移与冷迁移操作。"""
    @submenu("弹性云服务器")
    def ecs_batch_migration(self, names, migration_type="热迁移", scheduling=None, node="master01", cluster="Autotest",
                            bandwidth=None, cpu_auto=False):
        """批量迁移云服务器

        Args:
            names: 云服务器名称列表
            migration_type: 迁移方式，默认为"热迁移"，可选"冷迁移"
            scheduling: 调度方式
            node: 目标节点
            bandwidth: 带宽设置，默认为"全速"
            cpu_auto: CPU自动收敛
        """
        # 选择指定的云服务器
        self.select_rows_by_names(names)

        # 点击更多操作按钮
        self.get_by_role("button", name="更多操作").click()

        # 选择指定的云服务器并点击批量迁移
        self._click_batch_operation_option(f"批量{migration_type}")

        if scheduling == "手动指定":
            self.get_by_role("radio", name="手动指定 󦕟").click()
            if migration_type == "热迁移":
                # 选择目标集群cluster
                self.get_by_text("目标集群").locator("xpath=./following-sibling::div//input").click()
                locs = [
                    self.locator("li").filter(has_text=cluster).nth(1),  # 同名集群内迁移
                    self.locator("li").filter(has_text=cluster)
                ]
                self._find_element(locs, f"集群{cluster}").click()

                # 等待物理机选择区域加载完成
                # 尝试选择指定的目标物理机
                available_hosts = self._get_available_migration_hosts()
                if node in available_hosts:
                    # 点击该节点
                    self.get_by_role("radio", name=node).click()
                    checked_host = node
                    logger.info(f"已选择指定的目标物理机: {checked_host}")

        # 选择带宽
        if migration_type == "热迁移" and bandwidth:
            self.get_by_placeholder("请选择带宽").click()
            # self.locator("li").filter(has_text=bandwidth).click()
            self.locator("//*[text()='半速']/../preceding-sibling::*[1]/span").click()
            self.locator("li").filter(has_text=bandwidth).click()
        if cpu_auto and migration_type == "热迁移":
            # 设置开关
            loc = self.get_by_role("switch").locator("span")
            if not loc.is_enabled():
                loc.click()

        # 确认迁移
        self.dialog_confirm.click()

        logger.info(f"批量迁移云服务器下发成功: {names}, 迁移方式: {migration_type}, 带宽: {bandwidth}")


    @submenu("弹性云服务器")
    def ecs_hot_migration(self, name, target_host=None, m_type="系统分配", storage=False, bandwidth="全速",
                          cpu_auto=False):
        """云服务器热迁移

        Args:
            name: 云服务器名称
            target_host: 目标物理机，如"master03.cloud.local"
            m_type: 调度方式，"系统分配"或"手动指定"
            storage: 是否迁移存储，默认为False
            bandwidth: 迁移速率，默认为"全速"
            cpu_auto: 是否启用CPU自动收敛，默认为False
        """
        checked_host = None
        # 点击云服务器操作按钮，选择热迁移
        self.click_action(name, "热迁移")

        # 选择调度方式
        if m_type == "手动指定":

            self.get_by_role("radio", name="手动指定 󦕟").click()

            # 点击"选择物理机"按钮，打开物理机选择区域
            self.get_by_text("目标物理机").locator("xpath=./following-sibling::div/span").click()

            # 等待物理机选择区域加载完成

            # 取所有可用的物理机节点，排除包含is-disabled属性的节点
            available_hosts = self._get_available_migration_hosts()

            # 如果没有可用物理机，抛出异常
            if not available_hosts:
                error_msg = "没有可用的物理机可供选择"
                logger.error(error_msg)
                locs = [
                    self.get_by_label("close 选择物理机"),
                    self.get_by_text("取消"),
                ]
                self._find_element(locs, "取消").click()
                time.sleep(0.5)  # 等待选择物理机的section关闭
                self.get_by_label("热迁移", exact=True).get_by_text("取消").click()  # 取消热迁移
                pytest.skip(error_msg)

            # 选择目标物理机
            if target_host:
                # 尝试选择指定的目标物理机
                target_host = f"{target_host}.cloud.local" if ".cloud.local" not in target_host else target_host
                if target_host in available_hosts:
                    # 点击该节点
                    self.get_by_role("radio", name=target_host).click()
                    checked_host = target_host
                    self.dialog_confirm.click()
                    logger.info(f"已选择指定的目标物理机: {checked_host}")
                else:
                    # 如果指定的目标物理机不可用，选择第一个可用的
                    logger.warning(f"指定的目标物理机 {target_host} 不可用，选择第一个可用物理机")
                    self.get_by_role("radio", name=available_hosts[0]).click()
                    checked_host = available_hosts[0]
                    self.dialog_confirm.click()
                    logger.info(f"已选择第一个可用的物理机: {checked_host}")

        # 选择是否迁移存储
        if storage:
            self.get_by_role("checkbox").click()

        # 选择迁移速率
        self.get_by_placeholder("请选择迁移速率").click()
        self.locator("li").filter(has_text=bandwidth).click()

        # 设置CPU自动收敛选项
        if cpu_auto:
            switch_locator = self.get_by_role("switch").locator("span")
            if not switch_locator.is_enabled():
                switch_locator.click()

        # 确认热迁移
        self.dialog_confirm.click()

        logger.info(
            f"开始热迁移云服务器: {name}, 调度方式: {m_type}, 目标主机: {checked_host}, 存储迁移: {storage}, 迁移速率: {bandwidth}")
        return checked_host


    @submenu("弹性云服务器")
    def ecs_cold_migration(self, name, m_type="系统分配", cluster=None, target_host="master01"):
        """云服务器冷迁移

        Args:
            name: 云服务器名称
            m_type: 调度方式，"系统分配"或"手动指定"
            cluster: 目标集群，如"Autotest"
            target_host: 目标物理机，如"master01","controller01"
        """
        checked_host = None

        # 点击云服务器操作按钮，选择冷迁移
        self.click_action(name, "冷迁移")
        # 选择调度方式
        if m_type == "手动指定":

            self.get_by_role("radio", name="手动指定 󦕟").click()

            # 选择目标集群cluster
            self.get_by_text("目标集群").locator("xpath=./following-sibling::div//input").click()
            locs = [
                self.locator("li").filter(has_text=cluster).nth(1),  # 同名集群内迁移
                self.locator("li").filter(has_text=cluster)
            ]
            self._find_element(locs, f"集群{cluster}").click()

            # 等待物理机选择区域加载完成

            # 选择目标物理机
            if target_host:
                try:
                    # 尝试选择指定的目标物理机
                    target_host = f"{target_host}.cloud.local" if ".cloud.local" not in target_host else target_host
                    self.locator("section").get_by_placeholder("搜索（名称）").fill(target_host)
                    self.get_by_role("dialog").get_by_text("搜索").click()

                    # 尝试选择指定的目标物理机
                    self.get_by_role("radio", name=target_host).click()
                    checked_host = target_host
                    logger.info(f"已选择指定的目标物理机: {checked_host}")

                except Exception as e:
                    # 如果未指定的目标物理机，选择第一个可用的
                    logger.warning(f"指定的目标物理机 {target_host} 不可用 ，选择第一个可用物理机")
                    self.locator("section").get_by_text("重置").click()
                    available_hosts = self._get_available_migration_hosts()
                    # 如果没有可用物理机，抛出异常
                    if not available_hosts:
                        error_msg = "没有可用的物理机可供选择"
                        logger.error(error_msg)
                        self.dialog_cancel.click()
                        pytest.skip(error_msg)
                    self.get_by_role("radio", name=available_hosts[0]).click()
                    checked_host = available_hosts[0]
                    logger.info(f"已选择第一个可用的物理机: {checked_host}")

        # 确认冷迁移
        self.dialog_confirm.click()

        logger.info(f"云服务器冷迁移请求已提交: {name}，迁移方式: {m_type}, 集群{cluster},目标主机: {checked_host}")
        return checked_host


    @submenu("弹性云服务器")
    def ecs_hot_migration_options(self, name) -> list:
        """云服务器热迁移节点选项

        Args:
            name: 云服务器名称
        """
        # 点击云服务器操作按钮，选择热迁移
        self.click_action(name, "热迁移")

        self.get_by_role("radio", name="手动指定 󦕟").click()

        # 点击"选择物理机"按钮，打开物理机选择区域
        self.get_by_text("目标物理机").locator("xpath=./following-sibling::div/span").click()

        # 等待物理机选择区域加载完成

        # 取所有可用的物理机节点，排除包含is-disabled属性的节点
        available_hosts = self._get_available_migration_hosts()
        self.locator("section").get_by_text("取消").click()
        sleep(1)  # 多个弹窗堆叠，需要等待上一层关闭
        self.close_dialog_if_exists()
        return available_hosts


    def _get_available_migration_hosts(self):
        """获取可用的迁移物理机节点，排除包含is-disabled的节点

        Returns:
            可用物理机节点名称列表
        """
        available_hosts = []
        # 获取所有物理机行
        all_rows = self.locator("section").locator(".el-table__body-wrapper").locator("tr")
        row_count = all_rows.count()
        self.logger.info(f"找到 {row_count} 个tr行")

        # 备用选择器
        if row_count == 0:
            all_rows = self.locator("section").locator("tbody tr")
            row_count = all_rows.count()
            logger.info(f"使用备用选择器找到 {row_count} 个tr行")

        for i in range(row_count):
            try:
                row = all_rows.nth(i)
                first_td = row.locator("td").first

                # 获取节点名称
                host_name = first_td.inner_text().strip()

                # 获取第一个span并检查is-disabled
                first_span = first_td.locator("div label span").nth(0)
                class_attr = ""

                if first_span.count() > 0:
                    class_attr = first_span.get_attribute("class") or ""

                is_disabled = "is-disabled" in class_attr

                # 如果可用且名称不为空
                if not is_disabled and host_name:
                    available_hosts.append(host_name)

            except Exception as e:
                import traceback
                logger.error(f"处理第{i + 1}行出错: {e}")
                logger.error(traceback.format_exc())
                continue

        logger.info(f"可用节点: {available_hosts}")
        return available_hosts


    def ecs_batch_migration_names(self, names: list, pre_nodes: list, available_hosts: list):
        """批量云服务器热迁移节点检查

        Args:
            names: 云服务器名称
            available_hosts: 可用节点
        """
        unique_nodes = set(pre_nodes)

        # 场景1: 所有虚机在同一节点
        if len(unique_nodes) == 1:
            self.logger.info(f"虚机在同一节点{unique_nodes}")
            if not available_hosts:
                pytest.skip("没有可用的节点满足亲和组迁移策略")

            final_node = random.choice(available_hosts)
            self.ecs_hot_migration(names[0], final_node, m_type="手动指定")
            self.assert_status(names[0], status="迁移中", refresh=True, refresh_interval=2)
            self.assert_status(names[0])

            return names[1:], final_node

        # 场景2: 虚机分布在不同节点
        if len(unique_nodes) > 1 and len(unique_nodes) <= len(available_hosts) + 1:
            # 统计每个节点的索引
            node_indices = {}
            for idx, node in enumerate(pre_nodes):
                node_indices.setdefault(node, []).append(idx)

            # 找出现次数最少的节点
            min_node = min(node_indices, key=lambda n: len(node_indices[n]))
            min_indices = node_indices[min_node]

            # 如果有唯一节点（出现1次），只移除一个
            if len(min_indices) == 1:
                names.pop(min_indices[0])
                return names, min_node

            # 否则移除该节点的所有虚机
            [names.pop(idx) for idx in sorted(min_indices, reverse=True)]
            return names, min_node
        else:
            pytest.skip("没有可用的节点满足亲和组迁移策略")
