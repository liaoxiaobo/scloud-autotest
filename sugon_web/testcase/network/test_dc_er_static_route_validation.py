import re
import time

import pytest
import allure
from playwright.sync_api import expect

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
@allure.story('ER类型HA静态路由生效性验证')
class TestDCERStaticRouteValidation:

    @pytest.mark.parametrize(
        "vpc",
        [{"name": f"vpc-dc-er-route-{random_data(length=4)}", "subnet_name": f"subnet-dc-er-route-{random_data(length=4)}", "cidr": "13.34.34.0/24"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "vm",
        [{"basic": {"count": 1}, "bind_mfip": True, "name_prefix": "dc_"}],
        indirect=True,
    )
    @allure.title("云专线DC-ER类型HA静态路由生效性验证")
    def test_er_static_route_validation(self, vm, vpc, dc_page, vpc_page, er_page, ssh_vm):
        """测试ER类型HA静态路由生效性。

        前置条件（由脚本准备）：
        1. VPC+ECS（vm/vpc fixture自动创建）
        2. HA企业路由器，并将VPC添加为连接
        3. HA物理连接并审批通过（vlan=205）
        4. 虚拟网关关联ER（ER关联模式）
        5. 虚拟接口（静态路由模式，远端子网123.12.0.0/24）

        测试步骤：
        1. VPC下添加自定义路由（目的123.12.0.0/24，下一跳类型企业路由器）
        2. ER路由表添加规则（目的123.12.0.0/24，下一跳类型云专线）
        3. SSH连接vm1执行ping验证

        清理顺序：路由规则→虚拟接口→虚拟网关→物理连接→VPC路由→ER连接→ER→ECS→VPC
        （ECS和VPC由fixture teardown自动清理）
        """
        vpc_name = vpc["name"]
        vm_mfip = vm["mfip"]
        dc_name = f"physical-{random_data(length=4)}"
        vgw_name = f"vgw-{random_data(length=4)}"
        vif_name = f"vif-{random_data(length=4)}"
        er_name = f"er-dc-ha-{random_data(length=4)}"
        er_conn_name = f"conn-vpc-{random_data(length=4)}"
        dest_cidr = "123.12.0.0/24"
        cleanup_errors = []

        # ─────────────────────────────────────────────
        # 前置条件准备
        # ─────────────────────────────────────────────

        with allure_step_log("前置条件0: 清理残留资源（虚拟接口→虚拟网关→物理连接）"):
            _cleanup_residual_dc_resources(dc_page)

        with allure_step_log("前置条件1: 创建HA物理连接并审批通过"):
            dc_page.dc_physical_connection_create(
                name=dc_name,
                operator="unicom",
                port_type="10GE 单模光口",
                contact_name="张三",
                contact_phone="13805403159",
                contact_email="ll@sugon.com",
                ha_enable=True,
            )
            dc_page.assert_popup_success(timeout=10000)
            dc_page.assert_status(dc_name, status="办理中")

            dc_page.dc_physical_connection_approve(
                name=dc_name,
                status="DONE",
                vlan_code="205",
                cluster_name="Autotest",
            )
            dc_page.assert_popup_success(timeout=10000)

        with allure_step_log("前置条件2: 等待物理连接状态变为办结"):
            dc_page.wait_for_physical_connection_status(
                name=dc_name,
                expected_status="办结",
                expected_vm_status="运行中",
                timeout=600,
                interval=10,
            )

        with allure_step_log("前置条件3: 创建HA企业路由器"):
            er_page.er_create(
                name=er_name,
                cluster_name="Autotest",
                ha_enable=True,
            )
            er_page.assert_popup_success(timeout=10000)
            er_page.assert_status(er_name, status="运行中")

        with allure_step_log("前置条件4: 将VPC添加为ER连接"):
            er_page.goto_connection_tab(er_name)
            er_page.er_connection_create(
                name=er_conn_name,
                conn_type="VPC",
                vpc_name=vpc_name,
                subnet_name=vpc["subnet_name"],
            )
            er_page.assert_popup_success(timeout=10000)
            # 等待连接状态就绪
            er_page.page.wait_for_timeout(3000)

        with allure_step_log("前置条件5: 创建虚拟网关（ER关联模式）"):
            dc_page.virtual_gateway_create(
                name=vgw_name,
                association_mode="er",
                er_name=er_name,
            )
            dc_page.assert_popup_success(timeout=10000)
            dc_page.assert_status(vgw_name, status="运行中")

        with allure_step_log("前置条件6: 创建虚拟接口"):
            time.sleep(30)
            dc_page.virtual_interface_create(
                name=vif_name,
                physical_connection_name=dc_name,
                virtual_gateway_name=vgw_name,
                local_gateway="11.22.0.2/24",
                remote_gateway="11.22.0.3/24",
                route_mode="static",
                remote_subnet="123.12.0.0/24",
                local_subnet=vpc["cidr"],
                subnet_index=0,
            )
            dc_page.assert_popup_success(timeout=10000)

        with allure_step_log("前置条件6.5: 等待虚拟接口状态变为运行中"):
            dc_page.assert_status(
                vif_name,
                status="运行中",
                timeout=150,
                refresh=True,
                refresh_interval=10,
            )

        with allure_step_log("前置条件6.6: 等待5秒确保路由就绪"):
            time.sleep(5)

        # ─────────────────────────────────────────────
        # 测试步骤
        # ─────────────────────────────────────────────

        try:
            with allure_step_log("步骤1: 在VPC中添加自定义路由"):
                vpc_page.goto_service("虚拟私有云")
                vpc_page.goto_submenu("虚拟私有云")
                vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
                vpc_page.page.mouse.move(1, 1)
                vpc_page.get_by_role("tab", name="路由表").click()

                vpc_page.get_by_label("路由表", exact=True).get_by_text("新建").click()
                dialog = vpc_page.page.locator(".el-dialog__wrapper:visible")

                vpc_page.get_by_placeholder(re.compile(r"必填")).fill(dest_cidr)
                vpc_page.page.wait_for_timeout(1000)

                # 选择下一跳类型：企业路由器
                vpc_page.locator(".el-form-item").filter(
                    has=vpc_page.locator("label").filter(has_text="下一跳类型")
                ).get_by_placeholder("请选择").click()
                vpc_page.page.locator(".el-select-dropdown:visible").locator("li").filter(
                    has_text=re.compile(r"^企业路由器$")
                ).first.click()
                vpc_page.page.wait_for_timeout(2000)

                # 选择下一跳：ER实例
                vpc_page.locator(".el-form-item").filter(
                    has=vpc_page.locator("label").filter(has_text=re.compile(r"^下一跳$"))
                ).get_by_placeholder("请选择").click()

                dropdown = vpc_page.page.locator(".el-select-dropdown:visible")
                try:
                    dropdown.wait_for(state="visible", timeout=5000)
                    vpc_page.page.wait_for_timeout(2000)
                    option = dropdown.locator(".el-select-dropdown__item").filter(has_text=re.compile(re.escape(er_name))).first
                    option.scroll_into_view_if_needed(timeout=5000)
                    option.click(force=True)
                    logger.info(f"下一跳选择成功: {er_name}")
                except Exception:
                    logger.warning(f".el-select-dropdown__item 定位失败，降级使用 dropdown.get_by_text 选择: {er_name}")
                    dropdown.get_by_text(er_name, exact=True).last.click(force=True)

                vpc_page.get_by_label("新建路由表规则").get_by_text("确定").click()
                try:
                    expect(dialog).to_have_count(0, timeout=10000)
                except Exception:
                    pass

            with allure_step_log("步骤2: 验证VPC自定义路由"):
                vpc_page.page.reload()
                vpc_page.wait_for_page_ready()
                vpc_page.page.mouse.move(1, 1)
                vpc_page.get_by_role("tab", name="路由表").click()

                row_data = vpc_page.get_row_data(dest_cidr)
                actual_dest = row_data.get("目的地址", "")
                actual_type = row_data.get("下一跳类型", "")
                actual_next_hop = row_data.get("下一跳", "")
                actual_rule_type = row_data.get("类型", "")
                assert dest_cidr in actual_dest, f"目的地址不匹配"
                assert "企业路由器" in actual_type, f"下一跳类型不匹配"
                assert er_name in actual_next_hop, f"下一跳不匹配"
                assert "自定义" in actual_rule_type, f"类型不匹配"

            with allure_step_log("步骤3: 获取ER云专线连接名称"):
                er_page.goto_connection_tab(er_name)
                er_page.page.wait_for_timeout(3000)
                # 获取连接列表中类型为"云专线"的连接名称
                conn_names = er_page.get_column_data("名称")
                conn_types = er_page.get_column_data("连接类型")
                dc_conn_name = None
                for name, ctype in zip(conn_names, conn_types):
                    if "云专线" in ctype:
                        dc_conn_name = name
                        break
                if not dc_conn_name:
                    # 如果列名不同，尝试遍历所有行
                    rows = er_page.page.locator(".el-table__body-wrapper tbody tr").all()
                    for row in rows:
                        try:
                            cells = row.locator("td").all()
                            if len(cells) >= 3:
                                name_text = cells[1].text_content(timeout=2000).strip()
                                type_text = cells[2].text_content(timeout=2000).strip()
                                if "云专线" in type_text:
                                    dc_conn_name = name_text
                                    break
                        except Exception:
                            continue
                assert dc_conn_name, "未找到云专线类型的ER连接"
                logger.info(f"找到云专线连接名称: {dc_conn_name}")

            with allure_step_log("步骤4: 在ER路由表中添加规则"):
                er_page.goto_route_table_tab(er_name)
                er_page.er_route_rule_create(
                    destination=dest_cidr,
                    next_hop_type="云专线",
                    connection=dc_conn_name,
                    next_hop=dc_name,
                )
                er_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤5: 验证ER路由表规则"):
                # 截图记录创建后的页面状态
                screenshot_path = f"screenshots/test_er_route_rule_created_{int(time.time())}.png"
                er_page.page.screenshot(path=screenshot_path)
                allure.attach.file(screenshot_path, name="路由规则创建后页面截图", attachment_type=allure.attachment_type.PNG)

                # 刷新并等待规则显示，最多等待90秒，每15秒刷新一次（规则同步需要较长时间）
                rule_found = False
                for i in range(7):
                    if i > 0:
                        er_page.page.reload()
                        er_page.wait_for_page_ready()
                        # reload后重新进入路由表tab（Vue详情页会回到默认tab）
                        er_page.goto_route_table_tab(er_name)
                        er_page.page.wait_for_timeout(3000)
                    else:
                        # 首次验证，已在路由表tab，只需等待
                        er_page.page.wait_for_timeout(3000)

                    try:
                        row_data = er_page.get_row_data(dest_cidr)
                        actual_dest = row_data.get("目的地址", "")
                        actual_type = row_data.get("下一跳类型", "")
                        actual_next_hop = row_data.get("下一跳", "")
                        logger.info(f"第{i+1}轮路由表数据: {row_data}")
                        if dest_cidr in actual_dest and "云专线" in actual_type and dc_name in actual_next_hop:
                            rule_found = True
                            logger.info(f"ER路由表规则验证成功: {row_data}")
                            break
                    except Exception as e:
                        logger.info(f"第{i+1}轮未找到路由规则，继续刷新等待: {e}")
                    er_page.page.wait_for_timeout(10000)
                assert rule_found, f"ER路由表中未找到目的地址为 {dest_cidr} 的规则"

            with allure_step_log("步骤6: SSH连接vm1验证静态路由生效"):
                ssh_vm.connect(vm_mfip)

                ip_result = ssh_vm.run("ip ad", return_stdout=True)
                ping_result = ssh_vm.run("ping -c 4 123.12.0.10", return_rc=True, return_stdout=True)

                separator = "=" * 60
                logger.info(f"\n{separator}")
                logger.info(f"ip ad 输出 (VM: {vm_mfip}):")
                logger.info(f"{ip_result}")
                logger.info(f"{separator}")
                logger.info(f"ping -c 4 123.12.0.10 输出:")
                logger.info(f"{ping_result['stdout']}")
                logger.info(f"返回码 rc={ping_result['rc']}")
                logger.info(f"{separator}")

                combined_output = f"=== ip ad (来自 VM {vm_mfip}) ===\n{ip_result}\n\n=== ping -c 4 123.12.0.10 ===\n{ping_result['stdout']}\nrc={ping_result['rc']}"
                allure.attach(combined_output, name="SSH验证结果", attachment_type=allure.attachment_type.TEXT)

                assert ping_result["rc"] == 0, f"ping命令执行失败"
                # 放宽丢包容忍：允许首次丢包（路由刚建立时的ARP/MAC学习延迟），重试一次
                if not ("4 packets transmitted, 4 received" in ping_result["stdout"]
                        or "0% packet loss" in ping_result["stdout"]):
                    logger.warning("首次ping存在丢包，等待10秒后重试...")
                    time.sleep(10)
                    ping_result = ssh_vm.run("ping -c 4 123.12.0.10", return_rc=True, return_stdout=True)
                    logger.info(f"重试ping结果: rc={ping_result['rc']}, stdout={ping_result['stdout']}")
                assert ping_result["rc"] == 0, f"ping命令执行失败"
                assert (
                    "4 packets transmitted, 4 received" in ping_result["stdout"]
                    or "0% packet loss" in ping_result["stdout"]
                ), f"ping未全部通过"

                screenshot_path = f"screenshots/test_er_static_route_validation_ping_{int(time.time())}.png"
                vpc_page.page.screenshot(path=screenshot_path)
                allure.attach.file(screenshot_path, name="路由表页面截图", attachment_type=allure.attachment_type.PNG)

        finally:
            # ─────────────────────────────────────────────
            # 清理数据（按正确顺序，清理失败收集后统一抛出）
            # ─────────────────────────────────────────────

            with allure_step_log("清理准备: 关闭可能存在的弹窗"):
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
                try:
                    notifications = dc_page.page.locator(".el-notification__closeBtn")
                    for i in range(notifications.count()):
                        notifications.nth(i).click()
                        dc_page.page.wait_for_timeout(300)
                except Exception:
                    pass

            with allure_step_log("清理1: 删除虚拟接口"):
                try:
                    dc_page._ensure_virtual_interface_list()
                    dc_page.page.wait_for_timeout(2000)
                    try:
                        dc_page.get_row_by_name(vif_name)
                    except Exception:
                        logger.info(f"虚拟接口 {vif_name} 已不存在或已被级联删除，跳过")
                    else:
                        dc_page.virtual_interface_delete(vif_name)
                        dc_page.assert_deleted(vif_name, timeout=60)
                except Exception as e:
                    cleanup_errors.append(f"删除虚拟接口: {e}")

            with allure_step_log("清理2: 删除虚拟网关"):
                try:
                    dc_page._ensure_virtual_gateway_list()
                    dc_page.page.wait_for_timeout(2000)
                    dc_page.virtual_gateway_delete(vgw_name)
                    dc_page.assert_deleted(vgw_name, timeout=60)
                except Exception as e:
                    cleanup_errors.append(f"删除虚拟网关: {e}")

            with allure_step_log("清理3: 注销物理连接"):
                try:
                    dc_page._ensure_physical_connection_list()
                    dc_page.page.wait_for_timeout(2000)
                    dc_page.dc_physical_connection_terminate(dc_name)
                    dc_page.assert_deleted(dc_name, timeout=60)
                except Exception as e:
                    cleanup_errors.append(f"注销物理连接: {e}")

            with allure_step_log("清理4: 删除VPC自定义路由"):
                try:
                    vpc_page.goto_service("虚拟私有云")
                    vpc_page.goto_submenu("虚拟私有云")
                    vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
                    vpc_page.page.mouse.move(1, 1)
                    vpc_page.get_by_role("tab", name="路由表").click()
                    try:
                        vpc_page.click_action(dest_cidr, "删除")
                        vpc_page.dialog_confirm.click()
                        vpc_page.assert_deleted(dest_cidr, timeout=30)
                    except Exception:
                        logger.info(f"路由规则 {dest_cidr} 已不存在或已被自动清理，跳过删除")
                except Exception as e:
                    cleanup_errors.append(f"删除VPC路由规则: {e}")

            with allure_step_log("清理5: 删除ER的所有剩余连接"):
                try:
                    er_page.goto_connection_tab(er_name)
                    er_page.page.wait_for_timeout(3000)
                    # 遍历并删除所有剩余连接（包括VPC连接）
                    for _ in range(5):
                        rows = er_page.page.locator(".el-table__body-wrapper tbody tr").all()
                        deleted_any = False
                        for row in rows:
                            try:
                                cells = row.locator("td").all()
                                if len(cells) >= 2:
                                    conn_name = cells[1].text_content(timeout=2000).strip()
                                    if conn_name and conn_name != "名称":
                                        logger.info(f"删除ER连接: {conn_name}")
                                        er_page.er_connection_delete(conn_name)
                                        er_page.page.wait_for_timeout(2000)
                                        deleted_any = True
                                        break
                            except Exception:
                                continue
                        if not deleted_any:
                            break
                        er_page.page.wait_for_timeout(3000)
                except Exception as e:
                    cleanup_errors.append(f"删除ER连接: {e}")

            with allure_step_log("清理6: 删除ER实例"):
                try:
                    er_page.er_delete(er_name)
                    er_page.assert_deleted(er_name, timeout=60)
                except Exception as e:
                    cleanup_errors.append(f"删除ER实例: {e}")

            if cleanup_errors:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")
