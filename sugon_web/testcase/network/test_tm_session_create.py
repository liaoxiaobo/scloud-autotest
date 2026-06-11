import random

import pytest
import allure
from sugon_web.pages.network import VpcPage
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


def _random_mac():
    """生成随机MAC地址，使用 fa:16:e3 前缀。"""
    return "fa:16:e3:{:02x}:{:02x}:{:02x}".format(
        random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)
    )


def _create_vpc2(vpc_page):
    """创建第二个VPC，用于镜像会话的网络和镜像源VM。"""
    vpc_name = f"tm-vpc2-{random_data()}"
    subnet_name = f"autotest-{random_data()}"
    cidr = f"10.{random.randint(1, 254)}.{random.randint(0, 254)}.0/24"
    vpc_page.goto_service("虚拟私有云")
    vpc_page.vpc_create(name=vpc_name, subnet_name=subnet_name, cidr=cidr)
    vpc_page.assert_popup_success(timeout=30000)
    return {"name": vpc_name, "subnet_name": subnet_name, "cidr": cidr}


def _create_vm2(ecs_page, vpc_name, subnet_name, vm_name_prefix="tm-"):
    """在指定VPC下创建VM2（镜像源），返回VM名称和IP。"""
    vm_name = f"{vm_name_prefix}{random_data()}"
    ecs_page.goto_service("弹性云服务器")
    ecs_page.ecs_create(
        basic={"name": vm_name, "count": 1, "cluster": "Autotest", "flavor": {"base": "ecs.c6.Autotest"}},
        storage={"storage_pool": "xstor-test", "image": {"source": "镜像", "name": "xstor-test"}, "system_disk": 25},
        network={"networks": [{"network": vpc_name, "subnet": subnet_name}]},
        manage={"login_type": "密码登录", "login_pwd": "admin1234@sugon", "vnc_pwd": "sugon@20"},
    )
    ecs_page.assert_popup_success(timeout=120000)
    ecs_page.assert_status(vm_name, status="运行", timeout=300)
    row_data = ecs_page.get_row_data(vm_name)
    ip_raw = row_data.get("IP地址", "")
    ip = ip_raw.split("固定: ")[-1].strip() if "固定: " in ip_raw else ip_raw.strip()
    return {"name": vm_name, "ip": ip}


@allure.epic('网络服务')
@allure.feature('流量镜像')
@allure.story('镜像会话新建功能验证')
@pytest.mark.parametrize("vpc", [{"name_prefix": "tm_"}], indirect=True)
@pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "name_prefix": "tm_"}], indirect=True)
class TestTMSessionCreateInner:
    """镜像会话-新建-云内实例（开启/关闭）。两套前置资源均在类内共享：
    - VPC1+VM1：通过 pytest class scope fixture 复用
    - VPC2+VM2：通过类属性 _shared_vpc2 / _shared_vm2 复用
    """

    _shared_vpc2 = None
    _shared_vm2 = None

    @allure.title("镜像会话-新建-云内实例-开启")
    def test_tm_session_create_inner_enable(self, tm_page, ecs_page, vpc, vm):
        """测试镜像会话云内实例-开启场景的新建和列表验证。

        前置资源（fixture共享）：
        - vpc: VPC1，用于流量镜像目的实例网络
        - vm: VM1（在VPC1下），作为流量镜像目的实例
        - 类属性 _shared_vpc2 / _shared_vm2: VPC2+VM2，首次创建后共享给disable用例
        """
        vm1_name = vm["name"]
        tm_name = f"tm-inside-{random_data()}"
        session_name = f"tm-session-{random_data()}"

        # 首次创建 VPC2 + VM2，存入类属性供后续用例复用
        if TestTMSessionCreateInner._shared_vpc2 is None:
            with allure_step_log("前置: 创建VPC2和VM2（镜像源，类内共享）"):
                vpc_page = VpcPage(tm_page.page)
                TestTMSessionCreateInner._shared_vpc2 = _create_vpc2(vpc_page)
                TestTMSessionCreateInner._shared_vm2 = _create_vm2(
                    ecs_page,
                    TestTMSessionCreateInner._shared_vpc2["name"],
                    TestTMSessionCreateInner._shared_vpc2["subnet_name"],
                )

        vpc2_info = TestTMSessionCreateInner._shared_vpc2
        vm2_info = TestTMSessionCreateInner._shared_vm2

        try:
            with allure_step_log("步骤1: 创建云内实例类型流量镜像（目的实例=VM1）"):
                tm_page.goto_service("流量镜像")
                tm_page.goto_submenu("流量镜像")
                tm_page.tm_create_inner_ecs(name=tm_name, server_name=vm1_name)
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤2: 进入镜像会话Tab页"):
                tm_page.goto_tm_session_tab(tm_name)

            with allure_step_log("步骤3: 新建镜像会话（开启状态）"):
                tm_page.tm_session_create(
                    name=session_name,
                    enabled=True,
                    vpc_name=vpc2_info["name"],
                    subnet_name=vpc2_info["subnet_name"],
                    vm_name=vm2_info["name"],
                    vm_ip=vm2_info["ip"],
                    direction="全部流量",
                    desc="我的流量镜像_-123Abc",
                )
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤4: 验证镜像会话列表页"):
                tm_page.assert_list_contain(session_name, column_name="名称")
                row_data = tm_page.get_row_data(session_name)
                assert "全部流量" in row_data.get("方向", ""), f"方向不匹配: {row_data.get('方向')}"
                status = row_data.get("状态", row_data.get("状态 ", ""))
                assert "在线" in status, f"状态不匹配: {status}"
                assert "是" in row_data.get("是否开启", ""), f"是否开启不匹配: {row_data.get('是否开启')}"

        finally:
            # enable用例只清理本方法创建的会话和流量镜像；VPC2+VM2留给disable复用
            with allure_step_log("清理: 镜像会话"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.goto_tm_session_tab(tm_name)
                    tm_page.tm_session_delete(session_name)
                    tm_page.assert_deleted(session_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理镜像会话失败: {e}")

            with allure_step_log("清理: 流量镜像实例"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.tm_delete(tm_name)
                    tm_page.assert_deleted(tm_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理流量镜像实例失败: {e}")

    @allure.title("镜像会话-新建-云内实例-关闭")
    def test_tm_session_create_inner_disable(self, tm_page, ecs_page, vpc, vm):
        """测试镜像会话云内实例-关闭场景的新建和列表验证。

        前置资源（fixture共享）：
        - vpc: VPC1，用于流量镜像目的实例网络
        - vm: VM1（在VPC1下），作为流量镜像目的实例
        - 复用 enable 用例创建的 VPC2 + VM2（类属性）
        """
        vm1_name = vm["name"]
        tm_name = f"tm-inside-{random_data()}"
        session_name = f"tm-session-{random_data()}"

        vpc2_info = TestTMSessionCreateInner._shared_vpc2
        vm2_info = TestTMSessionCreateInner._shared_vm2

        # 防御：若前置用例未创建共享资源，则自动补建（避免enable失败导致disable中断）
        if vpc2_info is None or vm2_info is None:
            with allure_step_log("前置: 补建VPC2和VM2（enable未成功创建共享资源）"):
                vpc_page = VpcPage(tm_page.page)
                TestTMSessionCreateInner._shared_vpc2 = _create_vpc2(vpc_page)
                TestTMSessionCreateInner._shared_vm2 = _create_vm2(
                    ecs_page,
                    TestTMSessionCreateInner._shared_vpc2["name"],
                    TestTMSessionCreateInner._shared_vpc2["subnet_name"],
                )
                vpc2_info = TestTMSessionCreateInner._shared_vpc2
                vm2_info = TestTMSessionCreateInner._shared_vm2

        try:
            with allure_step_log("步骤1: 创建云内实例类型流量镜像（目的实例=VM1）"):
                tm_page.goto_service("流量镜像")
                tm_page.goto_submenu("流量镜像")
                tm_page.tm_create_inner_ecs(name=tm_name, server_name=vm1_name)
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤2: 进入镜像会话Tab页"):
                tm_page.goto_tm_session_tab(tm_name)

            with allure_step_log("步骤3: 新建镜像会话（关闭状态）"):
                tm_page.tm_session_create(
                    name=session_name,
                    enabled=False,
                    vpc_name=vpc2_info["name"],
                    subnet_name=vpc2_info["subnet_name"],
                    vm_name=vm2_info["name"],
                    vm_ip=vm2_info["ip"],
                    direction="全部流量",
                    desc="我的流量镜像_-123Abc",
                )
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤4: 验证镜像会话列表页"):
                tm_page.assert_list_contain(session_name, column_name="名称")
                row_data = tm_page.get_row_data(session_name)
                assert "全部流量" in row_data.get("方向", ""), f"方向不匹配: {row_data.get('方向')}"
                status = row_data.get("状态", row_data.get("状态 ", ""))
                assert "在线" in status, f"状态不匹配: {status}"
                assert "否" in row_data.get("是否开启", ""), f"是否开启不匹配: {row_data.get('是否开启')}"

        finally:
            # disable 用例负责最终清理：会话 -> 流量镜像 -> VM2 -> VPC2 -> VM1(fixture) -> VPC1(fixture)
            with allure_step_log("清理: 镜像会话"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.goto_tm_session_tab(tm_name)
                    tm_page.tm_session_delete(session_name)
                    tm_page.assert_deleted(session_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理镜像会话失败: {e}")

            with allure_step_log("清理: 流量镜像实例"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.tm_delete(tm_name)
                    tm_page.assert_deleted(tm_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理流量镜像实例失败: {e}")

            with allure_step_log("清理: 弹性云服务器（VM2）"):
                try:
                    if vm2_info and vm2_info.get("name"):
                        ecs_page.goto_service("弹性云服务器")
                        ecs_page.goto_submenu("弹性云服务器")
                        ecs_page.ecs_remove(vm2_info["name"])
                        ecs_page.assert_deleted(vm2_info["name"], timeout=60000)
                except Exception as e:
                    logger.warning(f"移除ECS VM2失败: {e}")

            with allure_step_log("清理: 从回收站彻底删除ECS（VM2）"):
                try:
                    if vm2_info and vm2_info.get("name"):
                        ecs_page.goto_submenu("回收站")
                        ecs_page.ecs_delete(vm2_info["name"])
                        ecs_page.assert_deleted(vm2_info["name"], timeout=60000)
                except Exception as e:
                    logger.warning(f"从回收站删除ECS VM2失败: {e}")

            with allure_step_log("清理: VPC2"):
                try:
                    if vpc2_info and vpc2_info.get("name"):
                        vpc_page = VpcPage(tm_page.page)
                        vpc_page.goto_service("虚拟私有云")
                        vpc_page.goto_submenu("虚拟私有云")
                        vpc_page.vpc_delete(vpc2_info["name"])
                        vpc_page.assert_deleted(vpc2_info["name"], timeout=30000)
                except Exception as e:
                    logger.warning(f"清理VPC2失败: {e}")

            # 兜底清理: fixture 创建的 VM1（_cleanup_vm_resources 在 overview 页搜索可能失败导致跳过）
            with allure_step_log("清理: 弹性云服务器（VM1-fixture兜底）"):
                try:
                    if vm1_name:
                        ecs_page.goto_service("弹性云服务器")
                        ecs_page.goto_submenu("弹性云服务器")
                        ecs_page.ecs_remove(vm1_name)
                        ecs_page.assert_deleted(vm1_name, timeout=60000)
                except Exception as e:
                    logger.warning(f"移除ECS VM1(fixture兜底)失败: {e}")

            with allure_step_log("清理: 从回收站彻底删除ECS（VM1-fixture兜底）"):
                try:
                    if vm1_name:
                        ecs_page.goto_submenu("回收站")
                        ecs_page.ecs_delete(vm1_name)
                        ecs_page.assert_deleted(vm1_name, timeout=60000)
                except Exception as e:
                    logger.warning(f"从回收站删除ECS VM1(fixture兜底)失败: {e}")

            # 兜底清理: fixture 创建的 VPC1
            with allure_step_log("清理: VPC1（fixture兜底）"):
                try:
                    vpc1_name = vpc["name"]
                    if vpc1_name:
                        vpc_page = VpcPage(tm_page.page)
                        vpc_page.goto_service("虚拟私有云")
                        vpc_page.goto_submenu("虚拟私有云")
                        vpc_page.vpc_delete(vpc1_name)
                        vpc_page.assert_deleted(vpc1_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理VPC1(fixture兜底)失败: {e}")

            # 重置类属性，避免影响后续其他类的执行
            TestTMSessionCreateInner._shared_vpc2 = None
            TestTMSessionCreateInner._shared_vm2 = None


@allure.epic('网络服务')
@allure.feature('流量镜像')
@allure.story('镜像会话新建功能验证')
class TestTMSessionCreateOutside:
    """镜像会话-新建-云外设备（用例421687）"""

    @allure.title("镜像会话-新建-云外设备")
    def test_tm_session_create_outside(self, tm_page, ecs_page):
        """测试镜像会话云外设备场景的新建和列表验证。

        不依赖外部vpc/vm fixture，全部资源在测试体内创建和清理。
        """
        tm_name = f"tm-outside-{random_data()}"
        session_name = f"tm-session-{random_data()}"
        vlan = "259"
        mac = _random_mac()

        vpc2_info = None
        vm2_info = None

        try:
            with allure_step_log("步骤0: 清理环境中可能残留的同名MAC流量镜像"):
                tm_page.goto_service("流量镜像")
                tm_page.goto_submenu("流量镜像")
                tm_page.tm_cleanup_by_mac(mac)

            with allure_step_log("步骤1: 创建VPC2和VM2（镜像源）"):
                vpc_page = VpcPage(tm_page.page)
                vpc2_info = _create_vpc2(vpc_page)
                vm2_info = _create_vm2(ecs_page, vpc2_info["name"], vpc2_info["subnet_name"])

            with allure_step_log("步骤2: 创建云外设备类型流量镜像"):
                tm_page.tm_create_outside_device(name=tm_name, vlan=vlan, mac=mac)
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤3: 进入镜像会话Tab页"):
                tm_page.goto_tm_session_tab(tm_name)

            with allure_step_log("步骤4: 新建镜像会话（出向流量）"):
                tm_page.tm_session_create(
                    name=session_name,
                    enabled=True,
                    vpc_name=vpc2_info["name"],
                    subnet_name=vpc2_info["subnet_name"],
                    vm_name=vm2_info["name"],
                    vm_ip=vm2_info["ip"],
                    direction="出向流量",
                    desc="我的流量镜像_-123Abc",
                )
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤5: 验证镜像会话列表页"):
                tm_page.assert_list_contain(session_name, column_name="名称")
                row_data = tm_page.get_row_data(session_name)
                assert "出向流量" in row_data.get("方向", ""), f"方向不匹配: {row_data.get('方向')}"
                status = row_data.get("状态", row_data.get("状态 ", ""))
                assert "在线" in status, f"状态不匹配: {status}"
                assert "是" in row_data.get("是否开启", ""), f"是否开启不匹配: {row_data.get('是否开启')}"

        finally:
            with allure_step_log("步骤6: 清理镜像会话"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.goto_tm_session_tab(tm_name)
                    tm_page.tm_session_delete(session_name)
                    tm_page.assert_deleted(session_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理镜像会话失败: {e}")

            with allure_step_log("步骤7: 清理流量镜像实例"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.tm_delete(tm_name)
                    tm_page.assert_deleted(tm_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理流量镜像实例失败: {e}")

            with allure_step_log("步骤8: 清理弹性云服务器"):
                try:
                    if vm2_info and vm2_info.get("name"):
                        ecs_page.goto_service("弹性云服务器")
                        ecs_page.goto_submenu("弹性云服务器")
                        ecs_page.ecs_remove(vm2_info["name"])
                        ecs_page.assert_deleted(vm2_info["name"], timeout=60000)
                except Exception as e:
                    logger.warning(f"移除ECS失败: {e}")

            with allure_step_log("步骤9: 从回收站彻底删除弹性云服务器"):
                try:
                    if vm2_info and vm2_info.get("name"):
                        ecs_page.goto_submenu("回收站")
                        ecs_page.ecs_delete(vm2_info["name"])
                        ecs_page.assert_deleted(vm2_info["name"], timeout=60000)
                except Exception as e:
                    logger.warning(f"从回收站彻底删除失败: {e}")

            with allure_step_log("步骤10: 清理VPC2"):
                try:
                    if vpc2_info and vpc2_info.get("name"):
                        vpc_page = VpcPage(tm_page.page)
                        vpc_page.goto_service("虚拟私有云")
                        vpc_page.vpc_delete(vpc2_info["name"])
                        vpc_page.assert_deleted(vpc2_info["name"], timeout=30000)
                except Exception as e:
                    logger.warning(f"清理VPC2失败: {e}")
