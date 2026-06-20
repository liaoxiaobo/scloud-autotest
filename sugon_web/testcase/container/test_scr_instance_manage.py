import allure
import pytest

from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('容器服务')
@allure.feature('容器镜像服务SCR')
@allure.story('实例管理功能验证')
class TestSCRInstanceManagement:
    """SCR 实例管理测试类：节点云硬盘扩容、命名空间管理、公网IP绑定解绑、规格变更。"""

    @allure.title("实例管理-列表页搜索和重置")
    def test_scr_search_reset(self, scr_page, scr_instance):
        """验证实例列表页搜索和重置功能。"""
        instance_name = scr_instance["name"]

        with allure_step_log("步骤1: 按实例名称搜索"):
            scr_page.goto_service(scr_page.service_name)
            scr_page.goto_submenu("实例管理")
            scr_page.search(instance_name)
            scr_page.assert_list_contain(instance_name, column_name="名称")

        with allure_step_log("步骤2: 重置搜索条件"):
            scr_page.btn_reset.click()
            assert scr_page._input_search.input_value() == "", "重置后搜索输入框未被清空"

    @allure.title("实例管理-修改实例名称")
    def test_scr_edit_name(self, scr_page, scr_instance):
        """修改 SCR 实例名称并验证列表更新。"""
        instance_name = scr_instance["name"]
        new_name = f"{instance_name}-edited"

        with allure_step_log("步骤1: 修改实例名称"):
            scr_page.scr_edit_name(instance_name, new_name)
            scr_page.assert_popup_success()

        with allure_step_log("步骤2: 验证列表显示新名称"):
            scr_page.assert_list_contain(new_name, column_name="名称")

        with allure_step_log("步骤3: 恢复原始名称"):
            scr_page.scr_edit_name(new_name, instance_name)
            scr_page.assert_popup_success()
            scr_page.assert_list_contain(instance_name, column_name="名称")

    @allure.title("实例管理-删除 SCR 实例")
    def test_scr_delete(self, scr_page, ssh_host):
        """创建临时 SCR 实例后删除，验证 UI 列表和后台虚机均清理。"""
        instance_name = f"scr-{random_data(length=4)}"

        with allure_step_log("步骤1: 创建临时 SCR 实例"):
            scr_page.scr_create(name=instance_name, instance_type="ALONE", flavor="4C8G")
            scr_page.assert_popup_success()

        with allure_step_log("步骤2: 等待实例状态收敛到运行中"):
            scr_page.assert_status(instance_name, status="运行中", timeout=1200)

        with allure_step_log("步骤3: 删除实例"):
            scr_page.scr_delete(instance_name)
            scr_page.assert_deleted(instance_name, timeout=600)

        with allure_step_log("步骤4: 后台验证虚机已删除"):
            ssh_host.wait_vm_deleted(instance_name, timeout=600)

    @allure.title("实例详情-修改云硬盘大小")
    def test_scr_node_volume_expand(self, scr_page, scr_instance, ssh_host):
        """验证云硬盘扩容功能及后台一致性。"""
        instance_name = scr_instance["name"]
        new_size = 20
        node_name = f"{instance_name}-0"

        with allure_step_log("步骤1: 进入实例详情页"):
            scr_page.goto_submenu("实例管理")
            scr_page.goto_detail_page(instance_name)
            scr_page.wait_for_page_ready()

        with allure_step_log("步骤2: 修改云硬盘大小"):
            scr_page.scr_node_volume_expand(new_size=new_size)
            scr_page.assert_popup_success()

        with allure_step_log("步骤3: 验证实例状态收敛到运行中"):
            # 返回实例列表页检查状态（强制导航回服务根页面以离开详情页）
            scr_page.goto_service(scr_page.service_name, force=True)
            scr_page.goto_submenu("实例管理")
            scr_page.assert_status(instance_name, status="运行中", timeout=600, refresh=True)

        with allure_step_log("步骤4: 验证云盘大小已更新"):
            # 进入详情页获取最新云硬盘大小
            scr_page.goto_detail_page(instance_name)
            scr_page.wait_for_page_ready()
            volume_size_text = scr_page.get_volume_size_text()
            assert f"{new_size}" in volume_size_text, (
                f"[FieldAssertion] 云硬盘大小 | 扩容后校验失败 | "
                f"期望: 包含 {new_size} | 实际: {volume_size_text}"
            )

        with allure_step_log("步骤5: 后台验证云硬盘信息"):
            result = ssh_host.run(
                f"source /root/admin-openrc.sh && scli volume list | grep {node_name}",
                return_rc=True
            )
            assert result["rc"] == 0, (
                f"[BackendAssertion] 后台未找到节点 {node_name} 对应的云硬盘: "
                f"{result.get('stderr', '')}"
            )
            assert f"{new_size}" in result["stdout"], (
                f"[BackendAssertion] 后台云硬盘大小不匹配 | "
                f"期望: 包含 {new_size} | 实际: {result['stdout']}"
            )

    @allure.title("实例管理-创建和删除命名空间")
    def test_scr_namespace_create_delete(self, scr_page, scr_instance):
        """验证命名空间的创建和删除功能。"""
        instance_name = scr_instance["name"]
        namespace_name = f"ns-{random_data(length=4)}"

        with allure_step_log("步骤1: 进入实例详情页-命名空间"):
            scr_page.goto_submenu("实例管理")
            scr_page.goto_detail_page(instance_name)
            scr_page.wait_for_page_ready()
            scr_page.page.get_by_text("命名空间", exact=True).wait_for(state="visible", timeout=10000)
            scr_page.page.get_by_text("命名空间", exact=True).click()
            scr_page.wait_for_page_ready()

        with allure_step_log("步骤2: 创建命名空间"):
            scr_page.scr_namespace_create(namespace_name)
            scr_page.assert_popup_success()
            scr_page.assert_list_contain(namespace_name, column_name="命名空间")

        with allure_step_log("步骤3: 删除命名空间"):
            scr_page.scr_namespace_delete(namespace_name)
            scr_page.assert_list_not_contain(namespace_name, column_name="命名空间")

    @allure.title("命名空间列表搜索功能验证")
    def test_scr_namespace_search(self, scr_page, scr_instance):
        """验证命名空间列表的搜索和重置功能。"""
        instance_name = scr_instance["name"]
        namespace_name = f"ns-{random_data(length=4)}"

        with allure_step_log("步骤1: 进入实例详情页-命名空间"):
            scr_page.goto_submenu("实例管理")
            scr_page.goto_detail_page(instance_name)
            scr_page.wait_for_page_ready()
            scr_page.page.get_by_text("命名空间", exact=True).wait_for(state="visible", timeout=10000)
            scr_page.page.get_by_text("命名空间", exact=True).click()
            scr_page.wait_for_page_ready()

        with allure_step_log("步骤2: 准备搜索数据（创建命名空间）"):
            scr_page.scr_namespace_create(namespace_name)
            scr_page.assert_popup_success()
            scr_page.assert_list_contain(namespace_name, column_name="命名空间")

        with allure_step_log("步骤3: 搜索命名空间"):
            scr_page.search(namespace_name)
            scr_page.assert_list_contain(namespace_name, column_name="命名空间")

        with allure_step_log("步骤4: 重置搜索条件"):
            scr_page.btn_reset.click()
            assert scr_page._input_search.input_value() == "", (
                "[FieldAssertion] 搜索框 | 重置后校验失败 | "
                "期望: 为空 | 实际: 有内容"
            )
            scr_page.assert_list_contain(namespace_name, column_name="命名空间")

        with allure_step_log("步骤5: 清理创建的命名空间"):
            scr_page.scr_namespace_delete(namespace_name)
            scr_page.assert_list_not_contain(namespace_name, column_name="命名空间")

    @allure.title("实例详情-绑定和解绑公网IP")
    def test_scr_public_ip_bind_unbind(self, scr_page, scr_instance, ssh_host):
        """验证实例公网IP的绑定和解绑功能及后台连通性。

        默认资源池中有充足的可用公网IP，直接从已有资源池中选择可用IP进行绑定，
        不再通过 eip fixture 预先分配新IP。
        """
        instance_name = scr_instance["name"]
        pool_name = "public_net(基础版)"

        with allure_step_log("步骤1: 进入实例详情页"):
            scr_page.goto_submenu("实例管理")
            scr_page.goto_detail_page(instance_name)
            scr_page.wait_for_page_ready()

        with allure_step_log("步骤2: 从资源池绑定公网IP"):
            ip_address = scr_page.scr_public_ip_bind(pool=pool_name)
            scr_page.assert_popup_success()
            logger.info(f"绑定的公网IP: {ip_address}")

        with allure_step_log("步骤3: 验证公网IP绑定成功"):
            public_ip = scr_page.get_public_ip_text()
            if not public_ip or public_ip == "--":
                scr_page.goto_service(scr_page.service_name)
                scr_page.goto_submenu("实例管理")
                row_data = scr_page.get_row_data(instance_name)
                public_ip = row_data.get("公网IP", "")
            assert ip_address in public_ip or public_ip == ip_address, (
                f"[FieldAssertion] 公网IP | 绑定后校验失败 | "
                f"期望: 包含 {ip_address} | 实际: {public_ip}"
            )

        with allure_step_log("步骤4: 后台验证连通性"):
            ssh_host.ping(ip_address)

        with allure_step_log("步骤5: 解绑公网IP"):
            scr_page.scr_public_ip_unbind()
            scr_page.assert_popup_success()

        with allure_step_log("步骤6: 验证公网IP已解绑"):
            public_ip = scr_page.get_public_ip_text()
            if public_ip and public_ip != "--":
                scr_page.goto_service(scr_page.service_name)
                scr_page.goto_submenu("实例管理")
                row_data = scr_page.get_row_data(instance_name)
                public_ip = row_data.get("公网IP", "")
            assert public_ip == "--" or not public_ip, (
                f"[FieldAssertion] 公网IP | 解绑后校验失败 | "
                f"期望: -- 或空 | 实际: {public_ip}"
            )

        with allure_step_log("步骤7: 后台验证无法连通"):
            ssh_host.ping(ip_address, connected=False)

    @allure.title("实例管理-单机实例修改规格")
    def test_scr_flavor_change(self, scr_page, scr_instance, ssh_host):
        """验证单机实例规格变更功能（只能升配）及后台一致性。"""
        instance_name = scr_instance["name"]
        target_flavor = "8C16G"

        with allure_step_log("步骤1: 修改规格并等待状态收敛"):
            scr_page.scr_flavor_change(instance_name, target_flavor)
            scr_page.assert_popup_success()

        with allure_step_log("步骤2: 等待状态收敛到运行中"):
            scr_page.assert_status(instance_name, "运行中", timeout=600, refresh=True)

        with allure_step_log("步骤3: 后台验证规格变更"):
            node_name = f"{instance_name}-0"
            ssh_host.assert_guest_fields(
                node_name,
                {"vcpu": "8", "memory_mb": "16384"},
                f"{node_name}规格变更后端验证失败"
            )
