import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.util import random_data
from sugon_web.config.config import Config


def _create_vm_and_bind_mfip(ecs_page, ops_page, vm_name, vpc_name, subnet_name, cluster_name):
    """创建VM并绑定MFIP，返回VM信息字典。"""
    storage_pool = f"{Config.get('stor', 'xstor')}-test"
    image_name = f"{Config.get('stor', 'xstor')}-test"

    ecs_page.goto_service("弹性云服务器")
    ecs_page.close_dialog_if_exists()
    ecs_page.wait_for_page_ready()
    ecs_page.ecs_create(
        basic={"name": vm_name, "count": 1, "cluster": cluster_name, "flavor": {"base": "ecs.c6.Autotest"}},
        storage={"storage_pool": storage_pool, "image": {"source": "镜像", "name": image_name}, "system_disk": 25},
        network={"networks": [{"network": vpc_name, "subnet": subnet_name}]},
        manage={"login_type": "密码登录", "login_pwd": "admin1234@sugon", "vnc_pwd": "sugon@20"},
    )
    ecs_page.assert_popup_success()
    ecs_page.assert_status(vm_name, timeout=300, refresh=True, refresh_interval=30)

    vm_data = ecs_page.get_row_data(vm_name)
    vm_ip = vm_data["IP地址"].split("固定: ")[-1].strip()

    ops_page.close_dialog_if_exists()
    ops_page.goto_service("基础设施")
    ops_page.close_dialog_if_exists()
    ops_page.wait_for_page_ready()
    ops_page.goto_submenu("平台网络")
    ops_page.mfip_create("默认项目", vpc_name, vm_ip)
    ops_page.assert_popup_success()
    ops_page.mfip_search(vm_ip)
    vm_mfip = ops_page.get_row_data(vm_ip).get("管理IP地址")

    return {"name": vm_name, "ip": vm_ip, "mfip": vm_mfip}


@allure.epic('网络服务')
@allure.feature('企业路由器')
@allure.story('连接生效性验证')
class TestERVPCConnectivity:

    @allure.title("企业路由器-HA-连接VPC-生效性验证")
    def test_er_vpc_connectivity(self, er_page, vpc_page, ecs_page, ops_page, ssh_vm, ssh_host):
        """测试HA ER打通两个VPC后的连通性：创建VPC和VM、添加ER连接、配置路由、双向ping验证。"""
        vpc1_name = f"er-vpc1-{random_data(length=4)}"
        vpc2_name = f"er-vpc2-{random_data(length=4)}"
        subnet1_name = f"subnet1-{random_data(length=4)}"
        subnet2_name = f"subnet2-{random_data(length=4)}"
        vm1_name = f"er-vm1-{random_data(length=4)}"
        vm2_name = f"er-vm2-{random_data(length=4)}"
        er_name = f"er-ha-{random_data(length=4)}"
        conn1_name = f"conn-vpc1-{random_data(length=4)}"
        conn2_name = f"conn-vpc2-{random_data(length=4)}"
        cluster_name = "Autotest"
        main_error = None
        cleanup_errors = []

        try:
            with allure_step_log("步骤1: 创建VPC1"):
                vpc_page.goto_service("虚拟私有云")
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                vpc_page.vpc_create(
                    name=vpc1_name,
                    subnet_name=subnet1_name,
                    cidr="173.3.3.0/24",
                    cluster=cluster_name,
                )
                vpc_page.assert_popup_success("创建虚拟私有云成功")
                vpc_page.assert_status(vpc1_name)
                logger.info(f"VPC1 {vpc1_name} 创建成功")

            with allure_step_log("步骤2: 创建VM1并绑定MFIP"):
                vm1_info = _create_vm_and_bind_mfip(ecs_page, ops_page, vm1_name, vpc1_name, subnet1_name, cluster_name)
                vm1_ip = vm1_info["ip"]
                vm1_mfip = vm1_info["mfip"]
                logger.info(f"VM1创建成功: name={vm1_name}, ip={vm1_ip}, mfip={vm1_mfip}")

            with allure_step_log("步骤3: 创建VPC2"):
                vpc_page.goto_service("虚拟私有云")
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                vpc_page.vpc_create(
                    name=vpc2_name,
                    subnet_name=subnet2_name,
                    cidr="174.4.4.0/24",
                    cluster=cluster_name,
                )
                vpc_page.assert_popup_success("创建虚拟私有云成功")
                vpc_page.assert_status(vpc2_name)
                logger.info(f"VPC2 {vpc2_name} 创建成功")

            with allure_step_log("步骤4: 创建VM2并绑定MFIP"):
                vm2_info = _create_vm_and_bind_mfip(ecs_page, ops_page, vm2_name, vpc2_name, subnet2_name, cluster_name)
                vm2_ip = vm2_info["ip"]
                vm2_mfip = vm2_info["mfip"]
                logger.info(f"VM2创建成功: name={vm2_name}, ip={vm2_ip}, mfip={vm2_mfip}")

            with allure_step_log("步骤5: 创建HA企业路由器"):
                er_page._ensure_list_page()
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                er_page.er_create(
                    name=er_name,
                    cluster_name=cluster_name,
                    ha_enable=True,
                )
                er_page.assert_popup_success(timeout=10000)
                er_page.assert_status(er_name, status="运行中", timeout=120, refresh=True, refresh_interval=20)
                logger.info(f"HA ER {er_name} 创建成功")

            with allure_step_log("步骤6: 添加VPC1连接到ER"):
                er_page._ensure_list_page()
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                er_page.btn_refresh.click()
                er_page.wait_for_page_ready()
                er_page.goto_connection_tab(er_name)
                er_page.er_connection_create(
                    name=conn1_name,
                    conn_type="VPC",
                    vpc_name=vpc1_name,
                    subnet_name=subnet1_name,
                )
                er_page.assert_popup_success(timeout=10000)
                er_page.assert_status(conn1_name, status="运行中", timeout=60, refresh=True, refresh_interval=20)
                logger.info(f"VPC1连接 {conn1_name} 添加成功")

            with allure_step_log("步骤7: 添加VPC2连接到ER"):
                er_page.er_connection_create(
                    name=conn2_name,
                    conn_type="VPC",
                    vpc_name=vpc2_name,
                    subnet_name=subnet2_name,
                )
                er_page.assert_popup_success(timeout=10000)
                er_page.assert_status(conn2_name, status="运行中", timeout=60, refresh=True, refresh_interval=20)
                logger.info(f"VPC2连接 {conn2_name} 添加成功")

            with allure_step_log("步骤8: 在VPC1中添加自定义路由"):
                vpc_page.goto_service("虚拟私有云")
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                vpc_page.route_rule_create(
                    vpc_name=vpc1_name,
                    dest_cidr="174.4.4.0/24",
                    next_hop=er_name,
                    next_hop_type="企业路由器",
                    ip_version="IPv4",
                )
                vpc_page.assert_popup_success()
                vpc_page.assert_list_contain("174.4.4.0/24", column_name="目的地址")
                logger.info("VPC1路由规则添加并验证成功")

            with allure_step_log("步骤9: 在VPC2中添加自定义路由"):
                vpc_page.goto_service("虚拟私有云")
                vpc_page.close_dialog_if_exists()
                vpc_page.wait_for_page_ready()
                vpc_page.route_rule_create(
                    vpc_name=vpc2_name,
                    dest_cidr="173.3.3.0/24",
                    next_hop=er_name,
                    next_hop_type="企业路由器",
                    ip_version="IPv4",
                )
                vpc_page.assert_popup_success()
                vpc_page.assert_list_contain("173.3.3.0/24", column_name="目的地址")
                logger.info("VPC2路由规则添加并验证成功")

            with allure_step_log("步骤10: 验证vm1到vm2的连通性"):
                ssh_vm.connect(vm1_mfip)
                result = ssh_vm.run(f"ping -c 4 {vm2_ip}", return_stdout=True)
                print(f"\n{'='*60}")
                print(f"[PING RESULT] VM1 ({vm1_ip}) -> VM2 ({vm2_ip}):")
                print(f"{'='*60}")
                print(result)
                print(f"{'='*60}\n")
                logger.info(f"VM1 ping VM2结果:\n{result}")
                allure.attach(result, name="VM1 ping VM2结果", attachment_type=allure.attachment_type.TEXT)
                assert "0% packet loss" in result, f"VM1无法ping通VM2: {result}"
                logger.info("VM1到VM2连通性验证通过")

            with allure_step_log("步骤11: 验证vm2到vm1的连通性"):
                ssh_vm.connect(vm2_mfip)
                result = ssh_vm.run(f"ping -c 4 {vm1_ip}", return_stdout=True)
                print(f"\n{'='*60}")
                print(f"[PING RESULT] VM2 ({vm2_ip}) -> VM1 ({vm1_ip}):")
                print(f"{'='*60}")
                print(result)
                print(f"{'='*60}\n")
                logger.info(f"VM2 ping VM1结果:\n{result}")
                allure.attach(result, name="VM2 ping VM1结果", attachment_type=allure.attachment_type.TEXT)
                assert "0% packet loss" in result, f"VM2无法ping通VM1: {result}"
                logger.info("VM2到VM1连通性验证通过")

        except Exception as e:
            main_error = e
            raise
        finally:
            with allure_step_log("清理: 删除VPC1路由规则"):
                try:
                    vpc_page.goto_service("虚拟私有云")
                    vpc_page.close_dialog_if_exists()
                    vpc_page.wait_for_page_ready()
                    vpc_page.goto_submenu("虚拟私有云")
                    vpc_page.close_dialog_if_exists()
                    vpc_page.wait_for_page_ready()
                    vpc_page.get_row_by_name(vpc1_name).locator("a").first.click()
                    vpc_page.get_by_role("tab", name="路由表").click()
                    vpc_page.route_rule_delete("174.4.4.0/24")
                    vpc_page.assert_list_not_contain("174.4.4.0/24", column_name="目的地址")
                    logger.info("VPC1路由规则删除成功")
                except Exception as e:
                    logger.warning(f"删除VPC1路由规则失败: {e}")
                    cleanup_errors.append(f"删除VPC1路由规则: {e}")

            with allure_step_log("清理: 删除VPC2路由规则"):
                try:
                    vpc_page.goto_service("虚拟私有云")
                    vpc_page.close_dialog_if_exists()
                    vpc_page.wait_for_page_ready()
                    vpc_page.goto_submenu("虚拟私有云")
                    vpc_page.close_dialog_if_exists()
                    vpc_page.wait_for_page_ready()
                    vpc_page.get_row_by_name(vpc2_name).locator("a").first.click()
                    vpc_page.get_by_role("tab", name="路由表").click()
                    vpc_page.route_rule_delete("173.3.3.0/24")
                    vpc_page.assert_list_not_contain("173.3.3.0/24", column_name="目的地址")
                    logger.info("VPC2路由规则删除成功")
                except Exception as e:
                    logger.warning(f"删除VPC2路由规则失败: {e}")
                    cleanup_errors.append(f"删除VPC2路由规则: {e}")

            with allure_step_log("清理: 删除ER连接"):
                try:
                    er_page._ensure_list_page()
                    er_page.close_dialog_if_exists()
                    er_page.wait_for_page_ready()
                    er_page.goto_connection_tab(er_name)
                    er_page.er_connection_delete(conn1_name)
                    er_page.assert_deleted(conn1_name, timeout=30)
                    er_page.er_connection_delete(conn2_name)
                    er_page.assert_deleted(conn2_name, timeout=30)
                    logger.info("ER连接删除成功")
                except Exception as e:
                    logger.warning(f"删除ER连接失败: {e}")
                    cleanup_errors.append(f"删除ER连接: {e}")

            with allure_step_log("清理: 删除ER实例"):
                try:
                    er_page._ensure_list_page()
                    er_page.close_dialog_if_exists()
                    er_page.wait_for_page_ready()
                    er_page.er_delete(er_name)
                    er_page.assert_deleted(er_name, timeout=60)
                    logger.info(f"ER {er_name} 删除成功")
                except Exception as e:
                    logger.warning(f"删除ER失败: {e}")
                    cleanup_errors.append(f"删除ER: {e}")

            with allure_step_log("清理: 删除VM"):
                try:
                    ecs_page.goto_service("弹性云服务器")
                    ecs_page.close_dialog_if_exists()
                    ecs_page.wait_for_page_ready()
                    for vm_name in [vm1_name, vm2_name]:
                        try:
                            ecs_page.close_dialog_if_exists()
                            ecs_page.wait_for_page_ready()
                            ecs_page.ecs_remove(vm_name)
                            ecs_page.assert_deleted(vm_name, timeout=120)
                            logger.info(f"VM {vm_name} 已移入回收站")
                            ecs_page.close_dialog_if_exists()
                            ecs_page.goto_submenu("回收站")
                            ecs_page.close_dialog_if_exists()
                            ecs_page.wait_for_page_ready()
                            ecs_page.ecs_delete(vm_name)
                            ecs_page.assert_deleted(vm_name, timeout=120)
                            logger.info(f"VM {vm_name} 已从回收站彻底删除")
                        except Exception as e:
                            logger.warning(f"删除VM {vm_name} 失败: {e}")
                            cleanup_errors.append(f"删除VM {vm_name}: {e}")
                except Exception as e:
                    logger.warning(f"删除VM失败: {e}")
                    cleanup_errors.append(f"删除VM: {e}")

            with allure_step_log("清理: 删除VPC"):
                try:
                    vpc_page.goto_service("虚拟私有云")
                    vpc_page.goto_submenu("虚拟私有云")
                    vpc_page.wait_for_page_ready()
                    vpc_names = [vpc1_name, vpc2_name]
                    vpc_page.vpc_delete(vpc_names)
                    vpc_page.assert_deleted(vpc_names, timeout=120)
                    logger.info(f"VPC批量删除成功: {vpc_names}")
                except Exception as e:
                    logger.warning(f"批量删除VPC失败: {e}")
                    cleanup_errors.append(f"删除VPC: {e}")

            if cleanup_errors and main_error is None:
                raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")
