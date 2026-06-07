import pytest
import allure
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('网络服务')
@allure.feature('流量镜像')
@allure.story('修改功能验证')
class TestTMEditInnerECS:
    """流量镜像-云内实例-修改（用例407247）"""

    @pytest.mark.parametrize("vpc", [{"name_prefix": "tm_"}], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "name_prefix": "tm_"}], indirect=True)
    @allure.title("流量镜像-云内实例-修改")
    def test_tm_edit_inner_ecs(self, tm_page, ecs_page, vpc, vm):
        """验证流量镜像云内实例类型的修改功能。

        前置资源：
        - fixture vpc+vm: VPC + VM（目的实例）
        - 测试体内: 创建云内实例类型流量镜像
        """
        vm_name = vm["name"]
        tm_name = f"tm-inside-{random_data()}"
        created_name = None

        try:
            # 前置: 创建云内实例类型流量镜像
            with allure_step_log("前置: 创建云内实例类型流量镜像"):
                created_name = tm_page.tm_create_inner_ecs(
                    name=tm_name,
                    server_name=vm_name,
                )
                tm_page.assert_popup_success(timeout=10000)
                tm_page.assert_list_contain(created_name, column_name="名称")
                tm_page.assert_status(created_name, status="正常")

            # 步骤1: 打开修改弹窗，验证初始值，修改名称和描述
            new_name = f"{created_name}-modified"
            new_desc = "这是autotest修改之后的描述信息"

            with allure_step_log("步骤1: 打开修改弹窗并验证初始值"):
                original_data = tm_page.tm_edit(
                    created_name,
                    new_name=new_name,
                    new_desc=new_desc,
                )
                # P0: 断言修改提交成功
                tm_page.assert_popup_success(timeout=10000)
                # P1: 断言初始值正确
                assert original_data["name"] == created_name, \
                    f"[FieldAssertion] 初始名称不匹配: 期望 {created_name}, 实际 {original_data['name']}"

            # 步骤2: 列表页验证修改结果
            with allure_step_log("步骤2: 列表页验证修改结果"):
                tm_page._ensure_list_page()
                tm_page.page.wait_for_timeout(3000)
                tm_page.assert_list_contain(new_name, column_name="名称")

                row_data = tm_page.get_row_data(new_name)
                actual_name = row_data.get("名称", "")
                actual_desc = row_data.get("描述", "")
                assert actual_name == new_name, \
                    f"[FieldAssertion] 列表页名称不匹配: 期望 {new_name}, 实际 {actual_name}"
                assert actual_desc == new_desc, \
                    f"[FieldAssertion] 列表页描述不匹配: 期望 {new_desc}, 实际 {actual_desc}"

            # 步骤3: 详情页验证修改结果
            with allure_step_log("步骤3: 详情页验证修改结果"):
                tm_page.goto_tm_detail(new_name)
                tm_page.wait_for_page_ready()
                # 流量镜像名称从URL参数同步加载，立即可见
                page_text = tm_page.page.content()
                assert new_name in page_text, \
                    f"[FieldAssertion] 详情页未找到名称: {new_name}"
                # 虚拟机名称异步加载，轮询等待最长30秒
                for _ in range(15):
                    page_text = tm_page.page.content()
                    if vm_name in page_text:
                        break
                    tm_page.page.wait_for_timeout(2000)
                else:
                    raise AssertionError(
                        f"[FieldAssertion] 详情页30秒内未找到虚拟机名称: {vm_name}"
                    )

        finally:
            # 清理: 流量镜像 -> ECS -> 回收站
            with allure_step_log("清理: 删除流量镜像实例"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(5000)
                    # 使用新名称删除（如果修改成功）或原名称（如果修改失败）
                    delete_target = new_name if created_name else None
                    if delete_target:
                        tm_page.tm_delete(delete_target)
                        tm_page.assert_deleted(delete_target, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理流量镜像失败: {e}")

            with allure_step_log("清理: 删除弹性云服务器"):
                try:
                    ecs_page.goto_service("弹性云服务器")
                    ecs_page.ecs_remove(vm_name)
                    ecs_page.assert_deleted(vm_name, timeout=60000)
                except Exception as e:
                    logger.warning(f"清理弹性云服务器失败: {e}")

            with allure_step_log("清理: 从回收站彻底删除弹性云服务器"):
                try:
                    ecs_page.ecs_delete(vm_name)
                    ecs_page.assert_deleted(vm_name, timeout=60000)
                except Exception as e:
                    logger.warning(f"从回收站彻底删除弹性云服务器失败: {e}")


@allure.epic('网络服务')
@allure.feature('流量镜像')
@allure.story('修改功能验证')
class TestTMEditOutsideDevice:
    """流量镜像-云外设备-修改（用例1407247）"""

    @pytest.mark.parametrize("vpc", [{"name_prefix": "tm_"}], indirect=True)
    @pytest.mark.parametrize("vm", [{"basic": {"count": 1}, "name_prefix": "tm_"}], indirect=True)
    @allure.title("流量镜像-云外设备-修改")
    def test_tm_edit_outside_device(self, tm_page, ecs_page, vpc, vm):
        """验证流量镜像云外设备类型的修改功能。

        前置资源：
        - fixture vpc+vm: VPC + VM（镜像源）
        - 测试体内: 创建云外设备类型流量镜像 + 镜像会话
        """
        vm_name = vm["name"]
        vm_ip = vm.get("ip", "")
        vpc_name = vpc["name"]
        subnet_name = vpc["subnet_name"]

        tm_name = f"tm-outside-{random_data()}"
        session_name = f"tm-session-{random_data()}"
        vlan = "259"
        mac = "fa:16:e3:44:53:47"
        created_name = None

        try:
            # 前置1: 创建云外设备类型流量镜像
            with allure_step_log("前置1: 创建云外设备类型流量镜像"):
                created_name = tm_page.tm_create_outside_device(
                    name=tm_name,
                    vlan=vlan,
                    mac=mac,
                )
                tm_page.assert_popup_success(timeout=10000)
                tm_page.assert_list_contain(created_name, column_name="名称")
                tm_page.assert_status(created_name, status="正常")

            # 前置2: 创建镜像会话
            with allure_step_log("前置2: 创建镜像会话"):
                tm_page.goto_tm_session_tab(created_name)
                tm_page.tm_session_create(
                    name=session_name,
                    enabled=True,
                    vpc_name=vpc_name,
                    subnet_name=subnet_name,
                    vm_name=vm_name,
                    vm_ip=vm_ip,
                    direction="全部流量",
                )
                tm_page.assert_popup_success(timeout=10000)
                tm_page.assert_list_contain(session_name, column_name="名称")

            # 步骤1: 打开修改弹窗并验证初始值，修改名称和描述
            new_name = f"{created_name}-modified"
            new_desc = "这是autotest修改之后的描述信息"

            with allure_step_log("步骤1: 打开修改弹窗并验证初始值"):
                # 需要先回到流量镜像列表页
                tm_page.goto_service("流量镜像")
                tm_page.goto_submenu("流量镜像")
                tm_page.page.wait_for_timeout(3000)

                original_data = tm_page.tm_edit(
                    created_name,
                    new_name=new_name,
                    new_desc=new_desc,
                )
                # P0: 断言修改提交成功
                tm_page.assert_popup_success(timeout=10000)
                # P1: 断言初始值正确
                assert original_data["name"] == created_name, \
                    f"[FieldAssertion] 初始名称不匹配: 期望 {created_name}, 实际 {original_data['name']}"

            # 步骤2: 列表页验证修改结果
            with allure_step_log("步骤2: 列表页验证修改结果"):
                tm_page._ensure_list_page()
                tm_page.page.wait_for_timeout(3000)
                tm_page.assert_list_contain(new_name, column_name="名称")

                row_data = tm_page.get_row_data(new_name)
                actual_name = row_data.get("名称", "")
                actual_desc = row_data.get("描述", "")
                assert actual_name == new_name, \
                    f"[FieldAssertion] 列表页名称不匹配: 期望 {new_name}, 实际 {actual_name}"
                assert actual_desc == new_desc, \
                    f"[FieldAssertion] 列表页描述不匹配: 期望 {new_desc}, 实际 {actual_desc}"

            # 步骤3: 详情页验证修改结果
            with allure_step_log("步骤3: 详情页验证修改结果"):
                tm_page.goto_tm_detail(new_name)
                tm_page.wait_for_page_ready()
                page_text = tm_page.page.content()
                assert new_name in page_text, \
                    f"[FieldAssertion] 详情页未找到名称: {new_name}"
                assert new_desc in page_text, \
                    f"[FieldAssertion] 详情页未找到描述: {new_desc}"
                assert "云外设备" in page_text, \
                    f"[FieldAssertion] 详情页未找到类型: 云外设备"
                assert vlan in page_text, \
                    f"[FieldAssertion] 详情页未找到VLAN: {vlan}"
                assert mac in page_text, \
                    f"[FieldAssertion] 详情页未找到MAC地址: {mac}"

        finally:
            # 清理: 镜像会话 -> 流量镜像 -> ECS -> 回收站
            with allure_step_log("清理: 删除镜像会话"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    tm_page.goto_tm_session_tab(new_name if created_name else tm_name)
                    tm_page.tm_session_delete(session_name)
                    tm_page.assert_deleted(session_name, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理镜像会话失败: {e}")

            with allure_step_log("清理: 删除流量镜像实例"):
                try:
                    tm_page.goto_service("流量镜像")
                    tm_page.goto_submenu("流量镜像")
                    tm_page.page.wait_for_timeout(3000)
                    delete_target = new_name if created_name else None
                    if delete_target:
                        tm_page.tm_delete(delete_target)
                        tm_page.assert_deleted(delete_target, timeout=30000)
                except Exception as e:
                    logger.warning(f"清理流量镜像失败: {e}")

            with allure_step_log("清理: 删除弹性云服务器"):
                try:
                    ecs_page.goto_service("弹性云服务器")
                    ecs_page.ecs_remove(vm_name)
                    ecs_page.assert_deleted(vm_name, timeout=60000)
                except Exception as e:
                    logger.warning(f"清理弹性云服务器失败: {e}")

            with allure_step_log("清理: 从回收站彻底删除弹性云服务器"):
                try:
                    ecs_page.ecs_delete(vm_name)
                    ecs_page.assert_deleted(vm_name, timeout=60000)
                except Exception as e:
                    logger.warning(f"从回收站彻底删除弹性云服务器失败: {e}")
