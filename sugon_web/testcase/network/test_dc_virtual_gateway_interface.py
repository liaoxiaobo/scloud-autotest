import time

import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('云专线DC')
@allure.story('虚拟网关及虚拟接口创建')
class TestDCVirtualGatewayInterface:

    @allure.title("云专线DC-虚拟网关-新建功能验证")
    def test_virtual_gateway_create(self, dc_page, vpc_page):
        """测试虚拟网关的创建、列表验证和删除功能。"""
        vpc_name = f"vpc-{random_data(length=4)}"
        subnet_name = f"subnet-{random_data(length=4)}"
        vgw_name = f"vgw-{random_data(length=4)}"

        with allure_step_log("步骤0: 创建虚拟私有云"):
            vpc_page.vpc_create(
                name=vpc_name,
                subnet_name=subnet_name,
                cidr="13.34.34.0/24",
            )
            vpc_page.assert_status(vpc_name, status="运行中")

        with allure_step_log("步骤1: 创建虚拟网关"):
            dc_page.virtual_gateway_create(
                name=vgw_name,
                vpc_name=vpc_name,
            )

        with allure_step_log("步骤2: 验证列表页"):
            dc_page.assert_popup_success(timeout=10000)
            dc_page.assert_list_contain(vgw_name, column_name="名称")
            dc_page.assert_status(vgw_name, status="运行中")

            # 验证关联模式和资源名称
            row_data = dc_page.get_row_data(vgw_name)
            association_mode = row_data.get("关联模式", "")
            resource_name = row_data.get("资源名称", "")
            assert "虚拟私有云" in association_mode, f"关联模式不匹配: 期望虚拟私有云, 实际 {association_mode}"
            assert vpc_name in resource_name, f"资源名称不匹配: 期望包含 {vpc_name}, 实际 {resource_name}"

        with allure_step_log("步骤3: 删除虚拟网关"):
            dc_page.virtual_gateway_delete(vgw_name)
            dc_page.assert_deleted(vgw_name, timeout=60)

        with allure_step_log("步骤4: 删除虚拟私有云"):
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.vpc_delete(vpc_name)
            vpc_page.assert_deleted(vpc_name, timeout=60)

    @allure.title("云专线DC-虚拟接口-新建功能验证")
    def test_virtual_interface_create(self, dc_page, vpc_page):
        """测试虚拟接口的完整生命周期：创建VPC、创建物理连接、审批、创建虚拟网关、
        创建虚拟接口、验证状态、清理资源。"""

        vpc_name = f"vpc-{random_data(length=4)}"
        subnet_name = f"subnet-{random_data(length=4)}"
        dc_name = f"physical-{random_data(length=4)}"
        vgw_name = f"vgw-{random_data(length=4)}"
        vif_name = f"vif-{random_data(length=4)}"
        operator = "unicom"
        port_type = "10GE 单模光口"
        contact_name = "张三"
        contact_phone = "13805403159"
        contact_email = "ll@sugon.com"
        vlan_code = "205"

        with allure_step_log("步骤0: 创建虚拟私有云"):
            vpc_page.vpc_create(
                name=vpc_name,
                subnet_name=subnet_name,
                cidr="13.34.34.0/24",
            )
            vpc_page.assert_status(vpc_name, status="运行中")

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

        with allure_step_log("步骤2: 等待物理连接状态变为办结"):
            dc_page.wait_for_physical_connection_status(
                name=dc_name,
                expected_status="办结",
                expected_vm_status="运行中",
                timeout=600,
                interval=10,
            )

        with allure_step_log("步骤3: 创建虚拟网关"):
            dc_page.virtual_gateway_create(
                name=vgw_name,
                vpc_name=vpc_name,
            )
            dc_page.assert_popup_success(timeout=10000)
            dc_page.assert_status(vgw_name, status="运行中")

        with allure_step_log("步骤3.5: 等待1分钟确保资源就绪"):
            time.sleep(60)

        with allure_step_log("步骤4: 创建虚拟接口"):
            dc_page.virtual_interface_create(
                name=vif_name,
                physical_connection_name=dc_name,
                virtual_gateway_name=vgw_name,
                local_gateway="11.22.0.2/24",
                remote_gateway="11.22.0.3/24",
                route_mode="static",
                remote_subnet="123.12.0.0/24",
                subnet_index=0,
            )
            dc_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤5: 等待并验证虚拟接口状态（最长150秒）"):
            dc_page.assert_status(
                vif_name,
                status="运行中",
                timeout=150,
                refresh=True,
                refresh_interval=10,
            )

            # 验证列表字段
            row_data = dc_page.get_row_data(vif_name)
            local_gw = row_data.get("本地网关", "")
            remote_gw = row_data.get("远端网关", "")
            assert "11.22.0.2/24" in local_gw, f"本地网关不匹配: 期望 11.22.0.2/24, 实际 {local_gw}"
            assert "11.22.0.3/24" in remote_gw, f"远端网关不匹配: 期望 11.22.0.3/24, 实际 {remote_gw}"

        with allure_step_log("步骤6: 清理资源"):
            # 等待15秒确保虚拟接口状态稳定后再删除
            time.sleep(15)

            # 删除虚拟接口
            dc_page.virtual_interface_delete(vif_name)
            dc_page.assert_deleted(vif_name, timeout=60)

            # 删除虚拟网关
            dc_page.virtual_gateway_delete(vgw_name)
            dc_page.assert_deleted(vgw_name, timeout=60)

            # 注销物理连接
            dc_page._ensure_physical_connection_list()
            dc_page.dc_physical_connection_terminate(dc_name)
            dc_page.assert_deleted(dc_name, timeout=60)

            # 删除虚拟私有云
            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.vpc_delete(vpc_name)
            vpc_page.assert_deleted(vpc_name, timeout=60)
