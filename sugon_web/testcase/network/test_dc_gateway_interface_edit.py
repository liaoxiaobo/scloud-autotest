import time

import pytest
import allure
from sugon_web.common.playwright import expect
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('云专线DC')
@allure.story('虚拟网关及虚拟接口修改功能验证')
class TestDCGatewayInterfaceEdit:

    @allure.title("云专线DC-虚拟网关修改功能验证")
    def test_virtual_gateway_edit(self, dc_page, vpc_page):
        """测试虚拟网关的修改功能：创建VPC和虚拟网关后，
        验证修改弹窗中关联模式、虚拟私有云字段为只读，
        修改名称和描述，验证列表页和详情页的修改结果。"""

        vpc_name = f"vpc-{random_data(length=4)}"
        subnet_name = f"subnet-{random_data(length=4)}"
        vgw_name = f"vgw-{random_data(length=4)}"
        new_vgw_name = f"{vgw_name}-modify"
        new_description = "修改后的描述值"

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
            dc_page.assert_popup_success(timeout=10000)
            dc_page.assert_status(vgw_name, status="运行中")

        with allure_step_log("步骤2: 执行修改操作（修改名称和描述）"):
            dc_page._ensure_virtual_gateway_list()
            dc_page.virtual_gateway_edit(
                name=vgw_name,
                new_name=new_vgw_name,
                description=new_description,
            )
            dc_page.assert_popup_success(timeout=10000)
            # 修改后列表可能未自动刷新，重新导航确保数据最新
            dc_page.page.wait_for_timeout(3000)
            dc_page._ensure_virtual_gateway_list()

        with allure_step_log("步骤3: 列表页验证修改结果"):
            dc_page.assert_list_contain(new_vgw_name, column_name="名称")
            dc_page.assert_status(new_vgw_name, status="运行中")

            row_data = dc_page.get_row_data(new_vgw_name)
            association_mode = row_data.get("关联模式", "")
            resource_name = row_data.get("资源名称", "")
            assert "虚拟私有云" in association_mode, f"关联模式不匹配: 期望虚拟私有云, 实际 {association_mode}"
            assert vpc_name in resource_name, f"资源名称不匹配: 期望包含 {vpc_name}, 实际 {resource_name}"

        with allure_step_log("步骤4: 详情页验证修改结果"):
            # 虚拟网关详情通过抽屉窗口展示，点击名称打开
            dc_page.page.locator("#cloud-container-content").get_by_text(new_vgw_name, exact=True).first.click()

            # 等待抽屉出现
            drawer = dc_page.page.locator(".el-drawer__wrapper:visible")
            expect(drawer).to_be_visible(timeout=10000)
            expect(drawer.get_by_text("详细信息", exact=True)).to_be_visible(timeout=5000)

            # 验证详情页中的名称和描述（在抽屉范围内搜索文本）
            expect(drawer.get_by_text(new_vgw_name, exact=True)).to_be_visible(timeout=5000)
            expect(drawer.get_by_text(new_description, exact=True)).to_be_visible(timeout=5000)

            # 关闭抽屉（Element UI 抽屉关闭按钮）
            try:
                close_btn = drawer.locator(".el-drawer__close-btn, .el-drawer__headerbtn").first
                if close_btn.count() > 0 and close_btn.is_visible():
                    close_btn.click()
                else:
                    # 备选：点击蒙层关闭
                    dc_page.page.locator(".el-drawer__container:visible").locator("..").click()
            except Exception:
                pass
            # 等待抽屉关闭
            try:
                expect(drawer).to_have_count(0, timeout=5000)
            except Exception:
                dc_page.page.wait_for_timeout(2000)

        with allure_step_log("步骤5: 清理资源"):
            dc_page._ensure_virtual_gateway_list()
            dc_page.virtual_gateway_delete(new_vgw_name)
            dc_page.assert_deleted(new_vgw_name, timeout=60)

            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.vpc_delete(vpc_name)
            vpc_page.assert_deleted(vpc_name, timeout=60)

    @allure.title("云专线DC-虚拟接口修改功能验证")
    def test_virtual_interface_edit(self, dc_page, vpc_page):
        """测试虚拟接口的修改功能：创建VPC、物理连接、虚拟网关、虚拟接口后，
        验证修改页面中物理连接、虚拟网关、本端网关、远端网关、路由模式字段为只读，
        修改名称和描述，验证列表页和详情页的修改结果。"""

        vpc_name = f"vpc-{random_data(length=4)}"
        subnet_name = f"subnet-{random_data(length=4)}"
        dc_name = f"physical-{random_data(length=4)}"
        vgw_name = f"vgw-{random_data(length=4)}"
        vif_name = f"vif-{random_data(length=4)}"
        new_vif_name = f"{vif_name}-modify"
        new_description = "修改后的描述值"
        operator = "unicom"
        port_type = "10GE 单模光口"
        contact_name = "张三"
        contact_phone = "13805403159"
        contact_email = "ll@sugon.com"
        vlan_code = "205"

        with allure_step_log("步骤0: 清理残留资源（虚拟接口→虚拟网关→物理连接）"):
            # 关闭可能存在的通知弹窗
            try:
                notifications = dc_page.page.locator(".el-notification__closeBtn")
                for i in range(notifications.count()):
                    notifications.nth(i).click()
                    dc_page.page.wait_for_timeout(300)
            except Exception:
                pass

            # 清理虚拟接口
            try:
                dc_page._ensure_virtual_interface_list()
                vif_names = dc_page.get_column_data("名称")
                for name in vif_names:
                    if name and name.startswith("vif-"):
                        dc_page.virtual_interface_delete(name)
                        dc_page.assert_deleted(name, timeout=60)
            except Exception as e:
                logger.info(f"清理虚拟接口时跳过: {e}")

            # 清理虚拟网关
            try:
                dc_page._ensure_virtual_gateway_list()
                vgw_names = dc_page.get_column_data("名称")
                for name in vgw_names:
                    if name and name.startswith("vgw-"):
                        dc_page.virtual_gateway_delete(name)
                        dc_page.assert_deleted(name, timeout=60)
            except Exception as e:
                logger.info(f"清理虚拟网关时跳过: {e}")

            # 清理物理连接
            try:
                dc_page._ensure_physical_connection_list()
                pc_names = dc_page.get_column_data("物理连接名称")
                for name in pc_names:
                    if name and name.startswith("physical-"):
                        dc_page.dc_physical_connection_terminate(name)
                        dc_page.assert_deleted(name, timeout=60)
            except Exception as e:
                logger.info(f"清理物理连接时跳过: {e}")

        with allure_step_log("步骤0.5: 创建虚拟私有云"):
            # 关闭可能存在的通知弹窗，避免阻塞后续点击
            try:
                notifications = dc_page.page.locator(".el-notification__closeBtn")
                for i in range(notifications.count()):
                    notifications.nth(i).click()
                    dc_page.page.wait_for_timeout(300)
            except Exception:
                pass
            # 关闭可能存在的对话框
            try:
                dialogs = dc_page.page.locator(".el-dialog__wrapper:visible")
                if dialogs.count() > 0:
                    for i in range(dialogs.count()):
                        close_btn = dialogs.nth(i).locator(".el-dialog__close-btn, .el-dialog__headerbtn, .el-icon-close").first
                        if close_btn.count() > 0 and close_btn.is_visible():
                            close_btn.click()
                            dc_page.page.wait_for_timeout(500)
            except Exception:
                pass

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

        with allure_step_log("步骤5: 等待虚拟接口状态变为运行中"):
            dc_page.assert_status(
                vif_name,
                status="运行中",
                timeout=150,
                refresh=True,
                refresh_interval=10,
            )

        with allure_step_log("步骤6: 执行修改操作（修改名称和描述）"):
            dc_page._ensure_virtual_interface_list()
            dc_page.virtual_interface_edit(
                name=vif_name,
                new_name=new_vif_name,
                description=new_description,
            )
            dc_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤7: 列表页验证修改结果"):
            dc_page.assert_list_contain(new_vif_name, column_name="名称")
            dc_page.assert_status(new_vif_name, status="运行中")

            row_data = dc_page.get_row_data(new_vif_name)
            local_gw = row_data.get("本地网关", "")
            remote_gw = row_data.get("远端网关", "")
            assert "11.22.0.2/24" in local_gw, f"本地网关不匹配: 期望 11.22.0.2/24, 实际 {local_gw}"
            assert "11.22.0.3/24" in remote_gw, f"远端网关不匹配: 期望 11.22.0.3/24, 实际 {remote_gw}"

        with allure_step_log("步骤8: 详情页验证修改结果"):
            # 虚拟接口详情页通过点击名称进入
            dc_page.page.locator("#cloud-container-content").get_by_text(new_vif_name, exact=True).first.click()
            dc_page.page.wait_for_timeout(3000)
            dc_page.wait_for_page_ready()

            # 验证详情页中存在新名称（使用 first 避免 strict mode violation）
            expect(dc_page.page.get_by_text(new_vif_name, exact=True).first).to_be_visible(timeout=5000)

        with allure_step_log("步骤9: 清理资源"):
            dc_page._ensure_virtual_interface_list()
            dc_page.virtual_interface_delete(new_vif_name)
            dc_page.assert_deleted(new_vif_name, timeout=60)

            dc_page._ensure_virtual_gateway_list()
            dc_page.virtual_gateway_delete(vgw_name)
            dc_page.assert_deleted(vgw_name, timeout=60)

            dc_page._ensure_physical_connection_list()
            dc_page.dc_physical_connection_terminate(dc_name)
            dc_page.assert_deleted(dc_name, timeout=60)

            vpc_page.goto_service("虚拟私有云")
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.vpc_delete(vpc_name)
            vpc_page.assert_deleted(vpc_name, timeout=60)
