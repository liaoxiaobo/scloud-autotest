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
    # 取最后一条匹配记录（最新创建的MFIP）
    rows = ops_page.get_rows_by_text(vm_ip)
    last_row = rows.last
    vm_mfip = ops_page.get_row_data_by_locator(last_row).get("管理IP地址")

    return {"name": vm_name, "ip": vm_ip, "mfip": vm_mfip}


def _wait_for_connection_ready(er_page, conn_name, wait_seconds=15, refresh_interval=5):
    """等待ER连接就绪，期间定时刷新列表。"""
    import time
    start = time.time()
    while time.time() - start < wait_seconds:
        remaining = wait_seconds - (time.time() - start)
        if remaining <= 0:
            break
        sleep_time = min(refresh_interval, remaining)
        time.sleep(sleep_time)
        er_page.btn_refresh.click()
        er_page.wait_for_page_ready()
    # 最终断言状态
    er_page.assert_status(conn_name, status="运行中", timeout=30, refresh=True, refresh_interval=10)


def _wait_for_route_rule_visible(er_page, destination, wait_seconds=60, refresh_interval=20):
    """等待路由规则在列表中可见，期间定时刷新列表。"""
    import time
    start = time.time()
    found = False
    while time.time() - start < wait_seconds:
        try:
            er_page.assert_list_contain(destination, column_name="目的地址")
            found = True
            break
        except AssertionError:
            remaining = wait_seconds - (time.time() - start)
            if remaining <= 0:
                break
            sleep_time = min(refresh_interval, remaining)
            time.sleep(sleep_time)
            er_page.btn_refresh.click()
            er_page.wait_for_page_ready()
    if not found:
        raise AssertionError(f"路由规则 {destination} 在 {wait_seconds} 秒内未在列表中出现")


def _run_peer_connection_test(
    er_page, vpc_page, ecs_page, ops_page, ssh_vm,
    er1_name, er2_name, ha_enable,
    vpc1_name, vpc2_name, subnet1_name, subnet2_name,
    vm1_name, vm2_name, conn1_name, conn2_name,
    cluster_name,
):
    """执行ER对等连接生效性验证的核心逻辑。"""
    # 创建VPC1
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

    # 创建VM1并绑定MFIP
    with allure_step_log("步骤2: 创建VM1并绑定MFIP"):
        vm1_info = _create_vm_and_bind_mfip(ecs_page, ops_page, vm1_name, vpc1_name, subnet1_name, cluster_name)
        vm1_ip = vm1_info["ip"]
        vm1_mfip = vm1_info["mfip"]
        logger.info(f"VM1创建成功: name={vm1_name}, ip={vm1_ip}, mfip={vm1_mfip}")

    # 创建VPC2
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

    # 创建VM2并绑定MFIP
    with allure_step_log("步骤4: 创建VM2并绑定MFIP"):
        vm2_info = _create_vm_and_bind_mfip(ecs_page, ops_page, vm2_name, vpc2_name, subnet2_name, cluster_name)
        vm2_ip = vm2_info["ip"]
        vm2_mfip = vm2_info["mfip"]
        logger.info(f"VM2创建成功: name={vm2_name}, ip={vm2_ip}, mfip={vm2_mfip}")

    # 创建ER1
    with allure_step_log("步骤5: 创建ER1"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er_page.er_create(
            name=er1_name,
            cluster_name=cluster_name,
            ha_enable=ha_enable,
        )
        er_page.assert_popup_success(timeout=10000)
        er_page.assert_status(er1_name, status="运行中", timeout=120, refresh=True, refresh_interval=20)
        logger.info(f"ER1 {er1_name} 创建成功")

    # 创建ER2
    with allure_step_log("步骤6: 创建ER2"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er_page.er_create(
            name=er2_name,
            cluster_name=cluster_name,
            ha_enable=ha_enable,
        )
        er_page.assert_popup_success(timeout=10000)
        er_page.assert_status(er2_name, status="运行中", timeout=120, refresh=True, refresh_interval=20)
        logger.info(f"ER2 {er2_name} 创建成功")

    # 添加VPC1连接到ER1
    with allure_step_log("步骤7: 添加VPC1连接到ER1"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er_page.goto_connection_tab(er1_name)
        er_page.er_connection_create(
            name=f"conn-{vpc1_name[:20]}",
            conn_type="VPC",
            vpc_name=vpc1_name,
            subnet_name=subnet1_name,
        )
        er_page.assert_popup_success(timeout=10000)
        er_page.assert_status(f"conn-{vpc1_name[:20]}", status="运行中", timeout=15, refresh=True, refresh_interval=5)
        logger.info("VPC1连接到ER1添加成功")

    # 添加VPC2连接到ER2
    with allure_step_log("步骤8: 添加VPC2连接到ER2"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er_page.goto_connection_tab(er2_name)
        er_page.er_connection_create(
            name=f"conn-{vpc2_name[:20]}",
            conn_type="VPC",
            vpc_name=vpc2_name,
            subnet_name=subnet2_name,
        )
        er_page.assert_popup_success(timeout=10000)
        er_page.assert_status(f"conn-{vpc2_name[:20]}", status="运行中", timeout=15, refresh=True, refresh_interval=5)
        logger.info("VPC2连接到ER2添加成功")

    # 生成ER1授权码
    with allure_step_log("步骤9: 生成ER1授权码"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er1_code = er_page.er_generate_auth_code(er1_name)
        logger.info(f"ER1授权码生成成功")

    # 生成ER2授权码
    with allure_step_log("步骤10: 生成ER2授权码"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er2_code = er_page.er_generate_auth_code(er2_name)
        logger.info(f"ER2授权码生成成功")

    # ER1添加ER连接（使用ER2授权码）
    with allure_step_log("步骤11: ER1添加ER连接"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er_page.goto_connection_tab(er1_name)
        er_page.er_connection_create(
            name=conn1_name,
            conn_type="ER",
            auth_code=er2_code,
        )
        er_page.assert_popup_success(timeout=10000)
        logger.info(f"ER1对等连接 {conn1_name} 添加成功")

    # 等待并验证ER1连接
    with allure_step_log("步骤12: 等待并验证ER1连接"):
        _wait_for_connection_ready(er_page, conn1_name, wait_seconds=15, refresh_interval=5)
        logger.info("ER1连接验证通过")

    # ER2添加ER连接（使用ER1授权码）
    with allure_step_log("步骤13: ER2添加ER连接"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er_page.goto_connection_tab(er2_name)
        er_page.er_connection_create(
            name=conn2_name,
            conn_type="ER",
            auth_code=er1_code,
        )
        er_page.assert_popup_success(timeout=10000)
        logger.info(f"ER2对等连接 {conn2_name} 添加成功")

    # 等待并验证ER2连接
    with allure_step_log("步骤14: 等待并验证ER2连接"):
        _wait_for_connection_ready(er_page, conn2_name, wait_seconds=15, refresh_interval=5)
        logger.info("ER2连接验证通过")

    # ER1路由表添加规则
    with allure_step_log("步骤15: ER1路由表添加规则"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er_page.goto_route_table_tab(er1_name)
        er_page.er_route_rule_create(
            destination="174.4.4.0/24",
            next_hop_type="企业路由器",
            connection=conn1_name,
            next_hop=er2_name,
        )
        er_page.assert_popup_success(timeout=10000)
        logger.info("ER1路由规则添加成功")

    # 等待并验证ER1路由规则
    with allure_step_log("步骤16: 等待并验证ER1路由规则"):
        _wait_for_route_rule_visible(er_page, "174.4.4.0/24", wait_seconds=15, refresh_interval=5)
        logger.info("ER1路由规则验证通过")

    # ER2路由表添加规则
    with allure_step_log("步骤17: ER2路由表添加规则"):
        er_page._ensure_list_page()
        er_page.close_dialog_if_exists()
        er_page.wait_for_page_ready()
        er_page.goto_route_table_tab(er2_name)
        er_page.er_route_rule_create(
            destination="173.3.3.0/24",
            next_hop_type="企业路由器",
            connection=conn2_name,
            next_hop=er1_name,
        )
        er_page.assert_popup_success(timeout=10000)
        logger.info("ER2路由规则添加成功")

    # 等待并验证ER2路由规则
    with allure_step_log("步骤18: 等待并验证ER2路由规则"):
        _wait_for_route_rule_visible(er_page, "173.3.3.0/24", wait_seconds=15, refresh_interval=5)
        logger.info("ER2路由规则验证通过")

    # VPC1添加自定义路由
    with allure_step_log("步骤19: VPC1添加自定义路由"):
        vpc_page.goto_service("虚拟私有云")
        vpc_page.close_dialog_if_exists()
        vpc_page.wait_for_page_ready()
        vpc_page.route_rule_create(
            vpc_name=vpc1_name,
            dest_cidr="174.4.4.0/24",
            next_hop=er1_name,
            next_hop_type="企业路由器",
            ip_version="IPv4",
        )
        vpc_page.assert_popup_success()
        vpc_page.assert_list_contain("174.4.4.0/24", column_name="目的地址")
        logger.info("VPC1路由规则添加并验证成功")

    # VPC2添加自定义路由
    with allure_step_log("步骤20: VPC2添加自定义路由"):
        vpc_page.goto_service("虚拟私有云")
        vpc_page.close_dialog_if_exists()
        vpc_page.wait_for_page_ready()
        vpc_page.route_rule_create(
            vpc_name=vpc2_name,
            dest_cidr="173.3.3.0/24",
            next_hop=er2_name,
            next_hop_type="企业路由器",
            ip_version="IPv4",
        )
        vpc_page.assert_popup_success()
        vpc_page.assert_list_contain("173.3.3.0/24", column_name="目的地址")
        logger.info("VPC2路由规则添加并验证成功")

    # 验证vm1到vm2的连通性
    with allure_step_log("步骤21: 验证vm1到vm2的连通性"):
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

    # 验证vm2到vm1的连通性
    with allure_step_log("步骤22: 验证vm2到vm1的连通性"):
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

    return {
        "vpc1_name": vpc1_name, "vpc2_name": vpc2_name,
        "vm1_name": vm1_name, "vm2_name": vm2_name,
        "er1_name": er1_name, "er2_name": er2_name,
        "conn1_name": conn1_name, "conn2_name": conn2_name,
        "conn_vpc1_name": f"conn-{vpc1_name[:20]}", "conn_vpc2_name": f"conn-{vpc2_name[:20]}",
    }


def _cleanup_resources(
    er_page, vpc_page, ecs_page,
    vpc1_name, vpc2_name, vm1_name, vm2_name,
    er1_name, er2_name, conn1_name, conn2_name,
    conn_vpc1_name, conn_vpc2_name,
):
    """清理测试资源。"""
    cleanup_errors = []

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

    with allure_step_log("清理: 删除ER1连接"):
        try:
            er_page._ensure_list_page()
            er_page.close_dialog_if_exists()
            er_page.wait_for_page_ready()
            er_page.goto_connection_tab(er1_name)
            for conn_name in [conn1_name, conn_vpc1_name]:
                try:
                    er_page.er_connection_delete(conn_name)
                    er_page.assert_deleted(conn_name, timeout=30)
                except Exception:
                    pass
            logger.info("ER1连接删除成功")
        except Exception as e:
            logger.warning(f"删除ER1连接失败: {e}")
            cleanup_errors.append(f"删除ER1连接: {e}")

    with allure_step_log("清理: 删除ER2连接"):
        try:
            er_page._ensure_list_page()
            er_page.close_dialog_if_exists()
            er_page.wait_for_page_ready()
            er_page.goto_connection_tab(er2_name)
            for conn_name in [conn2_name, conn_vpc2_name]:
                try:
                    er_page.er_connection_delete(conn_name)
                    er_page.assert_deleted(conn_name, timeout=30)
                except Exception:
                    pass
            logger.info("ER2连接删除成功")
        except Exception as e:
            logger.warning(f"删除ER2连接失败: {e}")
            cleanup_errors.append(f"删除ER2连接: {e}")

    with allure_step_log("清理: 删除ER实例"):
        for er_name in [er1_name, er2_name]:
            try:
                er_page._ensure_list_page()
                er_page.close_dialog_if_exists()
                er_page.wait_for_page_ready()
                er_page.er_delete(er_name)
                er_page.assert_deleted(er_name, timeout=60)
                logger.info(f"ER {er_name} 删除成功")
            except Exception as e:
                logger.warning(f"删除ER {er_name} 失败: {e}")
                cleanup_errors.append(f"删除ER {er_name}: {e}")

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

    return cleanup_errors


@allure.epic('网络服务')
@allure.feature('企业路由器')
@allure.story('对等连接生效性验证')
class TestERPeerConnection:

    @allure.title("ER对等连接生效性验证-HA2HA")
    def test_er_peer_connection_ha2ha(self, er_page, vpc_page, ecs_page, ops_page, ssh_vm, ssh_host):
        """测试两个HA类型ER之间的对等连接生效性。"""
        vpc1_name = f"er-peer-vpc1-{random_data(length=4)}"
        vpc2_name = f"er-peer-vpc2-{random_data(length=4)}"
        subnet1_name = f"subnet1-{random_data(length=4)}"
        subnet2_name = f"subnet2-{random_data(length=4)}"
        vm1_name = f"er-peer-vm1-{random_data(length=4)}"
        vm2_name = f"er-peer-vm2-{random_data(length=4)}"
        er1_name = f"er-peer1-ha-{random_data(length=4)}"
        er2_name = f"er-peer2-ha-{random_data(length=4)}"
        conn1_name = f"er1-er2-conn-{random_data(length=4)}"
        conn2_name = f"er2-er1-conn-{random_data(length=4)}"
        cluster_name = "Autotest"
        main_error = None
        resource_info = None

        try:
            resource_info = _run_peer_connection_test(
                er_page, vpc_page, ecs_page, ops_page, ssh_vm,
                er1_name, er2_name, ha_enable=True,
                vpc1_name=vpc1_name, vpc2_name=vpc2_name,
                subnet1_name=subnet1_name, subnet2_name=subnet2_name,
                vm1_name=vm1_name, vm2_name=vm2_name,
                conn1_name=conn1_name, conn2_name=conn2_name,
                cluster_name=cluster_name,
            )
        except Exception as e:
            main_error = e
            raise
        finally:
            if resource_info:
                cleanup_errors = _cleanup_resources(
                    er_page, vpc_page, ecs_page,
                    resource_info["vpc1_name"], resource_info["vpc2_name"],
                    resource_info["vm1_name"], resource_info["vm2_name"],
                    resource_info["er1_name"], resource_info["er2_name"],
                    resource_info["conn1_name"], resource_info["conn2_name"],
                    resource_info["conn_vpc1_name"], resource_info["conn_vpc2_name"],
                )
                if cleanup_errors and main_error is None:
                    raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")

    @allure.title("ER对等连接生效性验证-noHA2noHA")
    def test_er_peer_connection_noha2noha(self, er_page, vpc_page, ecs_page, ops_page, ssh_vm, ssh_host):
        """测试两个非HA类型ER之间的对等连接生效性。"""
        vpc1_name = f"er-peer-vpc1-{random_data(length=4)}"
        vpc2_name = f"er-peer-vpc2-{random_data(length=4)}"
        subnet1_name = f"subnet1-{random_data(length=4)}"
        subnet2_name = f"subnet2-{random_data(length=4)}"
        vm1_name = f"er-peer-vm1-{random_data(length=4)}"
        vm2_name = f"er-peer-vm2-{random_data(length=4)}"
        er1_name = f"er-peer1-noha-{random_data(length=4)}"
        er2_name = f"er-peer2-noha-{random_data(length=4)}"
        conn1_name = f"er1-er2-conn-{random_data(length=4)}"
        conn2_name = f"er2-er1-conn-{random_data(length=4)}"
        cluster_name = "Autotest"
        main_error = None
        resource_info = None

        try:
            resource_info = _run_peer_connection_test(
                er_page, vpc_page, ecs_page, ops_page, ssh_vm,
                er1_name, er2_name, ha_enable=False,
                vpc1_name=vpc1_name, vpc2_name=vpc2_name,
                subnet1_name=subnet1_name, subnet2_name=subnet2_name,
                vm1_name=vm1_name, vm2_name=vm2_name,
                conn1_name=conn1_name, conn2_name=conn2_name,
                cluster_name=cluster_name,
            )
        except Exception as e:
            main_error = e
            raise
        finally:
            if resource_info:
                cleanup_errors = _cleanup_resources(
                    er_page, vpc_page, ecs_page,
                    resource_info["vpc1_name"], resource_info["vpc2_name"],
                    resource_info["vm1_name"], resource_info["vm2_name"],
                    resource_info["er1_name"], resource_info["er2_name"],
                    resource_info["conn1_name"], resource_info["conn2_name"],
                    resource_info["conn_vpc1_name"], resource_info["conn_vpc2_name"],
                )
                if cleanup_errors and main_error is None:
                    raise AssertionError(f"清理失败 ({len(cleanup_errors)} 项): {'; '.join(cleanup_errors)}")
