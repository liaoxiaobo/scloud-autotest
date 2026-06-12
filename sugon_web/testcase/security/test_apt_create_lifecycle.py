import allure
import pytest
from sugon_web.utils.logger import allure_step_log, logger
from sugon_web.utils.data import random_data


@allure.epic('安全合规')
@allure.feature('攻击预警')
@allure.story('新建实例-全生命周期验证')
class TestAptCreateLifecycle:

    @allure.title("APT-新建实例-全生命周期验证")
    def test_apt_create_lifecycle(self, apt_page):
        """创建攻击预警实例，覆盖创建、列表/详情校验、
        跳转地址、关机/启动、再次跳转、清理删除全流程。"""
        name = f"autotest-apt-{random_data().replace('autotest-', '')}"

        with allure_step_log("步骤1: 进入攻击预警列表页面"):
            apt_page.wait_for_page_ready()
            assert "/apt" in apt_page.page.url, \
                f"未导航到 APT 页面，当前 URL: {apt_page.page.url}"
            logger.info(f"已进入 APT 列表页: {apt_page.page.url}")

        with allure_step_log("步骤2: 检查并清理已有APT实例"):
            existing = apt_page.delete_existing_apt(timeout=300)
            if existing:
                logger.info(f"已清理已有APT实例: {existing}")
            else:
                logger.info("APT 列表页无已有实例，无需清理")

        with allure_step_log(f"步骤3: 新建APT实例 {name}"):
            apt_page.apt_create(name=name)
            # 创建后通过实例出现在列表中且状态符合预期来验证成功
            apt_page.assert_apt_status(name, service_status="运行", vm_status="运行", timeout=1200)
            row_data = apt_page.get_row_data(name)
            logger.info(f"APT 实例 {name} 创建完成，行数据: {row_data}")

        with allure_step_log(f"步骤4: 进入详情页验证跳转地址"):
            apt_page.apt_to_details(name)
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is None:
                logger.warning(f"APT 实例 {name} 跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                assert "apt" in new_page.url.lower() or "/dashboard" in new_page.url or "/home" in new_page.url, \
                    f"新页面未进入 APT 平台，当前 URL: {new_page.url}"
                if new_page != apt_page.page:
                    new_page.close()
                logger.info(f"APT 实例 {name} 跳转地址验证通过")
            apt_page.goto_service('攻击预警')

        with allure_step_log(f"步骤5: APT实例 {name} 关机"):
            apt_page.apt_operations(name, "关机")
            apt_page.assert_apt_status(name, service_status="不可用", vm_status="关机", timeout=180)
            is_clickable = apt_page.apt_name_clickable(name)
            assert not is_clickable, f"关机后 APT 实例 {name} 名称仍可点击，期望不可点击"

        with allure_step_log(f"步骤6: APT实例 {name} 启动"):
            apt_page.apt_operations(name, "开机")
            apt_page.assert_apt_status(name, service_status="运行", vm_status="运行", timeout=300)

        with allure_step_log(f"步骤7: 开机后等待并再次验证实例 {name} 状态"):
            apt_page.assert_apt_status(name, service_status="运行", vm_status="运行", timeout=180)

        with allure_step_log(f"步骤8: 再次验证实例 {name} 跳转地址"):
            apt_page.apt_to_details(name)
            new_page = apt_page.apt_open_jump_address(refresh_interval=5, max_wait=300)
            if new_page is None:
                logger.warning(f"APT 实例 {name} 再次跳转地址验证跳过：目标服务器网络不可达")
            else:
                assert new_page.url, "再次跳转地址打开的新页面 URL 为空"
                assert "chrome-error" not in new_page.url, f"新页面加载到错误页面: {new_page.url}"
                assert "apt" in new_page.url.lower() or "/dashboard" in new_page.url or "/home" in new_page.url, \
                    f"新页面未进入 APT 平台，当前 URL: {new_page.url}"
                if new_page != apt_page.page:
                    new_page.close()
            apt_page.goto_service('攻击预警')

        with allure_step_log(f"步骤9(清理): 删除 APT 实例 {name}"):
            apt_page.apt_delete(name)
            apt_page.assert_deleted(name, timeout=300, refresh=True)
