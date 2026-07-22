import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic("网络服务")
@allure.feature("对等连接")
@allure.story("路由配置与连通性验证")
class TestPeerConnectRouting:

    @allure.title("对等连接-打通同组织同项目下的VPC")
    @pytest.mark.parametrize("vpc", [{"count": 2}], indirect=True)
    def test_peer_connect_vpc_routing(self, vpc_page, ecs_page, ops_page, ssh_vm, vpc):
        """验证通过对等连接和路由表配置，打通同组织同项目下的两个VPC。"""
        vpc_a = vpc[0]
        vpc_b = vpc[1]
        vpc_a_name = vpc_a["name"]
        vpc_b_name = vpc_b["name"]
        vpc_a_subnet = vpc_a["subnet_name"]
        vpc_b_subnet = vpc_b["subnet_name"]
        vpc_a_cidr = vpc_a["cidr"]
        vpc_b_cidr = vpc_b["cidr"]

        peer_connect_name = f"pc-{random_data()}"
        vm_a_name = f"vm-{random_data()}"
        vm_b_name = f"vm-{random_data()}"
        route_desc = "1234567890qwertyu中文中文"

        with allure_step_log("步骤1: 创建对等连接"):
            vpc_page.peer_connect_create(
                name=peer_connect_name,
                requester_vpc=vpc_a_name,
                receiver_vpc=vpc_b_name,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_list_contain(peer_connect_name)
            row_data = vpc_page.get_row_data(peer_connect_name)
            assert vpc_a_name == row_data["本端vpc"], f"本端VPC断言失败: {row_data}"
            assert vpc_b_name == row_data["对端vpc"], f"对端VPC断言失败: {row_data}"

        with allure_step_log("步骤2: 在VPC-a下创建云服务器实例ecs-a"):
            ecs_page.ecs_create(
                basic={"name": vm_a_name, "count": 1},
                network={"networks": [{"network": vpc_a_name, "subnet": vpc_a_subnet}]},
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status([vm_a_name])

            vm_a_data = ecs_page.get_row_data(vm_a_name)
            vm_a_ip = vm_a_data["IP地址"].split(":")[1].strip()
            vm_a_project = vm_a_data["项目名称"]

            ops_page.mfip_create(vm_a_project, vpc_a_name, vm_a_ip, exact=False)
            ops_page.assert_popup_success()
            ops_page.mfip_search(vm_a_ip)
            vm_a_mfip = ops_page.get_row_data(vm_a_ip).get("管理IP地址")

            logger.info(f"ecs-a: {vm_a_name}, 内网IP: {vm_a_ip}, Mfip: {vm_a_mfip}")

        with allure_step_log("步骤3: 在VPC-b下创建云服务器实例ecs-b"):
            ecs_page.ecs_create(
                basic={"name": vm_b_name, "count": 1},
                network={"networks": [{"network": vpc_b_name, "subnet": vpc_b_subnet}]},
            )
            ecs_page.assert_popup_success("创建实例命令下发成功")
            ecs_page.assert_status([vm_b_name])

            vm_b_data = ecs_page.get_row_data(vm_b_name)
            vm_b_ip = vm_b_data["IP地址"].split(":")[1].strip()
            vm_b_project = vm_b_data["项目名称"]

            ops_page.mfip_create(vm_b_project, vpc_b_name, vm_b_ip, exact=False)
            ops_page.assert_popup_success()
            ops_page.mfip_search(vm_b_ip)
            vm_b_mfip = ops_page.get_row_data(vm_b_ip).get("管理IP地址")

            logger.info(f"ecs-b: {vm_b_name}, 内网IP: {vm_b_ip}, Mfip: {vm_b_mfip}")

        with allure_step_log("步骤4: 在VPC-a路由表中新建本端路由"):
            vpc_page.route_rule_create(
                vpc_name=vpc_a_name,
                dest_cidr=vpc_b_cidr,
                next_hop=peer_connect_name,
                next_hop_type="对等连接",
                desc=route_desc,
            )
            vpc_page.assert_popup_success()
            vpc_page.assert_list_contain(vpc_b_cidr, "目的地址")
            route_data = vpc_page.get_row_data(vpc_b_cidr)
            assert "对等连接" == route_data["下一跳类型"], f"下一跳类型断言失败: {route_data}"
            assert peer_connect_name == route_data["下一跳"], f"下一跳断言失败: {route_data}"
            assert route_desc == route_data["描述"], f"描述断言失败: {route_data}"

        with allure_step_log("步骤5: 在VPC-b路由表中新建对端路由"):
            vpc_page.route_rule_create(
                vpc_name=vpc_b_name,
                dest_cidr=vpc_a_cidr,
                next_hop=peer_connect_name,
                next_hop_type="对等连接",
            )
            vpc_page.assert_popup_success()

            vpc_page.assert_list_contain(vpc_a_cidr, "目的地址")
            route_data = vpc_page.get_row_data(vpc_a_cidr)
            assert "对等连接" == route_data["下一跳类型"], f"下一跳类型断言失败: {route_data}"
            assert peer_connect_name == route_data["下一跳"], f"下一跳断言失败: {route_data}"

        with allure_step_log("步骤6: 验证ecs-a到ecs-b的连通性"):
            ssh_vm.connect(vm_a_mfip)
            ssh_vm.ping(vm_b_ip)

        with allure_step_log("步骤7: 验证ecs-b到ecs-a的连通性"):
            ssh_vm.connect(vm_b_mfip)
            ssh_vm.ping(vm_a_ip)

        with allure_step_log("步骤8: 清理测试数据"):
            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.get_row_by_name(vpc_a_name).locator("a").first.click()
            vpc_page.get_by_role("tab", name="路由表").click()
            vpc_page.route_rule_delete(vpc_b_cidr)
            vpc_page.assert_deleted(vpc_b_cidr)

            vpc_page.goto_submenu("虚拟私有云")
            vpc_page.get_row_by_name(vpc_b_name).locator("a").first.click()
            vpc_page.get_by_role("tab", name="路由表").click()
            vpc_page.route_rule_delete(vpc_a_cidr)
            vpc_page.assert_deleted(vpc_a_cidr)

            vpc_page.peer_connect_delete(peer_connect_name)
            vpc_page.assert_deleted(peer_connect_name)

            ecs_page.ecs_remove([vm_a_name, vm_b_name])
            ecs_page.ecs_delete([vm_a_name, vm_b_name])
            ecs_page.assert_deleted([vm_a_name, vm_b_name])

            logger.info("测试数据清理完成")
