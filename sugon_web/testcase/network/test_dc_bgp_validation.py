import re
import time

import pytest
import allure
from playwright.sync_api import expect

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('云专线DC')
@allure.story('BGP生效性验证')
class TestDCBgpValidation:

    @pytest.mark.parametrize(
        "vpc",
        [{"name": f"vpc-dc-bgp-{random_data(length=4)}", "subnet_name": f"subnet-dc-bgp-{random_data(length=4)}", "cidr": "173.173.173.0/24"}],
        indirect=True,
    )
    @pytest.mark.parametrize(
        "vm",
        [{"basic": {"count": 1}, "bind_mfip": True}],
        indirect=True,
    )
    @allure.title("云专线DC-BGP生效性验证")
    def test_bgp_validation(self, vm, vpc, dc_page, vpc_page, ssh_vm):
        """测试BGP路由生效性。

        前置条件（由脚本准备）：
        1. VPC+ECS（vm/vpc fixture自动创建）
        2. HA物理连接并审批通过（vlan=705）
        3. 虚拟网关关联VPC，BGP ASN=10000
        4. 虚拟接口（BGP模式，邻居AS=65533，MD5=123123）

        测试步骤：
        1. 进入VPC详情页路由表tab
        2. 创建自定义路由（目的地址10.9.9.0/24，下一跳类型云专线）
        3. 验证路由规则列表字段
        4. SSH连接vm1执行ping和ip ad验证

        清理顺序：路由规则→虚拟接口→虚拟网关→物理连接→ECS→VPC
        （ECS和VPC由fixture teardown自动清理）
        """
        vpc_name = vpc["name"]
        vm_mfip = vm["mfip"]
        dc_name = f"physical-{random_data(length=4)}"
        vgw_name = f"vgw-{random_data(length=4)}"
        vif_name = f"vif-{random_data(length=4)}"
        dest_cidr = "10.9.9.0/24"
        cleanup_errors = []

        # ─────────────────────────────────────────────
        # 前置条件准备
        # ─────────────────────────────────────────────

        with allure_step_log("前置条件0: 检查并清理残留物理连接"):
            dc_page._ensure_physical_connection_list()
            dc_page.page.wait_for_timeout(3000)
            try:
                rows = dc_page.page.locator(".el-table__body-wrapper tbody tr").all()
                for row in rows:
                    try:
                        name_cell = row.locator("td").nth(1)
                        name_text = name_cell.text_content(timeout=5000)
                        if name_text and name_text.strip():
                            res_name = name_text.strip().split()[0]
                            if res_name and res_name != "名称":
                                logger.info(f"发现残留物理连接: {res_name}，执行注销")
                                try:
                                    dc_page.dc_physical_connection_terminate(res_name)
                                    dc_page.assert_deleted(res_name, timeout=60)
                                    logger.info(f"残留物理连接 {res_name} 注销成功")
                                except Exception as e:
                                    logger.warning(f"注销残留物理连接 {res_name} 失败: {e}")
                    except Exception:
                        break
            except Exception as e:
                logger.warning(f"检查残留物理连接时出错: {e}")
            dc_page.page.reload()
            dc_page.wait_for_page_ready()

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
                vlan_code="705",
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

        with allure_step_log("前置条件3: 创建虚拟网关（BGP ASN=10000）"):
            dc_page.virtual_gateway_create(
                name=vgw_name,
                vpc_name=vpc_name,
                bgp_asn="10000",
            )
            dc_page.assert_popup_success(timeout=10000)
            dc_page.assert_status(vgw_name, status="运行中")

        with allure_step_log("前置条件4: 创建虚拟接口（BGP模式）"):
            time.sleep(30)
            dc_page.virtual_interface_create(
                name=vif_name,
                physical_connection_name=dc_name,
                virtual_gateway_name=vgw_name,
                local_gateway="172.22.29.100/24",
                remote_gateway="172.22.29.254/24",
                route_mode="bgp",
                bgp_peer_asn="65533",
                bgp_md5_password="123123",
                subnet_index=0,
            )
            dc_page.assert_popup_success(timeout=10000)

        with allure_step_log("前置条件4.5: 等待虚拟接口状态变为运行中"):
            dc_page.assert_status(
                vif_name,
                status="运行中",
                timeout=150,
                refresh=True,
                refresh_interval=10,
            )

        # ─────────────────────────────────────────────
        # 测试步骤
        # ─────────────────────────────────────────────

        try:
            with allure_step_log("步骤1: 进入VPC详情页路由表tab"):
                vpc_page.goto_service("虚拟私有云")
                vpc_page.goto_submenu("虚拟私有云")
                vpc_page.get_row_by_name(vpc_name).locator("a").first.click()
                vpc_page.page.mouse.move(1, 1)
                vpc_page.get_by_role("tab", name="路由表").click()

            with allure_step_log("步骤2: 创建自定义路由规则"):
                vpc_page.get_by_label("路由表", exact=True).get_by_text("新建").click()
                dialog = vpc_page.page.locator(".el-dialog__wrapper:visible")

                vpc_page.get_by_placeholder(re.compile(r"必填")).fill(dest_cidr)

                vpc_page.locator(".el-form-item").filter(
                    has=vpc_page.locator("label").filter(has_text="下一跳类型")
                ).get_by_placeholder("请选择").click()
                vpc_page.page.locator(".el-select-dropdown:visible").locator("li").filter(
                    has_text=re.compile(r"^云专线$")
                ).first.click()

                vpc_page.locator(".el-form-item").filter(
                    has=vpc_page.locator("label").filter(has_text=re.compile(r"^下一跳$"))
                ).get_by_placeholder("请选择").click()
                vpc_page.page.wait_for_timeout(2000)

                # 下拉框选项选择（带多层降级）
                dropdown = vpc_page.page.locator(".el-select-dropdown:visible")
                try:
                    dropdown.wait_for(state="visible", timeout=5000)
                    option = dropdown.locator(".el-select-dropdown__item").filter(has_text=dc_name).first
                    expect(option).to_be_visible(timeout=5000)
                    option.click(force=True)
                    logger.info(f"下一跳选择成功: {dc_name} (通过 .el-select-dropdown__item)")
                except Exception:
                    # 降级方案1：限定在可见下拉框内搜索
                    logger.warning(f".el-select-dropdown__item 定位失败，降级使用可见下拉框内搜索: {dc_name}")
                    try:
                        vpc_page.page.locator(".el-select-dropdown:visible").get_by_text(dc_name, exact=False).first.click(force=True)
                    except Exception:
                        # 降级方案2：键盘选择（先聚焦input确保事件发送到正确元素）
                        logger.warning(f"可见下拉框内搜索失败，使用键盘选择: {dc_name}")
                        input_el = vpc_page.locator(".el-form-item").filter(
                            has=vpc_page.locator("label").filter(has_text=re.compile(r"^下一跳$"))
                        ).locator(".el-input__inner").first
                        input_el.click()
                        vpc_page.page.wait_for_timeout(500)
                        vpc_page.page.keyboard.press("ArrowDown")
                        vpc_page.page.wait_for_timeout(500)
                        vpc_page.page.keyboard.press("Enter")

                vpc_page.get_by_label("新建路由表规则").get_by_text("确定").click()

            with allure_step_log("步骤3: 验证路由规则列表"):
                # 增加重试：页面刷新后数据可能未立即加载
                row_data = None
                for attempt in range(3):
                    vpc_page.page.reload()
                    vpc_page.wait_for_page_ready()
                    vpc_page.page.mouse.move(1, 1)
                    vpc_page.get_by_role("tab", name="路由表").click()
                    vpc_page.page.wait_for_timeout(3000)
                    try:
                        row_data = vpc_page.get_row_data(dest_cidr)
                        if row_data:
                            break
                    except AssertionError:
                        logger.warning(f"第 {attempt + 1} 次查找路由规则 {dest_cidr} 失败，重试中...")
                        if attempt == 2:
                            raise
                        vpc_page.page.wait_for_timeout(5000)

                actual_dest = row_data.get("目的地址", "")
                actual_type = row_data.get("下一跳类型", "")
                actual_next_hop = row_data.get("下一跳", "")
                actual_rule_type = row_data.get("类型", "")
                assert dest_cidr in actual_dest, f"目的地址不匹配"
                assert "云专线" in actual_type, f"下一跳类型不匹配"
                assert dc_name in actual_next_hop, f"下一跳不匹配"
                assert "自定义" in actual_rule_type, f"类型不匹配"

            with allure_step_log("步骤4: SSH连接vm1验证BGP路由生效"):
                ssh_vm.connect(vm_mfip)

                # 执行 ip ad 查看网络接口
                ip_result = ssh_vm.run("ip ad", return_stdout=True)

                # 执行 ping
                ping_result = ssh_vm.run("ping -c 4 10.9.9.9", return_rc=True, return_stdout=True)

                # 合并输出并附加到 Allure 报告
                combined_output = (
                    f"=== ip ad (来自 VM {vm_mfip}) ===\n"
                    f"{ip_result}\n\n"
                    f"=== ping -c 4 10.9.9.9 ===\n"
                    f"{ping_result['stdout']}\n"
                    f"rc={ping_result['rc']}"
                )
                allure.attach(
                    combined_output,
                    name="SSH验证结果",
                    attachment_type=allure.attachment_type.TEXT,
                )

                logger.info(f"ping结果: rc={ping_result['rc']}, stdout={ping_result['stdout']}")
                assert ping_result["rc"] == 0, f"ping命令执行失败"
                assert (
                    "4 packets transmitted, 4 received" in ping_result["stdout"]
                    or "0% packet loss" in ping_result["stdout"]
                ), f"ping未全部通过"

                # 浏览器端截图：路由表页面
                screenshot_path = f"screenshots/test_bgp_validation_ping_{int(time.time())}.png"
                vpc_page.page.screenshot(path=screenshot_path)
                allure.attach.file(
                    screenshot_path,
                    name="路由表页面截图",
                    attachment_type=allure.attachment_type.PNG,
                )

        finally:
            # ─────────────────────────────────────────────
            # 清理数据（按正确顺序，清理失败收集后统一抛出）
            # ─────────────────────────────────────────────

            # 关闭可能存在的弹窗/对话框，防止级联拦截
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

            with allure_step_log("清理1: 删除自定义路由"):
                try:
                    vpc_page.goto_service("虚拟私有云")
                    vpc_page.goto_submenu("虚拟私有云")
                    try:
                        row = vpc_page.get_row_by_name(vpc_name)
                    except Exception:
                        logger.warning(f"VPC {vpc_name} 未找到，可能已被自动清理，跳过路由规则删除")
                    else:
                        row.locator("a").first.click()
                        vpc_page.page.mouse.move(1, 1)
                        try:
                            vpc_page.get_by_role("tab", name="路由表").click()
                            vpc_page.click_action(dest_cidr, "删除")
                            vpc_page.dialog_confirm.click()
                            vpc_page.assert_deleted(dest_cidr, timeout=30)
                        except Exception:
                            logger.info(f"路由规则 {dest_cidr} 已不存在或已被自动清理，跳过删除")
                except Exception as e:
                    cleanup_errors.append(f"删除路由规则: {e}")

            with allure_step_log("清理2: 删除虚拟接口"):
                try:
                    dc_page._ensure_virtual_interface_list()
                    dc_page.virtual_interface_delete(vif_name)
                    dc_page.assert_deleted(vif_name, timeout=60)
                except Exception as e:
                    cleanup_errors.append(f"删除虚拟接口: {e}")

            with allure_step_log("清理3: 删除虚拟网关"):
                try:
                    dc_page._ensure_virtual_gateway_list()
                    dc_page.virtual_gateway_delete(vgw_name)
                    dc_page.assert_deleted(vgw_name, timeout=60)
                except Exception as e:
                    cleanup_errors.append(f"删除虚拟网关: {e}")

            with allure_step_log("清理4: 注销物理连接"):
                try:
                    dc_page._ensure_physical_connection_list()
                    dc_page.dc_physical_connection_terminate(dc_name)
                    dc_page.assert_deleted(dc_name, timeout=60)
                except Exception as e:
                    cleanup_errors.append(f"注销物理连接: {e}")

            if cleanup_errors:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")
