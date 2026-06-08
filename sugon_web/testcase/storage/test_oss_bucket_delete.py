import allure
import pytest

from sugon_web.pages.storage.oss import OosPage
from sugon_web.utils.logger import allure_step_log
from sugon_web.utils.data import random_data


@pytest.fixture
def oos_page(page):
    """创建OSS页面对象并导航到OSS服务。"""
    oos = OosPage(page)
    oos.goto_service("对象存储")
    return oos


@allure.epic("存储服务")
@allure.feature("对象存储")
@allure.story("桶管理-删除桶")
class TestOSSBucketDelete:
    """对象存储OSS-删除桶验证。"""

    @allure.title("对象存储-删除现有空桶")
    def test_oss_002_delete_existing_empty_bucket(self, oos_page):
        with allure_step_log("步骤1: 导航到对象存储OSS桶列表"):
            oos_page.goto_submenu("桶操作")
            oos_page.wait_for_page_ready()

        with allure_step_log("步骤2: 查找符合条件的autotest空桶"):
            bucket_name = oos_page.oos_bucket_find_empty_autotest()
            if not bucket_name:
                pytest.skip("当前环境未找到对象数量为0且存储用量为0的autotest桶")

        with allure_step_log("步骤3: 删除找到的桶"):
            oos_page.obs_bucket_delete(bucket_name)
            oos_page.assert_deleted(bucket_name)

        with allure_step_log("步骤4: 验证桶已不存在"):
            oos_page.goto_submenu("桶操作")
            oos_page.assert_deleted(bucket_name)

    @allure.title("对象存储-创建桶后立即删除")
    def test_oss_002_create_and_delete_bucket(self, oos_page):
        bucket_name = f"autotest-{random_data(length=8)}"

        with allure_step_log("步骤1: 导航到对象存储OSS桶列表"):
            oos_page.goto_submenu("桶操作")
            oos_page.wait_for_page_ready()

        with allure_step_log("步骤2: 创建新桶"):
            oos_page.oos_bucket_create_minimal(name=bucket_name)
            oos_page.assert_popup_success()

        with allure_step_log("步骤3: 验证桶已创建"):
            oos_page.goto_submenu("桶操作")
            oos_page.assert_list_contain(bucket_name, column_name="桶名称")

        with allure_step_log("步骤4: 删除新创建的桶"):
            oos_page.obs_bucket_delete(bucket_name)
            oos_page.assert_deleted(bucket_name)

        with allure_step_log("步骤5: 验证桶已不存在"):
            oos_page.goto_submenu("桶操作")
            oos_page.assert_deleted(bucket_name)
