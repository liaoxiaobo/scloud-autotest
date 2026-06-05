import time
import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('安全合规')
@allure.feature('日志审计VER')
@allure.story('新建实例-全生命周期验证')
class TestVerCreateLifecycle:

    @allure.title("VER-新建实例-全生命周期验证")
    def test_ver_create_lifecycle(self, ver_page):
        """创建日志审计VER实例，覆盖创建、列表/详情校验、
        跳转地址、关机/启动、再次跳转、清理删除全流程。"""
        name = f"autotest-ver-{random_data().replace('autotest-', '')}"

        with allure_step_log("步骤1: 进入日志审计VER列表页面"):
            ver_page.wait_for_page_ready()
            assert "/ver" in ver_page.page.url, \
                f"未导航到 VER 页面，当前 URL: {ver_page.page.url}"
            logger.info(f"已进入 VER 列表页: {ver_page.page.url}")

        with allure_step_log(f"步骤2: 新建VER实例 {name}"):
            ver_page.ver_create(name=name)
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=600)
            row_data = ver_page.get_row_data(name)
            logger.info(f"VER 实例 {name} 创建完成，行数据: {row_data}")

        with allure_step_log(f"步骤3: 进入详情页验证跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address(refresh_interval=5, max_wait=300)
            assert new_page.url, "跳转地址打开的新页面 URL 为空"
            assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
            assert new_page.url and "chrome-error" not in new_page.url, \
                f"新页面加载到错误页面: {new_page.url}"
            if new_page != ver_page.page:
                new_page.close()
            logger.info(f"VER 实例 {name} 跳转地址验证通过")
            ver_page.goto_service('日志审计')

        with allure_step_log(f"步骤4: VER实例 {name} 关机"):
            ver_page.ver_operations(name, "关机")
            ver_page.assert_ver_status(name, service_status="不可用", vm_status="关机", timeout=180)
            is_clickable = ver_page.ver_name_clickable(name)
            assert not is_clickable, f"关机后 VER 实例 {name} 名称仍可点击，期望不可点击"

        with allure_step_log(f"步骤5: VER实例 {name} 启动"):
            ver_page.ver_operations(name, "开机")
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤6: 开机后等待并再次验证实例 {name} 状态"):
            time.sleep(60)
            ver_page.assert_ver_status(name, service_status="运行", vm_status="运行", timeout=120)

        with allure_step_log(f"步骤7: 再次验证实例 {name} 跳转地址"):
            ver_page.ver_to_details(name)
            new_page = ver_page.ver_open_jump_address(refresh_interval=5, max_wait=300)
            assert new_page.url, "再次跳转地址打开的新页面 URL 为空"
            assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
            assert new_page.url and "chrome-error" not in new_page.url, \
                f"新页面加载到错误页面: {new_page.url}"
            if new_page != ver_page.page:
                new_page.close()
            ver_page.goto_service('日志审计')

        with allure_step_log(f"步骤8(清理): 删除 VER 实例 {name}"):
            ver_page.ver_delete(name)
            ver_page.assert_deleted(name, timeout=300, refresh=True)
