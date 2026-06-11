import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


def _cleanup_dc_resources(dc_page):
    """清理DC资源：按虚拟接口→虚拟网关→物理连接顺序清理。

    作为模块级helper，内部处理异常但不吞掉，仅记录日志。
    """
    cleanup_errors = []

    with allure_step_log("清理: 删除虚拟接口"):
        try:
            dc_page._ensure_virtual_interface_list()
            dc_page.wait_for_page_ready()
            vif_names = dc_page.get_column_data("名称")
            for name in vif_names:
                if name and name.startswith("vif-"):
                    dc_page.virtual_interface_delete(name)
                    dc_page.assert_deleted(name, timeout=60)
            logger.info("虚拟接口清理完成")
        except Exception as e:
            logger.warning(f"删除虚拟接口失败: {e}")
            cleanup_errors.append(f"删除虚拟接口: {e}")

    with allure_step_log("清理: 删除虚拟网关"):
        try:
            dc_page._ensure_virtual_gateway_list()
            dc_page.wait_for_page_ready()
            vgw_names = dc_page.get_column_data("名称")
            for name in vgw_names:
                if name and name.startswith("vgw-"):
                    dc_page.virtual_gateway_delete(name)
                    dc_page.assert_deleted(name, timeout=60)
            logger.info("虚拟网关清理完成")
        except Exception as e:
            logger.warning(f"删除虚拟网关失败: {e}")
            cleanup_errors.append(f"删除虚拟网关: {e}")

    with allure_step_log("清理: 注销物理连接"):
        try:
            dc_page._ensure_physical_connection_list()
            dc_page.wait_for_page_ready()
            pc_names = dc_page.get_column_data("物理连接名称")
            for name in pc_names:
                if name and name.startswith("physical-"):
                    dc_page.dc_physical_connection_terminate(name)
                    dc_page.assert_deleted(name, timeout=60)
            logger.info("物理连接注销完成")
        except Exception as e:
            logger.warning(f"注销物理连接失败: {e}")
            cleanup_errors.append(f"注销物理连接: {e}")

    return cleanup_errors


@allure.epic('网络服务')
@allure.feature('云专线DC')
@allure.story('HA新建与审批功能验证')
class TestDCApprovalReject:

    @allure.title("云专线DC-物理连接-HA-审批功能测试-驳回后通过")
    def test_dc_physical_connection_approve_reject_then_pass(self, dc_page):
        """测试物理连接审批驳回后再通过：创建非HA物理连接，先驳回审批，再通过审批，验证状态变化。"""
        dc_name = f"physical-{random_data(length=4)}"
        operator = "unicom"
        port_type = "10GE 单模光口"
        contact_name = "张三"
        contact_phone = "13805403159"
        contact_email = "ll@sugon.com"
        vlan_code = "205"

        with allure_step_log("前置: 清理残留资源（避免VLAN冲突）"):
            _cleanup_dc_resources(dc_page)

        with allure_step_log("步骤1: 创建物理连接（未开启HA）"):
            dc_page._ensure_physical_connection_list()
            dc_page.close_dialog_if_exists()
            dc_page.wait_for_page_ready()
            dc_page.dc_physical_connection_create(
                name=dc_name,
                operator=operator,
                port_type=port_type,
                contact_name=contact_name,
                contact_phone=contact_phone,
                contact_email=contact_email,
                ha_enable=False,
            )
            dc_page.assert_popup_success(timeout=10)
            dc_page.assert_status(dc_name, status="办理中")
            logger.info(f"物理连接 {dc_name} 创建成功，状态为办理中")

        with allure_step_log("步骤2: 执行审批驳回操作"):
            dc_page.dc_physical_connection_approve(
                name=dc_name,
                status="REJECTED",
            )
            dc_page.assert_popup_success(timeout=10)
            logger.info(f"物理连接 {dc_name} 审批驳回成功")

        with allure_step_log("步骤3: 验证驳回后状态"):
            dc_page._ensure_physical_connection_list()
            dc_page.wait_for_page_ready()
            dc_page.assert_status(dc_name, status="驳回")
            logger.info(f"物理连接 {dc_name} 状态验证为驳回")

        with allure_step_log("步骤4: 再次执行审批通过操作"):
            dc_page.dc_physical_connection_approve(
                name=dc_name,
                status="DONE",
                vlan_code=vlan_code,
                cluster_name="Autotest",
            )
            dc_page.assert_popup_success(timeout=10)
            logger.info(f"物理连接 {dc_name} 审批通过成功")

        with allure_step_log("步骤5: 轮询等待审批后状态变化（最长180秒）"):
            final_row = dc_page.wait_for_physical_connection_status(
                name=dc_name,
                expected_status="办结",
                expected_vm_status="运行中",
                timeout=180,
                interval=20,
            )
            logger.info(f"最终状态: {final_row}")

        with allure_step_log("清理: 按顺序注销DC资源"):
            cleanup_errors = _cleanup_dc_resources(dc_page)
            if cleanup_errors:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")
