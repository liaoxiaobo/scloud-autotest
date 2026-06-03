import re

import allure
import pytest
from sugon_web.pages.security.usm import UsmPage
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.framework.decorators import skip_if_nodes_less_than


@allure.epic('安全合规')
@allure.feature('云堡垒机高级版USM')
@allure.story('USM实例-热迁移-手动指定')
class TestUsmHotMigration:

    @allure.title("USM-热迁移-手动指定")
    @skip_if_nodes_less_than(2)
    def test_usm_hot_migration_manual(self, usm_instance, page, ssh_host):
        usm_page = UsmPage(page)
        usm_page.goto_list_page()
        """验证 USM 实例热迁移（手动指定目标物理机）功能。

        通过 fixture 获取 USM 实例，执行热迁移后验证页面状态和后台 virsh。
        """
        name = usm_instance["name"]
        logger.info(f"USM 实例 {name} 已就绪")

        with allure_step_log("步骤1: 进入USM列表页并记录当前物理机节点"):
            usm_page.goto_list_page()
            row_data = usm_page.get_row_data(name)
            source_host = row_data.get("物理机", "")
            vm_status_before = row_data.get("虚拟机状态", "")
            service_status_before = row_data.get("服务状态", "")
            logger.info(
                f"USM 实例 {name} 当前物理机: {source_host}, "
                f"虚拟机状态: {vm_status_before}, 服务状态: {service_status_before}"
            )
            assert source_host, f"未获取到 USM 实例 {name} 的物理机信息"
            assert "运行" in vm_status_before, \
                f"USM 实例 {name} 虚拟机状态不为运行: {vm_status_before}"
            assert "运行" in service_status_before, \
                f"USM 实例 {name} 服务状态不为运行: {service_status_before}"

        with allure_step_log("步骤2: 进入实例详情页记录云堡垒机ID"):
            server_id = usm_page.usm_get_server_id(name)
            assert server_id, f"未获取到 USM 实例 {name} 的 server_id"
            logger.info(f"USM 实例 {name} server_id: {server_id}")
            # 提取 UUID 前三段用于 virsh grep 匹配
            server_id_prefix = "-".join(server_id.split("-")[:3])
            logger.info(f"USM 实例 {name} UUID 前三段: {server_id_prefix}")

        with allure_step_log("步骤3: 执行热迁移（手动指定目标物理机）"):
            usm_page.goto_list_page()
            target_host = usm_page.usm_hot_migration(name, m_type="手动指定", bandwidth="全速")
            assert target_host, "热迁移未选择到目标物理机"
            assert target_host != source_host, \
                f"热迁移目标物理机与源物理机相同: {source_host}"
            usm_page.assert_popup_success("热迁移成功")
            logger.info(f"USM 实例 {name} 热迁移命令下发成功，目标物理机: {target_host}")

        with allure_step_log("步骤4: 验证迁移中状态"):
            usm_page.goto_list_page()
            usm_page.assert_status(name, status="迁移中", refresh=True, refresh_interval=5, timeout=60)
            logger.info("USM 实例状态已变为迁移中")

        with allure_step_log("步骤5: 等待迁移完成并验证页面状态"):
            usm_page.wait_for_source_complete(name, complete_timeout=180)
            usm_page.assert_status(name, status="运行", refresh=True, refresh_interval=5, timeout=180)
            row_data_after = usm_page.get_row_data(name)
            actual_host = row_data_after.get("物理机", "")
            actual_vm_status = row_data_after.get("虚拟机状态", "")
            actual_service_status = row_data_after.get("服务状态", "")
            logger.info(
                f"USM 实例 {name} 迁移后物理机: {actual_host}, "
                f"虚拟机状态: {actual_vm_status}, 服务状态: {actual_service_status}"
            )
            assert actual_host == target_host, \
                f"热迁移后物理机不匹配: 期望={target_host}, 实际={actual_host}"
            assert "运行" in actual_vm_status, \
                f"热迁移后虚拟机状态不为运行: {actual_vm_status}"
            assert "运行" in actual_service_status, \
                f"热迁移后服务状态不为运行: {actual_service_status}"
            logger.info("热迁移页面状态验证通过")

        with allure_step_log("步骤6: SSH连接源物理机后台验证虚拟机已迁出"):
            source_host_short = source_host.split(".")[0]
            virsh_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                check_rc=True,
            )
            logger.info(f"源物理机 {source_host_short} virsh list 输出:\n{virsh_output}")
            grep_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {source_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                check_rc=False,
            )
            logger.info(
                f"源物理机 {source_host_short} virsh grep 输出: {grep_output!r}"
            )
            assert not grep_output or server_id_prefix not in grep_output, \
                f"源物理机 {source_host_short} 上仍存在该虚拟机 UUID: {server_id_prefix}"
            logger.info(f"源物理机 {source_host_short} 验证通过：虚拟机已不在源节点")

        with allure_step_log("步骤7: SSH连接目标物理机后台验证虚拟机已迁入"):
            target_host_short = target_host.split(".")[0]
            virsh_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list'",
                check_rc=True,
            )
            logger.info(f"目标物理机 {target_host_short} virsh list 输出:\n{virsh_output}")
            grep_output = ssh_host.run(
                f"ssh -o StrictHostKeyChecking=no {target_host_short} "
                f"'docker exec -i nova_libvirt virsh list | grep {server_id_prefix}'",
                check_rc=True,
            )
            logger.info(
                f"目标物理机 {target_host_short} virsh grep 输出: {grep_output!r}"
            )
            assert server_id_prefix in grep_output, \
                f"目标物理机 {target_host_short} 上未找到该虚拟机 UUID: {server_id_prefix}"
            logger.info(f"目标物理机 {target_host_short} 验证通过：虚拟机已在目标节点")

        with allure_step_log("步骤8: SSH管理API验证节点归属"):
            guest_info = ssh_host.guest_show(server_id)
            actual_node = guest_info.get("node", "")
            logger.info(f"scli guest show {server_id} node={actual_node}")
            assert actual_node == target_host, \
                f"管理API节点不匹配: scli返回node={actual_node}, 期望={target_host}"
            logger.info(f"管理API验证通过: node={actual_node} 与目标物理机一致")
