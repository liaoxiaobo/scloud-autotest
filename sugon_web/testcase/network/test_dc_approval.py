import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data


@allure.epic('网络服务')
@allure.feature('云专线DC')
@allure.story('HA新建与审批功能验证')
class TestDCApproval:

    @allure.title("云专线DC-物理连接(开启HA)-新建功能验证")
    def test_dc_physical_connection_create_ha(self, dc_page):
        """测试开启HA的物理连接新建、列表验证、详情验证和注销功能。"""

        dc_name = f"physical-{random_data(length=4)}"
        operator = "unicom"
        operator_label = "联通"
        port_type = "10GE 单模光口"
        contact_name = "张三"
        contact_phone = "13805403159"
        contact_email = "ll@sugon.com"

        with allure_step_log("步骤1: 进入物理连接页面并创建物理连接（开启HA）"):
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

        with allure_step_log("步骤2: 验证列表页"):
            dc_page.assert_popup_success(timeout=10000)
            dc_page.assert_list_contain(dc_name, column_name="物理连接名称")
            dc_page.assert_status(dc_name, status="办理中")

        with allure_step_log("步骤3: 验证详情页"):
            dc_page.open_detail_by_name(dc_name)

            detail_name = dc_page.get_detail_field_value("物理连接名称")
            assert detail_name == dc_name, f"详情页名称不匹配: 期望 {dc_name}, 实际 {detail_name}"

            detail_operator = dc_page.get_detail_field_value("运营商")
            assert operator_label in detail_operator, f"详情页运营商不匹配: 期望包含 {operator_label}, 实际 {detail_operator}"

            detail_contact_name = dc_page.get_detail_field_value("联系人姓名")
            assert detail_contact_name == contact_name, f"详情页联系人姓名不匹配: 期望 {contact_name}, 实际 {detail_contact_name}"

            detail_contact_phone = dc_page.get_detail_field_value("联系人电话")
            assert detail_contact_phone == contact_phone, f"详情页联系人电话不匹配: 期望 {contact_phone}, 实际 {detail_contact_phone}"

            detail_contact_email = dc_page.get_detail_field_value("联系人邮箱")
            assert detail_contact_email == contact_email, f"详情页联系人邮箱不匹配: 期望 {contact_email}, 实际 {detail_contact_email}"

            # 验证HA字段显示为"开启"
            detail_ha = dc_page.get_detail_field_value("HA")
            assert "开启" in detail_ha, f"详情页HA状态不匹配: 期望开启, 实际 {detail_ha}"

        with allure_step_log("步骤4: 注销物理连接"):
            dc_page._ensure_physical_connection_list()
            dc_page.dc_physical_connection_terminate(dc_name)
            dc_page.assert_deleted(dc_name, timeout=60)

    @allure.title("云专线DC-物理连接-HA-审批功能测试-通过")
    def test_dc_physical_connection_approve_pass(self, dc_page):
        """测试物理连接审批通过功能：创建HA物理连接后执行审批，验证状态变化。"""

        dc_name = f"physical-{random_data(length=4)}"
        operator = "unicom"
        port_type = "10GE 单模光口"
        contact_name = "张三"
        contact_phone = "13805403159"
        contact_email = "ll@sugon.com"
        vlan_code = "205"

        with allure_step_log("步骤1: 创建物理连接（开启HA）"):
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

        with allure_step_log("步骤2: 执行审批操作（状态=通过，VLAN=205，集群=Autotest）"):
            dc_page.dc_physical_connection_approve(
                name=dc_name,
                status="DONE",
                vlan_code=vlan_code,
                cluster_name="Autotest",
            )
            dc_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤3: 轮询等待审批后状态变化（最长600秒）"):
            final_row = dc_page.wait_for_physical_connection_status(
                name=dc_name,
                expected_status="办结",
                expected_vm_status="运行中",
                timeout=600,
                interval=10,
            )
            logger.info(f"最终状态: {final_row}")

        with allure_step_log("步骤4: 注销物理连接"):
            dc_page._ensure_physical_connection_list()
            dc_page.dc_physical_connection_terminate(dc_name)
            dc_page.assert_deleted(dc_name, timeout=60)
