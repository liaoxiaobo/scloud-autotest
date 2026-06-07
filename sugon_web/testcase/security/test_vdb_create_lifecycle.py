import time
import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('安全合规')
@allure.feature('数据库审计VDB')
@allure.story('新建实例-全生命周期验证')
class TestVdbCreateLifecycle:

    @allure.title("VDB-新建实例-全生命周期验证")
    def test_vdb_create_lifecycle(self, vdb_page):
        """创建数据库审计VDB实例，覆盖创建、列表/详情校验、
        跳转地址、关机/启动、再次跳转、清理删除全流程。"""
        name = f"autotest-vdb-{random_data().replace('autotest-', '')}"

        with allure_step_log("步骤1: 进入数据库审计VDB列表页面"):
            vdb_page.wait_for_page_ready()
            assert "/vdb" in vdb_page.page.url, \
                f"未导航到 VDB 页面，当前 URL: {vdb_page.page.url}"
            logger.info(f"已进入 VDB 列表页: {vdb_page.page.url}")

        with allure_step_log(f"步骤2: 新建VDB实例 {name}"):
            vdb_page.vdb_create(name=name)
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=600)
            row_data = vdb_page.get_row_data(name)
            logger.info(f"VDB 实例 {name} 创建完成，行数据: {row_data}")

        with allure_step_log(f"步骤3: 进入详情页验证跳转地址"):
            vdb_page.vdb_to_details(name)
            new_page = vdb_page.vdb_open_jump_address(refresh_interval=5, max_wait=300)
            assert new_page.url, "跳转地址打开的新页面 URL 为空"
            assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
            assert new_page.url and "chrome-error" not in new_page.url, \
                f"新页面加载到错误页面: {new_page.url}"
            if new_page != vdb_page.page:
                new_page.close()
            logger.info(f"VDB 实例 {name} 跳转地址验证通过")
            vdb_page.goto_list_page()

        with allure_step_log(f"步骤4: VDB实例 {name} 关机"):
            vdb_page.vdb_operations(name, "关机")
            vdb_page.assert_vdb_status(name, service_status="不可用", vm_status="关机", timeout=180)
            is_clickable = vdb_page.vdb_name_clickable(name)
            assert not is_clickable, f"关机后 VDB 实例 {name} 名称仍可点击，期望不可点击"

        with allure_step_log(f"步骤5: VDB实例 {name} 启动"):
            vdb_page.vdb_operations(name, "开机")
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤6: 开机后等待并再次验证实例 {name} 状态"):
            vdb_page.assert_vdb_status(name, service_status="运行", vm_status="运行", timeout=180)

        with allure_step_log(f"步骤7: 再次验证实例 {name} 跳转地址"):
            vdb_page.vdb_to_details(name)
            new_page = vdb_page.vdb_open_jump_address(refresh_interval=5, max_wait=300)
            assert new_page.url, "再次跳转地址打开的新页面 URL 为空"
            assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
            assert new_page.url and "chrome-error" not in new_page.url, \
                f"新页面加载到错误页面: {new_page.url}"
            if new_page != vdb_page.page:
                new_page.close()
            vdb_page.goto_list_page()

        with allure_step_log(f"步骤8(清理): 删除 VDB 实例 {name}"):
            vdb_page.vdb_delete(name)
            vdb_page.assert_deleted(name, timeout=300, refresh=True)
