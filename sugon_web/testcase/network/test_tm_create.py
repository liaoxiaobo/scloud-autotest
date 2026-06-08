import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('流量镜像')
@allure.story('新建实例功能验证')
class TestTMCreateInnerECS:
    """流量镜像-新建-云内实例-ECS类型（用例407258）"""

    @pytest.mark.parametrize("vpc", [{"name_prefix": "tm_"}], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "name_prefix": "tm_"}], indirect=True)
    @allure.title("流量镜像-新建-云内实例-ECS类型")
    def test_tm_create_inner_ecs(self, tm_page, ecs_page, vpc, vm, ssh_vm):
        """测试流量镜像云内实例-ECS类型的新建、列表验证、详情验证和SSH验证。

        清理顺序（确保无论测试结果如何都执行）：
        1. 清理流量镜像实例
        2. 清理弹性云服务器
        3. 清理虚拟私有云（由 vpc fixture teardown 自动处理）
        """
        vm_name = vm["name"]
        vm_mfip = vm.get("mfip")
        tm_name = f"tm-{random_data()}"
        created_name = None

        try:
            with allure_step_log("步骤1: 创建云内实例-ECS类型流量镜像"):
                created_name = tm_page.tm_create_inner_ecs(
                    name=tm_name,
                    server_name=vm_name,
                )
                tm_page.assert_popup_success(timeout=10000)

            with allure_step_log("步骤2: 验证列表页"):
                tm_page.assert_list_contain(created_name, column_name="名称")
                tm_page.assert_status(created_name, status="正常")

                # 验证类型为云服务器
                row_data = tm_page.get_row_data(created_name)
                assert "云服务器" in row_data.get("类型", ""), f"类型不匹配: {row_data.get('类型')}"

            with allure_step_log("步骤3: 验证详情页"):
                tm_page.goto_tm_detail(created_name)
                tm_page.wait_for_page_ready()
                # 流量镜像详情页使用 cl-item-col 自定义组件，直接通过页面文本断言
                page_text = tm_page.page.content()
                assert created_name in page_text, f"详情页未找到名称: {created_name}"
                assert vm_name in page_text, f"详情页未找到虚拟机名称: {vm_name}"
                assert "运行" in page_text, "详情页未找到实例状态: 运行"

            with allure_step_log("步骤4: SSH验证eth1网卡存在"):
                assert vm_mfip, f"VM {vm_name} 未绑定MFIP，无法SSH连接"
                ssh_vm.connect(vm_mfip)
                result = ssh_vm.run("ip ad list eth1")
                logger.info(f"ip ad list eth1 输出: {result}")
                assert "does not exist" not in result, f"eth1网卡不存在: {result}"

        finally:
            with allure_step_log("步骤5: 清理流量镜像"):
                if created_name:
                    try:
                        tm_page.tm_delete(created_name)
                        tm_page.assert_deleted(created_name, timeout=30000)
                    except Exception as e:
                        logger.warning(f"清理流量镜像失败: {e}")

            with allure_step_log("步骤6: 清理弹性云服务器"):
                try:
                    ecs_page.goto_service("弹性云服务器")
                    ecs_page.ecs_remove(vm_name)
                    ecs_page.assert_deleted(vm_name, timeout=60000)
                except Exception as e:
                    logger.warning(f"清理弹性云服务器失败: {e}")


@allure.epic('网络服务')
@allure.feature('流量镜像')
@allure.story('新建实例功能验证')
class TestTMCreateOutsideDevice:
    """流量镜像-新建-云外设备（用例421682）"""

    @allure.title("流量镜像-新建-云外设备")
    def test_tm_create_outside_device(self, tm_page):
        """测试流量镜像云外设备类型的新建、列表验证和详情验证。"""
        tm_name = f"tm-outside-{random_data()}"
        vlan = "259"
        mac = "fa:16:e3:44:53:47"

        with allure_step_log("步骤0: 清理环境中可能残留的同名MAC流量镜像"):
            tm_page.tm_cleanup_by_mac(mac)

        with allure_step_log("步骤1: 创建云外设备类型流量镜像"):
            created_name = tm_page.tm_create_outside_device(
                name=tm_name,
                vlan=vlan,
                mac=mac,
            )
            tm_page.assert_popup_success(timeout=10000)

        with allure_step_log("步骤2: 验证列表页"):
            tm_page.assert_list_contain(created_name, column_name="名称")
            tm_page.assert_status(created_name, status="正常")

            # 验证VLAN和MAC地址
            row_data = tm_page.get_row_data(created_name)
            row_vlan = row_data.get("VLAN", "")
            row_mac = row_data.get("MAC地址", "")
            assert vlan in str(row_vlan), f"VLAN不匹配: 期望 {vlan}, 实际 {row_vlan}"
            assert mac == row_mac, f"MAC地址不匹配: 期望 {mac}, 实际 {row_mac}"

        with allure_step_log("步骤3: 验证详情页"):
            tm_page.goto_tm_detail(created_name)
            tm_page.wait_for_page_ready()
            # 流量镜像详情页使用 cl-item-col 自定义组件，直接通过页面文本断言
            page_text = tm_page.page.content()
            assert created_name in page_text, f"详情页未找到名称: {created_name}"
            assert "云外设备" in page_text, "详情页未找到类型: 云外设备"
            assert "正常" in page_text, "详情页未找到状态: 正常"
            assert vlan in page_text, f"详情页未找到VLAN: {vlan}"
            assert mac in page_text, f"详情页未找到MAC地址: {mac}"

        with allure_step_log("步骤4: 清理流量镜像"):
            tm_page.tm_delete(created_name)
            tm_page.assert_deleted(created_name, timeout=30000)
