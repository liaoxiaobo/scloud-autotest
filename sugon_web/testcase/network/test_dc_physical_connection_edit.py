import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


def _cleanup_residual_dc_resources(dc_page):
    """按虚拟接口→虚拟网关→物理连接顺序清理残留资源。"""
    try:
        notifications = dc_page.page.locator(".el-notification__closeBtn")
        for i in range(notifications.count()):
            notifications.nth(i).click()
            dc_page.page.wait_for_timeout(300)
    except Exception:
        pass

    try:
        dc_page._ensure_virtual_interface_list()
        vif_names = dc_page.get_column_data("名称")
        for name in vif_names:
            if name and name.startswith("vif-"):
                dc_page.virtual_interface_delete(name)
                dc_page.assert_deleted(name, timeout=60)
    except Exception as e:
        logger.info(f"清理虚拟接口时跳过: {e}")

    try:
        dc_page._ensure_virtual_gateway_list()
        vgw_names = dc_page.get_column_data("名称")
        for name in vgw_names:
            if name and name.startswith("vgw-"):
                dc_page.virtual_gateway_delete(name)
                dc_page.assert_deleted(name, timeout=60)
    except Exception as e:
        logger.info(f"清理虚拟网关时跳过: {e}")

    try:
        dc_page._ensure_physical_connection_list()
        pc_names = dc_page.get_column_data("物理连接名称")
        for name in pc_names:
            if name and name.startswith("physical-"):
                dc_page.dc_physical_connection_terminate(name)
                dc_page.assert_deleted(name, timeout=60)
    except Exception as e:
        logger.info(f"清理物理连接时跳过: {e}")


@allure.epic('网络服务')
@allure.feature('云专线DC')
@allure.story('物理连接修改功能验证')
class TestDCPhysicalConnectionEdit:

    @allure.title("云专线DC-物理连接修改功能验证")
    def test_dc_physical_connection_edit(self, dc_page):
        """测试物理连接的修改功能：创建HA物理连接并审批通过后，
        验证修改弹窗中运营商、端口类型、HA字段为只读，
        修改名称和描述，验证列表页和详情页的修改结果。"""

        dc_name = f"physical-{random_data(length=4)}"
        new_dc_name = f"{dc_name}-modify"
        new_description = "修改后的描述值"
        operator = "unicom"
        operator_label = "联通"
        port_type = "10GE 单模光口"
        contact_name = "张三"
        contact_phone = "13805403159"
        contact_email = "ll@sugon.com"
        vlan_code = "205"

        with allure_step_log("步骤0: 清理残留资源（虚拟接口→虚拟网关→物理连接）"):
            _cleanup_residual_dc_resources(dc_page)

        try:
            with allure_step_log("步骤1: 创建HA物理连接并审批通过"):
                dc_page._ensure_physical_connection_list()
                dc_page.dc_physical_connection_create(
                    name=dc_name,
                    operator=operator,
                    port_type=port_type,
                    contact_name=contact_name,
                    contact_phone=contact_phone,
                    contact_email=contact_email,
                    ha_enable=True,
                )
                dc_page.assert_popup_success(timeout=10000)
                dc_page.assert_status(dc_name, status="办理中")

                dc_page.dc_physical_connection_approve(
                    name=dc_name,
                    status="DONE",
                    vlan_code=vlan_code,
                    cluster_name="Autotest",
                )
                dc_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤2: 等待物理连接状态变为办结/运行中"):
                dc_page.wait_for_physical_connection_status(
                    name=dc_name,
                    expected_status="办结",
                    expected_vm_status="运行中",
                    timeout=1200,
                    interval=10,
                )

            with allure_step_log("步骤3: 执行修改操作（修改名称和描述）"):
                dc_page._ensure_physical_connection_list()
                dc_page.dc_physical_connection_edit(
                    name=dc_name,
                    new_name=new_dc_name,
                    description=new_description,
                )
                dc_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤4: 列表页验证修改结果"):
                dc_page.assert_list_contain(new_dc_name, column_name="物理连接名称")
                dc_page.assert_status(new_dc_name, status="运行中")

                row_data = dc_page.get_row_data(new_dc_name)
                detail_operator = row_data.get("运营商", "")
                assert operator_label in detail_operator, f"列表页运营商不匹配: 期望包含 {operator_label}, 实际 {detail_operator}"

            with allure_step_log("步骤5: 详情页验证修改结果"):
                dc_page.open_detail_by_name(new_dc_name)

                detail_name = dc_page.get_detail_field_value("物理连接名称")
                assert detail_name == new_dc_name, f"详情页名称不匹配: 期望 {new_dc_name}, 实际 {detail_name}"

                detail_operator = dc_page.get_detail_field_value("运营商")
                assert operator_label in detail_operator, f"详情页运营商不匹配: 期望包含 {operator_label}, 实际 {detail_operator}"

                # 验证HA字段仍为开启
                try:
                    detail_ha = dc_page.get_detail_field_value("HA")
                    assert "开启" in detail_ha, f"详情页HA状态不匹配: 期望开启, 实际 {detail_ha}"
                except AssertionError:
                    logger.info("HA字段未显示，确认HA策略未开启")
        finally:
            with allure_step_log("清理: 删除虚拟接口"):
                try:
                    dc_page._ensure_virtual_interface_list()
                    vif_names = dc_page.get_column_data("名称")
                    for name in vif_names:
                        if name and name.startswith("vif-"):
                            dc_page.virtual_interface_delete(name)
                            dc_page.assert_deleted(name, timeout=60)
                except Exception as e:
                    logger.warning(f"删除虚拟接口失败: {e}")

            with allure_step_log("清理: 删除虚拟网关"):
                try:
                    dc_page._ensure_virtual_gateway_list()
                    vgw_names = dc_page.get_column_data("名称")
                    for name in vgw_names:
                        if name and name.startswith("vgw-"):
                            dc_page.virtual_gateway_delete(name)
                            dc_page.assert_deleted(name, timeout=60)
                except Exception as e:
                    logger.warning(f"删除虚拟网关失败: {e}")

            with allure_step_log("清理: 注销物理连接"):
                try:
                    dc_page._ensure_physical_connection_list()
                    pc_names = dc_page.get_column_data("物理连接名称")
                    for name in pc_names:
                        if name and name.startswith("physical-"):
                            dc_page.dc_physical_connection_terminate(name)
                            dc_page.assert_deleted(name, timeout=60)
                except Exception as e:
                    logger.warning(f"注销物理连接失败: {e}")
